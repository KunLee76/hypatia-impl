"""
LoHi-implementation Hierarchical
=====================================================================

Trying LoHi（p×s 分群）：
- 固定文獻的分群模式p×s = 6×10 （每個群包含 6 個連續軌道平面 × 每平面連續 10 顆衛星）
- 分群不依地理位置，依星座生成 `plane_id` 與該平面內的 `pos_in_plane/slot` 2個欄位
- 群際鄰接：2群間存在至少一條跨群 ISL 即建邊
- 群內可能要納入佇列延遲成本（Load-aware in-group）(要注意一下)

對照list
  [1] 分群（p×s）.................. VirtualPIDRouterPlaneBlock
  [2] 群內子圖 + 連通分量 ...................... VirtualPIDRouterPlaneBlock.refresh_pid_members_and_subgraphs()
  [3] 佇列延遲權重（群內） ................... apply_queue_aware_weights_intra_only()
  [4] 群圖（PID 為節點）....................... GroupPlanner.build_group_graph()
  [5] 群際最短路（以群為節點） ................ GroupPlanner.shortest_group_path()
  [6] 邊界挑選.................... BorderSelector.pick_border_pair()
  [7] 端到端 fstate （群內用 Dijkstra） ....... build_fstate_lohi()
  [8] control plane counting（PID/群圖） .......... ControlSignalingStats
  [9] Hypatia 入口 .............................. algorithm_lohi()

- 若缺少欄位，模組會試著從常見鍵名推斷；若仍無法推斷，會以衛星 id 做保守 fallback
"""
from dataclasses import dataclass
from typing import Dict, Set, Tuple, List, Optional, Callable, Any
import datetime as _dt
import heapq
import json
import math
import networkx as nx
import os
import random

# ==========================
# Tunables (LoHi p×s - 文獻固定參數 6×10)
# ==========================
# 環境變數優先，否則使用文獻默認值
PLANES_PER_GROUP = int(os.environ.get('LOHI_PLANES_PER_GROUP', 6))       # p (文獻默認: 6)
SATS_PER_PLANE_IN_GROUP = int(os.environ.get('LOHI_SATS_PER_PLANE', 10))  # s (文獻默認: 10)

# Intra-PID queue-aware weights
BETA_Q = float(os.environ.get('LOHI_BETA_Q', 1.0))   # [3]
BETA_S = float(os.environ.get('LOHI_BETA_S', 0.0))   # [3]

# ============================================================================
# LoHi 階層路由：控制面 vs 資料面分離
# ============================================================================
#
# 控制面（Control Plane）：由管理衛星執行決策
#   - 群間路由（PID graph SPF）
#   - 邊界衛星對選擇  
#   - 負載感知、路由提示生成
#   - 每個 snapshot 計算一次，物化成 FIB
#
# 資料面（Data Plane）：封包轉發
#   - 根據控制面提示，直接往邊界衛星路由
#   - 不需要封包實際繞行管理衛星
#   - 使用勢能場快速路由到出口邊界
#
# 這種設計符合 LoHi 論文的精神：
#   - 管理衛星負責「決策」而非「轉發」
#   - 階層性體現在控制邏輯，而非資料路徑
# ============================================================================

# Management-hop switches (控制資料面是否實際繞行管理衛星)
# 預設都為 False：控制面決策 + 資料面直達（避免 loops）
ENFORCE_MGMT_HOP_CROSS_PID = os.environ.get('LOHI_ENFORCE_MGMT_HOP_CROSS_PID', '0') not in ['0','false','False']
ENFORCE_MGMT_HOP_SAME_PID  = os.environ.get('LOHI_ENFORCE_MGMT_HOP_SAME_PID', '0') not in ['0','false','False']

# Group-level cost (Tg) modeling (since no GET/ICN)
# MODE: 'constant' (default) | 'off'
TG_MODE = os.environ.get('LOHI_TG_MODE', 'constant')
TG_CONST_NG = int(os.environ.get('LOHI_TG_CONST_NG', 10))          # estimated DATA objs per GET
TG_CONST_LAVG_BYTES = int(os.environ.get('LOHI_TG_CONST_LAVG', 1500))  # avg size (bytes) per DATA
LINK_BW_BPS_DEFAULT = float(os.environ.get('LOHI_LINK_BW_BPS', 1_000_000_000))  # 1 Gbps default
TG_SCALE = float(os.environ.get('LOHI_TG_SCALE', 1.0))             # scale factor for combining with hop cost

# ==========================
# Control signaling stats
# ==========================
@dataclass
class EventRow:
    snapshot: int
    sim_time_ms: int
    event: str
    count: int = 1
    bytes: int = 0
    detail: Optional[Dict[str, Any]] = None

class ControlSignalingStats:
    """Collect and export control-plane signaling stats.  [8]

    事件：
      - pid_rebuild: 分群/成員變動
      - topology_change: 依群際邊存在與否的變化
      - routing_update: fstate 差分
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.timeline: List[EventRow] = []
        self.total_bytes = 0
        self.total_events = 0
        self.pid_rebuilds = 0
        self.routing_updates = 0
        self.topology_changes = 0

    def _append(self, row: EventRow):
        self.timeline.append(row)
        self.total_events += row.count
        self.total_bytes += row.bytes

    def record_pid_rebuild(self, snapshot, ms, changed_pids:int):
        """記錄 PID 重建事件
        
        Note:
            bytes 計算交給 analyzer 統一處理（HDR + changed_pids*ENTRY）
        """
        self.pid_rebuilds += 1
        self._append(EventRow(snapshot, ms, 'pid_rebuild', 1, 0,
                              {'changed_pids': changed_pids}))

    def record_topology_change(self, snapshot, ms, delta_group_edges:int):
        """記錄群圖拓撲變化事件
        
        Note:
            bytes 計算交給 analyzer 統一處理（HDR + |delta_group_edges|*ENTRY）
        """
        self.topology_changes += 1
        self._append(EventRow(snapshot, ms, 'topology_change', 1, 0,
                              {'delta_group_edges': delta_group_edges}))

    def record_routing_update(self, snapshot, ms, changed:int, total:int):
        """記錄路由更新事件
        
        Note:
            bytes 計算交給 analyzer 統一處理（HDR + changed*ENTRY）
        """
        self.routing_updates += 1
        self._append(EventRow(snapshot, ms, 'routing_update', 1, 0,
                              {'changed_entries': changed, 'total_entries': total}))

    def to_json(self):
        """
        輸出 JSON 格式統計（與 GID 統一格式）
        使用 by_type 結構來組織事件統計
        """
        # 建立 by_type 結構
        by_type = {}
        for event in self.timeline:
            event_type = event.event
            if event_type not in by_type:
                by_type[event_type] = {"count": 0, "bytes": 0}
            by_type[event_type]["count"] += event.count
            by_type[event_type]["bytes"] += event.bytes
        
        return {
            'summary': {
                'total_events': self.total_events,
                'total_bytes': self.total_bytes,
                'by_type': by_type  # ✅ 統一格式
            },
            'timeline': [
                {
                    'snapshot': row.snapshot,
                    'time_ms': row.sim_time_ms,  # ✅ 統一欄位名
                    'event': row.event,
                    'count': row.count,
                    'bytes': row.bytes,
                    'detail': row.detail
                }
                for row in self.timeline
            ]
        }

_SIGNALING = ControlSignalingStats()

# ==========================
# [1][2] PID router (p×s)
# ==========================
class VirtualPIDRouterPlaneBlock:
    """based PID partitioner + per-PID subgraphs/CC map. [1][2]

    - 以衛星的 (plane_id, pos_in_plane) 依固定 `PLANES_PER_GROUP × SATS_PER_PLANE_IN_GROUP` 分群；
      group_key = (plane_block_id, seg_id_in_plane)，其中：
        plane_block_id = plane_id // PLANES_PER_GROUP
        seg_id_in_plane = pos_in_plane // SATS_PER_PLANE_IN_GROUP
      同一個 group 即為「連續的 p 個平面 × 每平面連續 s 顆衛星」。

    欄位：
      - pid_members: pid_int -> set(sat)
      - pid_key_map: pid_int -> (plane_block_id, seg_id_in_plane)
      - pid_of_sat: sat -> pid_int
      - pid_subgraphs: pid_int -> nx.Graph of intra-PID nodes
      - pid_sat_comp: pid_int -> {sat: comp_id}
      - pid_mgmt_sat: pid_int -> management satellite id (selected deterministically)
      
    **群內圖去抖動**：
      - 維護每 PID 內每條邊的 down_counter
      - 邊消失後保留 M_down 個 snapshot 才真正移除
    """
    def __init__(self, M_down: int = 2, planes_per_group: int = None, sats_per_plane_in_group: int = None):
        """
        Args:
            M_down: 群內邊去抖動參數
            planes_per_group: 每群包含的軌道平面數（None=使用全局默認值）
            sats_per_plane_in_group: 每平面包含的衛星數（None=使用全局默認值）
        """
        self.pid_members: Dict[int, Set[int]] = {}
        self.pid_key_map: Dict[int, Tuple[int,int]] = {}
        self.pid_of_sat: Dict[int,int] = {}
        self.pid_subgraphs: Dict[int, nx.Graph] = {}
        self.pid_sat_comp: Dict[int, Dict[int,int]] = {}
        self.pid_mgmt_sat: Dict[int, int] = {}
        self._prev_pid_of_sat: Dict[int,int] = {}
        self._snapshot_ms = 100
        self._snapshot_idx = 0
        
        # 分群參數（使用傳入值或全局默認值）
        self.planes_per_group = planes_per_group if planes_per_group is not None else PLANES_PER_GROUP
        self.sats_per_plane_in_group = sats_per_plane_in_group if sats_per_plane_in_group is not None else SATS_PER_PLANE_IN_GROUP
        
        # 群內圖去抖動
        self.M_down = M_down
        # pid -> {(u,v): down_counter}
        self.intra_edge_down_counter: Dict[int, Dict[Tuple[int,int], int]] = {}
        # pid -> {(u,v): edge_data}（保留最近的邊數據）
        self.intra_edge_holdover: Dict[int, Dict[Tuple[int,int], dict]] = {}

    def set_snapshot(self, idx:int, step_ms:int):
        self._snapshot_idx = idx
        self._snapshot_ms = step_ms

    # --- helpers to infer plane & position ---
    @staticmethod
    def _infer_plane_and_pos(node_attrs: dict) -> Tuple[Optional[int], Optional[int]]:
        plane_keys = ['plane','orbital_plane','plane_id','walker_plane','orbit_plane']
        pos_keys   = ['slot','pos_in_plane','index_in_plane','walker_index','sat_index_in_plane']
        plane = None
        pos = None
        for k in plane_keys:
            if k in node_attrs:
                try:
                    plane = int(node_attrs[k])
                    break
                except Exception:
                    pass
        for k in pos_keys:
            if k in node_attrs:
                try:
                    pos = int(node_attrs[k])
                    break
                except Exception:
                    pass
        return plane, pos

    def _build_pid_from_plane_blocks(self, G_sat: nx.Graph) -> None:
        """依 p×s 分群（使用固定參數：文獻 6×10 或環境變數覆蓋）"""
        pid_counter = 0
        self.pid_members.clear(); self.pid_key_map.clear(); self.pid_of_sat.clear(); self.pid_mgmt_sat.clear()
        
        # 建立 gkey -> pid_int 的反向映射（避免迭代時修改字典）
        gkey_to_pid: Dict[Tuple[int,int], int] = {}
        
        # 掃描節點，依 plane/pos 產生 group_key
        for sid, attrs in G_sat.nodes(data=True):
            plane, pos = self._infer_plane_and_pos(attrs)
            if plane is None or pos is None:
                plane_block_id = -1
                seg_id_in_plane = (sid // max(1, self.sats_per_plane_in_group)) % self.sats_per_plane_in_group
            else:
                plane_block_id = plane // self.planes_per_group
                seg_id_in_plane = pos // self.sats_per_plane_in_group
            gkey = (plane_block_id, seg_id_in_plane)
            
            # 取得/配置 pid_int（使用臨時映射避免迭代衝突）
            if gkey not in gkey_to_pid:
                pid_int = pid_counter
                pid_counter += 1
                gkey_to_pid[gkey] = pid_int
                self.pid_key_map[pid_int] = gkey
                self.pid_members[pid_int] = set()
            else:
                pid_int = gkey_to_pid[gkey]
            
            self.pid_members[pid_int].add(sid)
            self.pid_of_sat[sid] = pid_int
        
        # 選管理衛星：優先度數最高，次選最小 id（穩定）
        for pid, mem in list(self.pid_members.items()):
            if not mem:
                continue
            Gp = G_sat.subgraph(mem)
            if len(Gp) == 0:
                continue
            try:
                degs = Gp.degree()
                max_deg = max(d for _, d in degs)
                cands = [n for n, d in Gp.degree() if d == max_deg]
                self.pid_mgmt_sat[pid] = min(cands)
            except Exception:
                self.pid_mgmt_sat[pid] = min(mem)

    def refresh_pid_members_and_subgraphs(self,
                                          sat_ids: List[int],
                                          G_sat: nx.Graph) -> Dict[int,int]:
        """p×s分群；建立群內子圖與連通分量；回傳 sat->pid  [2]
        並以 PID 層級統計 membership 變動，用於控制信令
        
        **加入群內圖去抖動**：消失的邊保留 M_down 個 snapshot
        """
        self._build_pid_from_plane_blocks(G_sat)
        # 建群內子圖/分量（加入去抖動）
        self.pid_subgraphs.clear()
        self.pid_sat_comp.clear()
        
        # **修復並發問題**：創建副本避免迭代時修改
        for pid, mem in list(self.pid_members.items()):
            if not mem:
                self.pid_subgraphs[pid] = nx.Graph()
                self.pid_sat_comp[pid] = {}
                continue
            
            # 1. 從 G_sat 取當前觀察到的群內子圖
            Gp_observed = G_sat.subgraph(mem).copy()
            
            # 2. 初始化此 PID 的計數器（如果不存在）
            if pid not in self.intra_edge_down_counter:
                self.intra_edge_down_counter[pid] = {}
            if pid not in self.intra_edge_holdover:
                self.intra_edge_holdover[pid] = {}
            
            # 3. 取得當前觀察到的邊
            observed_edges = set()
            for u, v in Gp_observed.edges():
                edge_key = (min(u, v), max(u, v))
                observed_edges.add(edge_key)
                # 重置 down_counter（邊仍存在）
                self.intra_edge_down_counter[pid][edge_key] = 0
                # 儲存邊數據
                self.intra_edge_holdover[pid][edge_key] = Gp_observed.get_edge_data(u, v).copy()
            
            # 4. 處理消失的邊：down_counter++
            holdover_edges = set()
            for edge_key in list(self.intra_edge_down_counter[pid].keys()):
                if edge_key not in observed_edges:
                    self.intra_edge_down_counter[pid][edge_key] += 1
                    
                    # 如果未超過閾值，保留邊（holdover）
                    if self.intra_edge_down_counter[pid][edge_key] < self.M_down:
                        holdover_edges.add(edge_key)
                    else:
                        # 超過閾值，移除
                        del self.intra_edge_down_counter[pid][edge_key]
                        self.intra_edge_holdover[pid].pop(edge_key, None)
            
            # 5. 建構最終的群內子圖（觀察到的邊 + holdover 邊）
            Gp = Gp_observed.copy()
            for edge_key in holdover_edges:
                u, v = edge_key
                if not Gp.has_edge(u, v):
                    # 恢復邊（使用保存的數據）
                    edge_data = self.intra_edge_holdover[pid].get(edge_key, {})
                    Gp.add_edge(u, v, **edge_data)
            
            self.pid_subgraphs[pid] = Gp
            
            # 6. 重新計算連通分量
            comp_map: Dict[int,int] = {}
            for cid, comp in enumerate(nx.connected_components(Gp)):
                for s in comp:
                    comp_map[s] = cid
            self.pid_sat_comp[pid] = comp_map
        
        # 控制信令：估算 PID 層級變動量
        changed = 0
        if self._prev_pid_of_sat:
            changed_pids = set()
            for sid, p_now in self.pid_of_sat.items():
                p_prev = self._prev_pid_of_sat.get(sid)
                if p_prev is not None and p_prev != p_now:
                    changed_pids.add(p_prev)
                    changed_pids.add(p_now)
            changed = len(changed_pids)
        else:
            changed = sum(1 for _, mem in self.pid_members.items() if mem)
        _SIGNALING.record_pid_rebuild(self._snapshot_idx, self._snapshot_ms*self._snapshot_idx, changed)
        self._prev_pid_of_sat = dict(self.pid_of_sat)
        return dict(self.pid_of_sat)
# ==========================
# [3] 群內佇列延遲權重（不動群際）
# ==========================

def apply_queue_aware_weights_intra_only(G_sat: nx.Graph,
                                         sat_pid: Dict[int,int],
                                         queue_bytes: Optional[Dict[Tuple[int,int], int]],
                                         link_rate_bps: Optional[Dict[Tuple[int,int], float]],
                                         beta_q: float = BETA_Q,
                                         beta_s: float = BETA_S) -> None:
    """僅對群內邊加入排隊延遲處罰，群際邊保留原始 geo_len_m [3]

    weight(u,v) = geo_len_m + beta_q * (queue_bytes*8 / rate_bps) * C_UNIT + beta_s

    - 若缺測量資料，回退為 geo_len_m。
    """
    C_UNIT = 3e5
    for u, v, d in G_sat.edges(data=True):
        base = float(d.get('geo_len_m', d.get('weight', 1.0)))
        pa, pb = sat_pid.get(u), sat_pid.get(v)
        if pa is None or pb is None:
            d['weight'] = base
            continue
        if pa != pb:
            d['weight'] = base
            continue
        if not queue_bytes or not link_rate_bps:
            d['weight'] = base
            continue
        q = None; r = None
        if (u,v) in queue_bytes and (u,v) in link_rate_bps:
            q = queue_bytes[(u,v)]; r = link_rate_bps[(u,v)]
        elif (v,u) in queue_bytes and (v,u) in link_rate_bps:
            q = queue_bytes[(v,u)]; r = link_rate_bps[(v,u)]
        if q is not None and r and r > 0:
            q_delay_s = (q * 8.0) / r
            d['weight'] = base + beta_q * q_delay_s * C_UNIT + beta_s
        else:
            d['weight'] = base

# ==========================
# [4][5] 群圖與群際路徑規劃
# ==========================
class GroupPlanner:
    """維護群圖（以 PID 為節點），並在其上做最短路  [4][5]
    邊成本：
      - 'hop'：成本=1；
      - 'invlinks'：成本=1/#links，偏好多連結之鄰接
    另外維護群邊的 **PID 與實體 ISL 清單**（edge_meta）
    
    **去抖動機制**：
      - 邊的加入需連續 K_up 個 snapshot 觀察到
      - 邊的移除需連續 K_down 個 snapshot 未觀察到
    """
    def __init__(self, K_up: int = 3, K_down: int = 3):
        self.group_graph = nx.Graph()
        self.prev_edges: Set[Tuple[int,int]] = set()
        self.edge_meta: Dict[Tuple[int,int], Dict[str, any]] = {}  # {(a,b): {'pid_id':int,'links':int,'isl_pairs':[(u,v),...]}}
        self._snapshot_idx = 0
        self._snapshot_ms = 100
        self._pid_counter = 0
        
        # 去抖動計數器
        self.K_up = K_up
        self.K_down = K_down
        self.edge_up_counter: Dict[Tuple[int,int], int] = {}    # 連續觀察到的次數
        self.edge_down_counter: Dict[Tuple[int,int], int] = {}  # 連續未觀察到的次數
        self.stable_edges: Set[Tuple[int,int]] = set()          # 穩定的邊（已通過 hysteresis）

    def set_snapshot(self, idx:int, step_ms:int):
        self._snapshot_idx = idx
        self._snapshot_ms = step_ms

    @staticmethod
    def _compute_Tg(links:int) -> float:
        if TG_MODE.lower() == 'off':
            return 0.0
        # constant model: Tg = (Ng * Lavg * 8) / (links * BW)  [seconds]
        Ng = max(1, TG_CONST_NG)
        Lavg_b = max(1, TG_CONST_LAVG_BYTES) * 8.0
        BW = max(1.0, LINK_BW_BPS_DEFAULT)
        Tg = (Ng * Lavg_b) / (max(1, links) * BW)
        return float(Tg)

    def build_group_graph(self, G_sat: nx.Graph, pid_of_sat: Dict[int,int], cost_mode:str='hop'):
        """建構群圖，加入去抖動機制
        
        **改進 8: 啟動期動態 K_up/K_down**
        - 前 5 個 snapshot (500ms)：K_up=1, K_down=1（快速建立群圖）
        - 之後：使用配置的 K_up/K_down（穩定性優先）
        """
        # 動態調整 hysteresis 閾值
        effective_K_up = 1 if self._snapshot_idx < 5 else self.K_up
        effective_K_down = 1 if self._snapshot_idx < 5 else self.K_down
        
        # 1. 統計當前 snapshot 的跨群 ISL
        edge_count: Dict[Tuple[int,int], int] = {}
        isl_pairs: Dict[Tuple[int,int], List[Tuple[int,int]]] = {}
        for u, v, d in G_sat.edges(data=True):
            pa, pb = pid_of_sat.get(u), pid_of_sat.get(v)
            if pa is None or pb is None or pa == pb:
                continue
            a, b = (pa, pb) if pa < pb else (pb, pa)
            edge_count[(a,b)] = edge_count.get((a,b),0) + 1
            isl_pairs.setdefault((a,b), []).append((u,v))
        
        observed_edges = set(edge_count.keys())
        
        # 2. 更新去抖動計數器
        # 2a. 對於觀察到的邊：up_counter++，down_counter=0
        for edge in observed_edges:
            self.edge_up_counter[edge] = self.edge_up_counter.get(edge, 0) + 1
            self.edge_down_counter[edge] = 0
            
            # 如果連續 effective_K_up 次觀察到，加入穩定邊集合
            if self.edge_up_counter[edge] >= effective_K_up:
                self.stable_edges.add(edge)
        
        # 2b. 對於已存在但本次未觀察到的邊：down_counter++，up_counter=0
        for edge in list(self.stable_edges):
            if edge not in observed_edges:
                self.edge_down_counter[edge] = self.edge_down_counter.get(edge, 0) + 1
                self.edge_up_counter[edge] = 0
                
                # 如果連續 effective_K_down 次未觀察到，從穩定邊移除
                if self.edge_down_counter[edge] >= effective_K_down:
                    self.stable_edges.discard(edge)
                    # 清理計數器
                    self.edge_up_counter.pop(edge, None)
                    self.edge_down_counter.pop(edge, None)
        
        # 3. 使用穩定邊建構群圖
        GG = nx.Graph()
        self.edge_meta.clear()
        for (a, b) in self.stable_edges:
            cnt = edge_count.get((a, b), 0)
            if cnt <= 0:
                # holdover：沿用上一輪的 meta（含 isl_pairs），並以較高成本保留
                last = self.edge_meta.get((a, b))
                if last:
                    cnt_last = max(1, last.get('links', 1))
                    Tg = self._compute_Tg(cnt_last)
                    base = 1.0 if cost_mode != 'invlinks' else 1.0 / cnt_last
                    w = (base + TG_SCALE * Tg) * 1.2  # 懲罰：偏好用到本輪觀察到的邊
                    GG.add_edge(a, b, weight=w, links=cnt_last, Tg=Tg)
                    self.edge_meta[(a, b)] = dict(last)
                continue
            
            base = 1.0 if cost_mode != 'invlinks' else 1.0/max(1,cnt)
            Tg = self._compute_Tg(cnt)
            w = base + TG_SCALE * Tg
            GG.add_edge(a, b, weight=w, links=cnt, Tg=Tg)
            
            # assign an id per (a,b) meta PID (logical inter-group path id)
            pid_id = self._pid_counter
            self._pid_counter += 1
            self.edge_meta[(a, b)] = {
                'pid_id': pid_id, 
                'links': cnt, 
                'isl_pairs': isl_pairs.get((a, b), [])
            }
        
        # 4. 記錄拓撲變化（用於信令統計）
        curr = {(a,b) for (a,b) in GG.edges()}
        delta = len(curr - self.prev_edges) - len(self.prev_edges - curr)
        _SIGNALING.record_topology_change(self._snapshot_idx, self._snapshot_ms*self._snapshot_idx, delta)
        self.prev_edges = curr
        self.group_graph = GG

    def shortest_group_path(self, src_pid:int, dst_pid:int) -> List[int]:
        if src_pid == dst_pid:
            return [src_pid]
        if not self.group_graph.has_node(src_pid) or not self.group_graph.has_node(dst_pid):
            return []
        try:
            return nx.shortest_path(self.group_graph, src_pid, dst_pid, weight='weight')
        except nx.NetworkXNoPath:
            return []

    def get_edge_meta(self, a:int, b:int) -> Optional[Dict[str,any]]:
        x, y = (a,b) if a < b else (b,a)
        return self.edge_meta.get((x,y))
    
    def distances_to(self, dst_pid: int):
        """
        以「目的群 dst_pid 為根」計算群圖加權最短路樹。
        回傳 (dist, prev)：
          - dist[g] = g → dst_pid 的最短距離
          - prev[g] = g 往 dst_pid 的下一個「鄰居群」（一致性決策，避免 A<->B 互指）
        """
        GG = self.group_graph
        if not GG.has_node(dst_pid):
            return {}, {}
        dist = {n: float('inf') for n in GG.nodes()}
        prev = {n: None for n in GG.nodes()}
        dist[dst_pid] = 0.0
        # pq: (distance_from_dst, node)
        pq = [(0.0, dst_pid)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            # 從 u 展開到鄰居 v
            for v, edata in GG[u].items():
                w = float(edata.get('weight', 1.0))
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u  # v 往 dst 的下一跳是 u
                    heapq.heappush(pq, (nd, v))
        return dist, prev

# ==========================
# [6] 邊界挑選
# ==========================
class BorderSelector:
    """從 src_PID 指向 next_PID 的所有實體跨邊中，挑一組 (u_in_src, v_in_next)。[6]

    策略：選擇最短 geo_len_m 的邊界對（符合 LoHi 原意）+ 分量感知
    """
    @staticmethod
    @staticmethod
    def pick_border_pair(G_sat: nx.Graph,
                         gplanner: 'GroupPlanner',
                         src_pid:int,
                         next_pid:int,
                         sat_pid: Dict[int, int],
                         src_sat: Optional[int] = None,
                         router: Optional['VirtualPIDRouterPlaneBlock'] = None) -> Optional[Tuple[int,int]]:
        """
        選擇邊界對，優先考慮：
        1. 與來源衛星同分量（src_comp_id）
        2. **與目標 PID 管理衛星同分量**（改進 5）
        3. 最短地理距離
        
        Args:
            src_sat: 來源衛星（用於分量檢查）
            router: PID router（用於獲取分量信息）
        """
        meta = gplanner.get_edge_meta(src_pid, next_pid)
        if not meta:
            return None
        
        # 獲取來源衛星的分量 ID
        src_comp_id = None
        if src_sat is not None and router is not None:
            pid_comp_map = router.pid_sat_comp.get(src_pid, {})
            src_comp_id = pid_comp_map.get(src_sat)
        
        # 獲取目標 PID 管理衛星的分量 ID（改進 5）
        next_mgmt_sat = router.pid_mgmt_sat.get(next_pid) if router else None
        next_mgmt_comp_id = None
        if next_mgmt_sat is not None and router is not None:
            next_pid_comp_map = router.pid_sat_comp.get(next_pid, {})
            next_mgmt_comp_id = next_pid_comp_map.get(next_mgmt_sat)
        
        # 兩階段選擇：先選同 CC 的，再選所有的
        candidates_same_cc = []
        candidates_all = []
        
        for (u, v) in meta.get('isl_pairs', []):
            # 確保方向正確：u 在 src_pid，v 在 next_pid
            if sat_pid.get(u) == next_pid and sat_pid.get(v) == src_pid:
                u, v = v, u  # 交換方向
            
            # **分量感知（來源側）**：u 必須與 src_sat 同分量
            if src_comp_id is not None and router is not None:
                pid_comp_map = router.pid_sat_comp.get(src_pid, {})
                u_comp_id = pid_comp_map.get(u)
                if u_comp_id != src_comp_id:
                    continue  # 跳過不同分量的邊界
            
            d = G_sat.get_edge_data(u, v, default={})
            w = float(d.get('geo_len_m', d.get('weight', 1.0)))
            
            # **分量感知（目標側）**：v 是否與 next_pid 管理衛星同分量？
            v_same_cc_as_mgmt = False
            if next_mgmt_comp_id is not None and router is not None:
                next_pid_comp_map = router.pid_sat_comp.get(next_pid, {})
                v_comp_id = next_pid_comp_map.get(v)
                if v_comp_id == next_mgmt_comp_id:
                    v_same_cc_as_mgmt = True
            
            if v_same_cc_as_mgmt:
                candidates_same_cc.append((w, u, v))
            candidates_all.append((w, u, v))
        
        # 優先從同 CC 候選中選擇
        if candidates_same_cc:
            candidates_same_cc.sort()
            _, u, v = candidates_same_cc[0]
            return (u, v)
        elif candidates_all:
            candidates_all.sort()
            _, u, v = candidates_all[0]
            return (u, v)
        
        return None

# ==========================
# [7] 端到端 fstate 拼接
# ==========================

# ========================================================================
# Phase 1: 勢能單調 + ECMP 擾動 - 模組級輔助函數
# ========================================================================

def _add_ecmp_perturbation(G: nx.Graph, eps: float = 1e-8) -> None:
    """
    為圖的所有邊添加可重現的極小擾動，消除 ECMP 平手問題
    
    Args:
        G: NetworkX 圖
        eps: 擾動大小 (預設 1e-8，足夠小不影響路徑選擇)
    
    擾動規則:
        - 使用邊 ID (min(u,v), max(u,v)) 作為 seed 確保可重現
        - weight_eff = weight + perturbation
        - perturbation ∈ [0, eps)
    """
    for u, v, data in G.edges(data=True):
        # 邊 ID：保證無向圖中 (u,v) 和 (v,u) 使用相同 seed
        edge_id = (min(u, v), max(u, v))
        random.seed(hash(edge_id) % (2**32))
        
        # 擾動值
        perturbation = random.random() * eps
        
        # weight_eff = original_weight + perturbation
        original_weight = data.get('weight', 1.0)
        data['weight_eff'] = original_weight + perturbation

def _build_potential_field(targets: List[int], G: nx.Graph, weight: str = 'weight_eff') -> Dict[int, float]:
    """
    建立勢能場：以目標節點為 source 計算到所有節點的最短距離
    
    Args:
        targets: 目標節點列表 (可能多個)
        G: NetworkX 圖
        weight: 邊權重屬性名稱 (預設 'weight_eff' 使用 ECMP 擾動後的權重)
    
    Returns:
        dist: {node_id: distance_to_nearest_target}
        
    多目標時取 min(dist_to_target_i)
    """
    dist = {n: float('inf') for n in G.nodes()}
    
    for target in targets:
        if target not in G:
            continue
        
        try:
            # 從目標反向計算距離（確保一致性）
            dist_from_target = nx.single_source_dijkstra_path_length(
                G, target, weight=weight
            )
            
            # 更新為最小距離
            for node, d in dist_from_target.items():
                dist[node] = min(dist[node], d)
        except nx.NetworkXError:
            # 目標不在圖中或其他錯誤
            continue
    
    return dist

def _select_potential_descent_neighbor(
    u: int, 
    neighbors: List[int], 
    dist: Dict[int, float], 
    tolerance: float = 1e-6
) -> Optional[int]:
    """
    選擇使勢能下降的鄰居（ECMP 一致性破平手）
    
    Args:
        u: 當前節點
        neighbors: ISL 鄰居列表
        dist: 勢能場 (distance to target)
        tolerance: 容忍度 (允許極小的「水平移動」)
    
    Returns:
        next_hop: 選中的鄰居 ID，若無法選擇則 None
    
    優先級:
        1. 嚴格下降: dist[n] < dist[u] - tolerance
        2. 弱下降: dist[n] <= dist[u] + tolerance
        3. 最小上升: min(dist[n]) where dist[n] > dist[u]
        4. 無法選擇: None (等待 holdover)
    """
    my_dist = dist.get(u, float('inf'))
    
    # 過濾掉距離為 inf 的鄰居（不可達）
    valid_neighbors = [n for n in neighbors if dist.get(n, float('inf')) < float('inf')]
    if not valid_neighbors:
        return None
    
    # 1. 嚴格下降
    strict_descent = [
        n for n in valid_neighbors
        if dist[n] < my_dist - tolerance
    ]
    if strict_descent:
        # ECMP 破平手：選 dist 最小，再選 id 最小
        return min(strict_descent, key=lambda n: (dist[n], n))
    
    # 2. 弱下降（容忍範圍內）
    weak_descent = [
        n for n in valid_neighbors
        if dist[n] <= my_dist + tolerance
    ]
    if weak_descent:
        return min(weak_descent, key=lambda n: (dist[n], n))
    
    # 3. 被迫上升（選上升最少的）
    # 這種情況理論上不應該發生在正確的勢能場中，但作為 fallback
    return min(valid_neighbors, key=lambda n: (dist[n], n))


def _route_direct_in_subgraph(src: int, dst: int, pid: int, 
                               router, G_sat: nx.Graph,
                               intra_tree_cache: Optional[Dict] = None) -> Optional[int]:
    """
    在 PID 子圖內，從 src 直接路由到 dst（優先使用預計算的路徑樹快取）
    
    注意：不處理 src==dst 的情況（應該在主流程攔截）
    
    Args:
        src: 源衛星 ID
        dst: 目標衛星 ID
        pid: PID ID
        router: VirtualPIDRouterPlaneBlock 實例
        G_sat: 衛星網絡圖
        intra_tree_cache: 預計算的群內路徑樹快取 {(dst, pid): {src: next_hop}}
    
    Returns:
        下一跳衛星 ID，或 None（失敗）
    """
    # ★ 性能優化：優先使用預計算的路徑樹快取
    if intra_tree_cache is not None:
        cache_key = (dst, pid)
        if cache_key in intra_tree_cache:
            next_hop_map = intra_tree_cache[cache_key]
            if src in next_hop_map:
                return next_hop_map[src]
    
    # 快取未命中，回退到原有邏輯（勢能場路由）
    
    # 檢查連通性
    comp_map = router.pid_sat_comp.get(pid, {})
    src_comp = comp_map.get(src)
    dst_comp = comp_map.get(dst)
    
    if src_comp is None or dst_comp is None or src_comp != dst_comp:
        return None
    
    # ★ 關鍵修復：不使用 router.pid_subgraphs（多線程競態），直接在 G_sat 上計算
    # 但只考慮該 PID 的節點
    pid_nodes = set(router.pid_members.get(pid, []))
    if src not in pid_nodes or dst not in pid_nodes:
        return None
    
    # 創建臨時子圖視圖（只包含該 PID 的節點）
    subgraph = G_sat.subgraph(pid_nodes)
    
    # 使用勢能場選擇下一跳（tolerance 對齊 ECMP 擾動）
    potential = _build_potential_field([dst], subgraph, weight='weight_eff')
    neighbors = list(G_sat.neighbors(src))  # 使用 G_sat 的鄰居（確保是當前拓撲）
    
    # 只考慮在同一 PID 內的鄰居
    neighbors = [n for n in neighbors if n in pid_nodes]
    
    if not neighbors:
        return None
    
    next_hop = _select_potential_descent_neighbor(
        src, neighbors, potential, tolerance=1e-8
    )
    
    return next_hop


def _fallback_spf_one_hop(src: int, dst: int, G_sat: nx.Graph) -> Optional[int]:
    """
    保底機制：在全網圖上計算到 dst 的 SPF，選擇能使距離下降的鄰居
    
    只選一步，不預先計算整條路徑
    
    Returns:
        下一跳衛星 ID，或 None（失敗）
    """
    if not G_sat.has_node(src) or not G_sat.has_node(dst):
        return None
    
    try:
        # 計算從 dst 到所有節點的距離（反向 Dijkstra）
        distances = nx.single_source_dijkstra_path_length(
            G_sat, dst, weight='weight_eff'
        )
        
        if src not in distances:
            return None
        
        src_dist = distances[src]
        neighbors = list(G_sat.neighbors(src))
        
        if not neighbors:
            return None
        
        # 找能縮短距離的鄰居
        candidates = []
        for neighbor in neighbors:
            if neighbor in distances:
                neighbor_dist = distances[neighbor]
                edge_weight = G_sat[src][neighbor].get('weight_eff', 1.0)
                # 檢查是否在最短路徑上
                if abs(src_dist - edge_weight - neighbor_dist) < 1e-6:
                    candidates.append(neighbor)
        
        # 確定性選擇：ID 最小的鄰居
        if candidates:
            return min(candidates)
        
        return None
    
    except Exception:
        return None


def _break_2cycles(
    fstate: Dict[Tuple[int,int], Tuple[int,int,int]],
    G_sat: nx.Graph,
    sat_pid: Dict[int,int],
    router,  # VirtualPIDRouterPlaneBlock
    num_sats: int,
    dst_sat_map: Dict[int,int],
    isl_if_idxs_func: Callable,
    log_debug_func: Callable,
    max_iterations: int = 3
) -> Dict[Tuple[int,int], Tuple[int,int,int]]:
    """
    作為保險機制，迭代檢測並修復 2-cycles (A ↔ B)
    
    Args:
        fstate: 當前轉發狀態
        G_sat: 衛星圖
        sat_pid: 衛星到群ID映射
        router: 路由器對象（用於獲取子圖）
        num_sats: 衛星總數
        dst_sat_map: 目的地到衛星映射
        isl_if_idxs_func: ISL interface 索引函數
        log_debug_func: 日誌函數
        max_iterations: 最大迭代次數
    
    Returns:
        修復後的 fstate
    
    策略:
        1. 檢測所有 2-cycles: (u, dst) → v, (v, dst) → u
        2. id 較大的改指向勢能下降的鄰居
        3. 若無勢能下降鄰居，設為 None（等待 holdover）
        4. 迭代直到無新 2-cycle 或達最大迭代次數
    """
    for iteration in range(max_iterations):
        cycles_found = []
        
        # 檢測所有 2-cycles
        checked = set()
        for (u, dst), (next_hop, my_if, next_if) in fstate.items():
            if (u, dst) in checked:
                continue
            
            # 檢查是否形成 2-hop loop
            reverse_entry = fstate.get((next_hop, dst))
            if reverse_entry is not None:
                reverse_next = reverse_entry[0]
                if reverse_next == u:
                    # 發現 2-cycle: u ↔ next_hop
                    smaller_id = min(u, next_hop)
                    larger_id = max(u, next_hop)
                    cycles_found.append((smaller_id, larger_id, dst))
                    checked.add((u, dst))
                    checked.add((next_hop, dst))
        
        # ★ 性能優化：如果本輪沒有發現 2-cycle，提前終止
        if not cycles_found:
            # log_debug_func(f"  2-Cycle 清洗第 {iteration+1} 輪：無發現，提前終止")
            break
        
        # 修復: id 較大的改指向勢能下降的鄰居
        fixes_applied = 0
        for (small_id, large_id, dst) in cycles_found:
            # 獲取 large_id 所在的群
            large_pid = sat_pid.get(large_id)
            if large_pid is None:
                continue
            
            # 獲取目標衛星
            dst_sat = dst if dst < num_sats else dst_sat_map.get(dst)
            if dst_sat is None:
                continue
            
            # 建立勢能場
            pid_nodes = set(router.pid_members.get(large_pid, []))
            if large_id not in pid_nodes:
                continue
            
            subgraph = G_sat.subgraph(pid_nodes)
            potential_dist = _build_potential_field([dst_sat], subgraph, weight='weight_eff')
            
            # ★ 改進：先嘗試同 PID 鄰居，若無法修復則允許任何鄰居
            neighbors_in_pid = [n for n in G_sat.neighbors(large_id) if n != small_id and n in pid_nodes]
            new_hop = _select_potential_descent_neighbor(large_id, neighbors_in_pid, potential_dist, tolerance=1e-6)
            
            # 若同 PID 無法修復，使用全局勢能場嘗試任意鄰居
            if new_hop is None:
                global_potential_dist = _build_potential_field([dst_sat], G_sat, weight='weight_eff')
                all_neighbors = [n for n in G_sat.neighbors(large_id) if n != small_id]
                new_hop = _select_potential_descent_neighbor(large_id, all_neighbors, global_potential_dist, tolerance=1e-6)
            
            if new_hop is not None:
                # 成功找到替代路徑
                my_if, next_if = isl_if_idxs_func(large_id, new_hop)
                fstate[(large_id, dst)] = (new_hop, my_if, next_if)
                fixes_applied += 1
            else:
                # 無法修復，移除等待 holdover
                if (large_id, dst) in fstate:
                    del fstate[(large_id, dst)]
                    fixes_applied += 1
        
        # log_debug_func(f"  2-Cycle 清洗第 {iteration+1} 輪：發現 {len(cycles_found)} 個，修復 {fixes_applied} 個")
    
    return fstate


def build_fstate_lohi(
    G_sat: nx.Graph,
    sat_pid: Dict[int,int],
    router: VirtualPIDRouterPlaneBlock,
    gplanner: GroupPlanner,
    ground_station_satellites_in_range,
    satellites,
    ground_stations,
    num_isls_per_sat,
    gid_to_sat_gsl_if_idx,
    prev_dst_sat_map: Optional[Dict[int,int]] = None,  # **改進 6**：歷史 destination GS 視線
    prev_src_sat_map: Optional[Dict[int,int]] = None,  # **改進 12**：歷史 source GS 視線
    prev_fstate: Optional[Dict[Tuple[int,int], Tuple[int,int,int]]] = None,  # **改進 13+**: 歷史 fstate (用於 _safe_write)
) -> Dict[Tuple[int,int], Tuple[int,int,int]]:
    """產生 fstate（第一跳）：(u,dst) -> (next_hop, my_if, next_if)  [7]

    - 一致決策：以「目的群為根」的最短路樹（避免 A<->B 互指 loop）
    - 強制管理衛星跳（ENFORCE_MGMT_HOP=True）：跨群前，先走到群內管理衛星，再走到出口邊界衛星
    - my_if/next_if：ISL 介面索引來自 sat_neighbor_to_if（若可用）或 edge 屬性回退；GSL 介面來自 gid_to_sat_gsl_if_idx
    - **改進 6**：destination GS 視線 fallback 沿用歷史（視線連續性）
    - **改進 12**：source GS 視線也沿用歷史（uplink 黏著）
    """
    num_sats = len(satellites) if not isinstance(satellites,int) else satellites
    num_gs = len(ground_stations) if not isinstance(ground_stations,int) else ground_stations

    # ========================================================================
    # 應用 ECMP 擾動到 G_sat（消除平手問題）
    # ========================================================================
    _add_ecmp_perturbation(G_sat, eps=1e-8)

    # 目的集合：將每個 GS 投影到其候選可視衛星所在 PID
    dst_pid_map: Dict[int,int] = {}
    dst_sat_map: Dict[int,int] = {}  # GS node -> best satellite (destination)
    src_sat_map: Dict[int,int] = {}  # **改進 12**：GS node -> best satellite (source)
    
    for gid0 in range(num_gs):
        candidates = ground_station_satellites_in_range.get(gid0, []) if isinstance(ground_station_satellites_in_range, dict) else []
        
        if not candidates:
            # **改進 6**：GS 視線 fallback
            # 優先：沿用上一張的值（視線通常連續）
            gs_node = num_sats + gid0
            if prev_dst_sat_map and gs_node in prev_dst_sat_map:
                fallback_sat = prev_dst_sat_map[gs_node]
                if fallback_sat in sat_pid:
                    dst_pid_map[gs_node] = sat_pid[fallback_sat]
                    dst_sat_map[gs_node] = fallback_sat
                    continue
            
            # 否則：使用簡單 fallback（gid % num_sats）
            fallback_sat = gid0 % num_sats
            if fallback_sat in sat_pid:
                dst_pid_map[gs_node] = sat_pid[fallback_sat]
                dst_sat_map[gs_node] = fallback_sat
            continue
        
        sat_candidate = candidates[0][1] if isinstance(candidates[0], (list,tuple)) and len(candidates[0])>1 else candidates[0]
        if sat_candidate in sat_pid:
            dst_pid_map[num_sats + gid0] = sat_pid[sat_candidate]
            dst_sat_map[num_sats + gid0] = sat_candidate

    # 嘗試取得鄰接介面索引查表（若 algorithm_lohi() 有設）
    global _SAT_NEI_TO_IF  # 可由外層 algorithm_lohi() 在呼叫前設成 sat_neighbor_to_if
    sat_neighbor_to_if = globals().get('_SAT_NEI_TO_IF', None)

    def _isl_if_idxs(u:int, v:int) -> Tuple[int,int]:
        """回傳 u→v 的 (my_if, next_if)。優先 sat_neighbor_to_if[u][v]，否則回退 edge 屬性或 0。"""
        if sat_neighbor_to_if is not None:
            try:
                return int(sat_neighbor_to_if[u][v]), int(sat_neighbor_to_if[v][u])
            except Exception:
                pass
        d = G_sat.get_edge_data(u, v, default={}) or {}
        # 常見的屬性名稱回退（視 Hypatia 版本而定）
        cand_u = d.get('if_u', d.get('if_idx_u', d.get('if_idx_src')))
        cand_v = d.get('if_v', d.get('if_idx_v', d.get('if_idx_dst')))
        mu = int(cand_u) if cand_u is not None else 0
        mv = int(cand_v) if cand_v is not None else 0
        # 最後保底：限制在 0..num_isls_per_sat[u/v]-1
        if num_isls_per_sat and len(num_isls_per_sat) > u and num_isls_per_sat[u] > 0:
            mu %= num_isls_per_sat[u]
        if num_isls_per_sat and len(num_isls_per_sat) > v and num_isls_per_sat[v] > 0:
            mv %= num_isls_per_sat[v]
        return mu, mv
    
    # 目的群為根：快取 prev map，確保全網一致的下一個群決策
    dst_pid_prev_cache: Dict[int, Dict[int,int]] = {}
    # **群內最短路樹快取**：(dst_sat, src_pid) -> {sat_id: next_hop_sat_id}
    intra_group_tree_cache: Dict[Tuple[int,int], Dict[int,int]] = {}
    
    # **精度容忍**：距離比較的誤差範圍
    EPS = 1e-4
    
    fstate: Dict[Tuple[int,int], Tuple[int,int,int]] = {}

    # =========================================================================
    # LoHi 三段式階層路由（控制面 vs 資料面分離）
    # =========================================================================
    #
    # 📊 控制面職責（由管理衛星執行，每個 snapshot 計算一次）：
    #
    # 1️⃣ 群間路由決策（Group-level SPF）
    #    - 管理衛星在群圖(GG)上計算最短路徑
    #    - 決定從 src_PID → dst_PID 的下一跳 PID
    #    - 輸出：pid_to_group_path[dst_pid] = (dist, prev)
    #
    # 2️⃣ 邊界衛星對選擇（Border Pair Selection）
    #    - 管理衛星選擇最佳的跨群 ISL
    #    - 考慮負載、延遲等因素（BorderSelector）
    #    - 輸出：(u_border, v_border) 對
    #
    # 3️⃣ 路由提示生成（Routing Hints / FIB Generation）
    #    - 管理衛星將決策結果物化成 fstate
    #    - 每個衛星獲得「往哪個邊界」的提示
    #    - 輸出：fstate[(u, dst)] = (next_hop, my_if, next_if)
    #
    # 🚀 資料面行為（封包轉發，不繞管理衛星）：
    #    - 查表 fstate，直接往邊界衛星路由
    #    - 使用勢能場快速計算下一跳
    #    - 不需要封包實際經過管理衛星
    #
    # ✅ 這種設計的優勢：
    #    - 階層性體現在控制邏輯（三段式決策）
    #    - 避免資料面繞行導致的 loops
    #    - 快速（勢能場）+ 可擴展（群分區）
    # =========================================================================
    
    # -------------------------------------------------------------------------
    # 控制面職責 1️⃣：群間路由決策（Group-level SPF）
    # -------------------------------------------------------------------------
    # 為每個目標 GS 計算群級路徑（由管理衛星邏輯執行）
    pid_to_group_path = {}  # dst_pid -> (dist, prev) 從 group SPF
    
    for gid in range(num_gs):
        dst_node = num_sats + gid
        if dst_node not in dst_pid_map:
            continue
        
        dst_pid = dst_pid_map[dst_node]
        
        # 如果還沒有計算過這個 dst_pid 的群級路徑
        if dst_pid not in pid_to_group_path:
            dist, prev = gplanner.distances_to(dst_pid)
            pid_to_group_path[dst_pid] = (dist, prev)
    
    # =========================================================================
    # 🚀 性能優化：預計算群內路徑樹（避免重複 SPF）
    # =========================================================================
    # 為每個目標衛星預先計算其所在 PID 內的最短路徑樹
    # 這樣同 PID 內的所有源衛星都可以直接查表，無需重複計算
    
    # 收集所有唯一的目標衛星及其 PID
    unique_dst_targets = {}  # dst_sat -> dst_pid
    for dst_node, dst_sat in dst_sat_map.items():
        dst_pid = sat_pid.get(dst_sat)
        if dst_pid is not None:
            unique_dst_targets[dst_sat] = dst_pid
    
    # 為每個目標衛星預計算群內路徑樹
    # intra_group_tree_cache[(dst_sat, pid)] = {src_sat: next_hop_sat}
    for dst_sat, dst_pid in unique_dst_targets.items():
        cache_key = (dst_sat, dst_pid)
        if cache_key in intra_group_tree_cache:
            continue  # 已經計算過
        
        # 獲取該 PID 的子圖
        Gp = router.pid_subgraphs.get(dst_pid)
        if not Gp or not Gp.has_node(dst_sat):
            continue
        
        # 使用 single_source_dijkstra 一次性計算從 dst_sat 到所有節點的最短路徑
        try:
            lengths, paths = nx.single_source_dijkstra(Gp, dst_sat, weight='weight')
            
            # 建立 next_hop 映射：對每個源節點，記錄其到 dst_sat 的下一跳
            next_hop_map = {}
            for src_node, path in paths.items():
                if src_node == dst_sat:
                    continue  # 跳過目標自己
                if len(path) >= 2:
                    # path = [src_node, hop1, hop2, ..., dst_sat]
                    # 下一跳是 path[1]
                    next_hop_map[src_node] = path[1]
            
            intra_group_tree_cache[cache_key] = next_hop_map
        except (nx.NetworkXNoPath, nx.NodeNotFound, nx.NetworkXError):
            # 無法計算路徑樹（可能圖不連通），跳過
            pass
    
    # 對每個源衛星 → 目標 GS 進行路由
    for u in range(num_sats):
        src_pid = sat_pid.get(u)
        if src_pid is None:
            continue
        
        for gid in range(num_gs):
            dst_node = num_sats + gid
            if dst_node not in dst_sat_map:
                continue
            
            dst_sat = dst_sat_map[dst_node]
            dst_pid = sat_pid.get(dst_sat)
            if dst_pid is None:
                continue
            
            # 特殊情況：已經在目標衛星
            if u == dst_sat:
                gsl_if_idx = gid_to_sat_gsl_if_idx[gid] if gid_to_sat_gsl_if_idx and gid < len(gid_to_sat_gsl_if_idx) else 0
                my_if = num_isls_per_sat[u] + gsl_if_idx if num_isls_per_sat and u < len(num_isls_per_sat) else gsl_if_idx
                fstate[(u, dst_node)] = (dst_node, my_if, 0)
                continue
            
            # ----------------------------------------------------------------
            # 情況 A: 同群路由 (src_pid == dst_pid)
            # ----------------------------------------------------------------
            if src_pid == dst_pid:
                mgmt_sat = router.pid_mgmt_sat.get(src_pid)
                comp_map = router.pid_sat_comp.get(src_pid, {})
                u_comp = comp_map.get(u)
                dst_comp = comp_map.get(dst_sat)
                mgmt_comp = comp_map.get(mgmt_sat) if mgmt_sat else None
                
                # 決定目標
                target = None
                if u == mgmt_sat:
                    # 管理衛星直接往目標走
                    target = dst_sat
                elif (ENFORCE_MGMT_HOP_SAME_PID and mgmt_sat is not None and 
                      u_comp == mgmt_comp == dst_comp):
                    # 同群路由：經過管理衛星（已知導致 loop，default=False）
                    target = mgmt_sat
                else:
                    # 直接到目標
                    target = dst_sat
                
                # 在群內路由（使用預計算的路徑樹快取）
                next_hop = _route_direct_in_subgraph(u, target, src_pid, router, G_sat, intra_group_tree_cache)
                
                # ★ Fix-3: 保底機制
                if next_hop is None:
                    next_hop = _fallback_spf_one_hop(u, dst_sat, G_sat)
                
                # ★ ISL驗證：只寫入有效的ISL連接
                if next_hop is not None and G_sat.has_edge(u, next_hop):
                    my_if, next_if = _isl_if_idxs(u, next_hop)
                    fstate[(u, dst_node)] = (next_hop, my_if, next_if)
                # 否則依賴 holdover
                continue
            
            # ----------------------------------------------------------------
            # 情況 B: 跨群路由 (src_pid != dst_pid)
            # ----------------------------------------------------------------
            # 控制面職責 1️⃣：查詢群間路徑（管理衛星已計算好）
            dist, prev = pid_to_group_path.get(dst_pid, ({}, {}))
            next_pid = prev.get(src_pid)
            
            if next_pid is None:
                # 群圖不連通
                continue
            
            # -------------------------------------------------------------------------
            # 控制面職責 2️⃣：邊界衛星對選擇（管理衛星決策）
            # -------------------------------------------------------------------------
            # BorderSelector 根據負載、延遲等因素選擇最佳跨群 ISL
            border_pair = BorderSelector.pick_border_pair(
                G_sat, gplanner, src_pid, next_pid, sat_pid,
                src_sat=u, router=router
            )
            
            if not border_pair:
                continue
            
            u_border, v_border = border_pair
            # 暫無次佳邊界（未來可擴展）
            u_border2, v_border2 = None, None
            
            # -------------------------------------------------------------------------
            # 控制面職責 3️⃣：FIB 生成（物化路由提示到 fstate）
            # -------------------------------------------------------------------------
            
            # ★ B1. 硬規則：邊界直接跳轉（多層 fallback）
            if u == u_border:
                # 1. 嘗試主邊界
                if G_sat.has_edge(u_border, v_border):
                    my_if, next_if = _isl_if_idxs(u_border, v_border)
                    fstate[(u, dst_node)] = (v_border, my_if, next_if)
                    continue
                
                # 2. 嘗試次佳邊界
                if u_border2 and v_border2:
                    if u == u_border2 and G_sat.has_edge(u_border2, v_border2):
                        my_if, next_if = _isl_if_idxs(u_border2, v_border2)
                        fstate[(u, dst_node)] = (v_border2, my_if, next_if)
                        continue
                    else:
                        # 在群內朝 u_border2 走（使用快取）
                        next_hop = _route_direct_in_subgraph(u, u_border2, src_pid, router, G_sat, intra_group_tree_cache)
                        # ★ ISL驗證
                        if next_hop and G_sat.has_edge(u, next_hop):
                            my_if, next_if = _isl_if_idxs(u, next_hop)
                            fstate[(u, dst_node)] = (next_hop, my_if, next_if)
                            continue
                
                # 3. 嘗試管理中繼（跨群邊界 fallback）
                mgmt_sat = router.pid_mgmt_sat.get(src_pid)
                if ENFORCE_MGMT_HOP_CROSS_PID and mgmt_sat:
                    comp_map = router.pid_sat_comp.get(src_pid, {})
                    if comp_map.get(u) == comp_map.get(mgmt_sat):
                        next_hop = _route_direct_in_subgraph(u, mgmt_sat, src_pid, router, G_sat, intra_group_tree_cache)
                        # ★ ISL驗證
                        if next_hop and G_sat.has_edge(u, next_hop):
                            my_if, next_if = _isl_if_idxs(u, next_hop)
                            fstate[(u, dst_node)] = (next_hop, my_if, next_if)
                            continue
                
                # 4. SPF 保底（目標是邊界）
                fallback_target = u_border2 if u_border2 else u_border
                next_hop = _fallback_spf_one_hop(u, fallback_target, G_sat)
                # ★ ISL驗證
                if next_hop and G_sat.has_edge(u, next_hop):
                    my_if, next_if = _isl_if_idxs(u, next_hop)
                    fstate[(u, dst_node)] = (next_hop, my_if, next_if)
                    continue
                
                # 5. 條件式 holdover
                if prev_fstate and (u, dst_node) in prev_fstate:
                    prev_entry = prev_fstate[(u, dst_node)]
                    prev_next_hop = prev_entry[0]
                    if G_sat.has_edge(u, prev_next_hop):
                        fstate[(u, dst_node)] = prev_entry
                # 否則不寫入（空缺）
                continue
            
            # ★ B2. 資料面：非邊界衛星直接往邊界路由（不繞管理衛星）
            # 
            # 設計理念：
            # - 控制面已經決定好「往哪個邊界出去」（u_border）
            # - 資料面只需執行：直接用勢能場路由到 u_border
            # - 不需要繞行管理衛星（避免 loops，提升性能）
            
            next_hop = _route_direct_in_subgraph(u, u_border, src_pid, router, G_sat, intra_group_tree_cache)
            
            # 保底機制
            if next_hop is None:
                next_hop = _fallback_spf_one_hop(u, u_border, G_sat)
            
            # ★ ISL驗證：確保next_hop是有效的ISL鄰居
            if next_hop is not None and G_sat.has_edge(u, next_hop):
                my_if, next_if = _isl_if_idxs(u, next_hop)
                fstate[(u, dst_node)] = (next_hop, my_if, next_if)
            # 否則依賴 holdover

    # Ground stations to ground stations
    # **改進 12**: Source GS sticky uplink
    for src_gid in range(num_gs):
        src_gs_node = num_sats + src_gid
        
        # 找最近的源衛星（優先當前可見，其次歷史 sticky，最後 fallback）
        src_candidates = ground_station_satellites_in_range.get(src_gid, []) if isinstance(ground_station_satellites_in_range, dict) else []
        
        if src_candidates:
            # 有可見衛星：選第一個
            src_sat = src_candidates[0][1] if isinstance(src_candidates[0], (list,tuple)) and len(src_candidates[0])>1 else src_candidates[0]
        elif prev_src_sat_map and src_gs_node in prev_src_sat_map:
            # 無可見衛星但有歷史：沿用 sticky uplink
            src_sat = prev_src_sat_map[src_gs_node]
            if src_sat not in sat_pid:
                # Fallback 到簡單映射
                src_sat = src_gid % num_sats
        else:
            # 完全沒有：簡單 fallback
            src_sat = src_gid % num_sats
        
        # 記錄 source GS 的附掛衛星（供下次 sticky）
        src_sat_map[src_gs_node] = src_sat
        
        for dst_gid in range(num_gs):
            if src_gid == dst_gid:
                continue
            dst_gs_node = num_sats + dst_gid
            # 從 GS 到最近的衛星
            my_if = 0
            next_if = num_isls_per_sat[src_sat] + gid_to_sat_gsl_if_idx[src_gid] if num_isls_per_sat else 0
            fstate[(src_gs_node, dst_gs_node)] = (src_sat, my_if, next_if)
    
    # ========================================================================
    # 2-Cycle 清洗（保險機制）
    # ========================================================================
    # 定義 no-op log function for _break_2cycles
    def _noop_log(msg):
        pass
    
    fstate = _break_2cycles(fstate, G_sat, sat_pid, router, num_sats, dst_sat_map, _isl_if_idxs, _noop_log, max_iterations=3)
    
    return fstate, dst_sat_map, src_sat_map  # **改進 12**：同時返回 src_sat_map

# ==========================
# Hypatia adapter）
# ==========================
_ROUTER: Optional[VirtualPIDRouterPlaneBlock] = None
_GPLANNER: Optional[GroupPlanner] = None
_PREV_DST_SAT_MAP: Dict[int,int] = {}  # **改進 6**：維護 destination GS->sat 的歷史映射（downlink 黏著）
_PREV_SRC_SAT_MAP: Dict[int,int] = {}  # **改進 12**：維護 source GS->sat 的歷史映射（uplink 黏著）


def init(config: Optional[dict] = None):
    """初始化模組層物件與參數  [9]

    config keys（可做的）：
      - beta_q, beta_s
      - group_cost_mode: 'hop' | 'invlinks'
    """
    global BETA_Q, BETA_S
    global _ROUTER, _GPLANNER

    cfg = config or {}
    BETA_Q = float(cfg.get('beta_q', BETA_Q))
    BETA_S = float(cfg.get('beta_s', BETA_S))

    # 分群參數（使用配置或全局默認值）
    planes_per_group = cfg.get('planes_per_group', PLANES_PER_GROUP)
    sats_per_plane = cfg.get('sats_per_plane_in_group', SATS_PER_PLANE_IN_GROUP)
    
    _ROUTER = VirtualPIDRouterPlaneBlock(
        M_down=2,
        planes_per_group=planes_per_group,
        sats_per_plane_in_group=sats_per_plane
    )
    _GPLANNER = GroupPlanner()
    _SIGNALING.reset()
    
    return {'ok': True, 'msg': f'algorithm_lohi initialized with p={planes_per_group}, s={sats_per_plane}'}


def algorithm_lohi(
    output_dynamic_state_dir,
    time_since_epoch_ns,
    satellites,
    ground_stations,
    sat_net_graph_only_satellites_with_isls,
    ground_station_satellites_in_range,
    num_isls_per_sat,
    sat_neighbor_to_if,
    list_gsl_interfaces_info,
    prev_output,
    enable_verbose_logs,
    # Optional: queue-aware inputs（僅群內作用）
    link_queue_bytes: Optional[Dict[Tuple[int,int], int]] = None,
    link_rate_bps: Optional[Dict[Tuple[int,int], float]] = None,
    epoch: Optional[int] = None,
    time_step_ns: Optional[int] = None,
    group_cost_mode: str = 'hop',
):
    """LoHi 純化版：兩層（群圖 + 群內）組裝 fstate。[9]

    每個 snapshot：
      1) 重置邊權重到 geo_len_m（僅作為基礎）
      2) 分群/子圖/分量（記錄 pid_rebuild）
      3) **僅對群內**加入佇列權重（若提供 queue 量測）
      4) 建立群圖（group graph），以 hop 或 invlinks 當作成本；記錄 topology_change
      5) 以群圖規劃 src_pid→dst_pid；映射到邊界對；群內 SPF 接到邊界；輸出 fstate
      6) 計算 routing_update（以 (u,dst)->next-hop 差分計）
    """
    global _PREV_DST_SAT_MAP, _PREV_SRC_SAT_MAP
    
    assert _ROUTER is not None and _GPLANNER is not None, "call init() first"

    # 時間刻度（必須由主程式提供；Hypatia 給的是 ns）
    assert time_step_ns is not None
    step_ns = int(time_step_ns)
    snapshot_idx = int(time_since_epoch_ns // step_ns)
    step_ms = int(step_ns // 1_000_000)
    _ROUTER.set_snapshot(snapshot_idx, step_ms)
    _GPLANNER.set_snapshot(snapshot_idx, step_ms)

    # (1) 重置權重並添加衛星屬性（plane, pos）到圖節點
    num_sats = len(satellites) if not isinstance(satellites, int) else satellites
    
    for _, _, d in sat_net_graph_only_satellites_with_isls.edges(data=True):
        if 'geo_len_m' in d:
            d['weight'] = d['geo_len_m']
    
    # 添加 plane 和 pos_in_plane 屬性到圖節點
    # 嘗試從常見星座配置推斷（基於衛星總數）
    constellation_config = _infer_constellation_config(num_sats)
    
    for sid in range(num_sats):
        node_data = sat_net_graph_only_satellites_with_isls.nodes.get(sid, None)
        if node_data is None:
            sat_net_graph_only_satellites_with_isls.add_node(sid)
            node_data = sat_net_graph_only_satellites_with_isls.nodes[sid]
        
        # 計算 plane 和 pos
        if constellation_config:
            num_orbits, num_sats_per_orbit = constellation_config
            orbit = sid // num_sats_per_orbit
            pos = sid % num_sats_per_orbit
            node_data['plane'] = orbit
            node_data['pos_in_plane'] = pos
        else:
            # 無法推斷，使用 fallback（讓 _infer_plane_and_pos 處理）
            pass

    # (2) 分群（plane-block：p×s 固定 6×10）
    sat_ids = list(range(num_sats))
    sat_to_pid = _ROUTER.refresh_pid_members_and_subgraphs(sat_ids,
                                                           sat_net_graph_only_satellites_with_isls)

    # (3) 群內佇列權重
    apply_queue_aware_weights_intra_only(sat_net_graph_only_satellites_with_isls,
                                         sat_to_pid,
                                         link_queue_bytes,
                                         link_rate_bps,
                                         beta_q=BETA_Q, beta_s=BETA_S)

    # (4) 群圖（以跨 PID 的實體 ISL 是否存在來決定鄰接）
    _GPLANNER.build_group_graph(sat_net_graph_only_satellites_with_isls,
                                sat_to_pid, cost_mode=group_cost_mode)

    # (5) 生 fstate（LoHi 拼接）
    # ground_station_satellites_in_range 正規化為 {gid0: [(dist, sat_id), ...]}
    gs_map = _normalize_gs_range_candidates(ground_station_satellites_in_range,
                                            satellites, ground_stations)
    
    # GID to satellite GSL interface index
    num_ground_stations = len(ground_stations) if not isinstance(ground_stations, int) else ground_stations
    gid_to_sat_gsl_if_idx = [0] * num_ground_stations  # 每個衛星只有一個 GSL 介面
    
    # 前一次的 fstate（用於差分統計，但不影響文件寫入）
    prev_fstate = None
    if prev_output is not None and 'fstate' in prev_output:
        prev_fstate = prev_output['fstate']
    
    fstate, dst_sat_map, src_sat_map = build_fstate_lohi(
        sat_net_graph_only_satellites_with_isls,
        sat_to_pid,
        _ROUTER,
        _GPLANNER,
        gs_map,
        satellites,
        ground_stations,
        num_isls_per_sat,
        gid_to_sat_gsl_if_idx,
        prev_dst_sat_map=_PREV_DST_SAT_MAP,  # **改進 6**：傳遞歷史 destination GS 視線
        prev_src_sat_map=_PREV_SRC_SAT_MAP,  # **改進 12**：傳遞歷史 source GS 視線
        prev_fstate=prev_fstate,              # **改進 13+**: 傳遞歷史 fstate (用於 _safe_write)
    )
    
    # **改進 6 & 12**：更新全局 dst_sat_map 和 src_sat_map（供下次使用）
    _PREV_DST_SAT_MAP = dst_sat_map
    _PREV_SRC_SAT_MAP = src_sat_map
    
    # ==================== HOLDOVER 機制 ====================
    # 對於本回合算不出來的 (u, dst)，從 prev_fstate 沿用
    # 這避免瞬時抖動造成的缺表 → 斷鏈
    # **FIX**: 驗證 ISL 存在性，避免沿用無效的跳躍
    if prev_fstate:
        holdover_count = 0
        holdover_skipped = 0
        # **修復並發問題**：創建副本避免迭代時修改
        for (src, dst), decision in list(prev_fstate.items()):
            if (src, dst) not in fstate:
                next_hop = decision[0]
                # **FIX**: 只有當 src 和 next_hop 之間真的有 ISL 時才沿用
                # (如果是 src->GS 或 GS->dst，next_hop 可能 >= num_sats，這是合法的)
                if src < num_sats and next_hop < num_sats:
                    # 衛星間跳躍：必須驗證 ISL
                    if sat_net_graph_only_satellites_with_isls.has_edge(src, next_hop):
                        fstate[(src, dst)] = decision
                        holdover_count += 1
                    else:
                        holdover_skipped += 1
                else:
                    # GS 相關跳躍：直接沿用
                    fstate[(src, dst)] = decision
                    holdover_count += 1
        
        if enable_verbose_logs and holdover_skipped > 0:
            print(f"  > Holdover: used {holdover_count}, skipped {holdover_skipped} (no ISL)")
    
    # ==================== **改進 10 & 12**: 全局 SPF FALLBACK ====================
    # 當分層路由完全失敗時（群圖分區導致），使用全局最短路徑作為 fallback
    # **改進 12**: 分批處理，不設硬門檻（冷啟動時缺失路由很多，但仍需 fallback）
    missing_routes = []
    num_sats = len(satellites) if not isinstance(satellites, int) else satellites
    num_gs = len(ground_stations) if not isinstance(ground_stations, int) else ground_stations
    
    # 檢查所有衛星到所有 GS 的路由是否存在
    for u in range(num_sats):
        for gid0 in range(num_gs):
            dst_node = num_sats + gid0
            if (u, dst_node) not in fstate:
                missing_routes.append((u, dst_node, gid0))
    
    # **性能日誌**: 記錄缺失路由數
    if enable_verbose_logs and len(missing_routes) > 0:
        print(f"  > Global fallback: {len(missing_routes)} missing routes (out of {num_sats * num_gs} total)")
    
    # **改進 12**: 處理所有缺失路由（移除批次限制以確保完整性）
    # 之前的 batch_size=2000 會導致部分路由缺失
    if missing_routes:
        # **階段 2 優化**: 批次 SPF - 每個目標衛星只計算一次
        # 收集所有唯一的目標衛星
        target_sats = {}  # dst_sat -> [(u, dst_node, gid0), ...]
        
        # 處理所有缺失路由，不設批次限制
        for u, dst_node, gid0 in missing_routes:
            # 找到目標 GS 的可視衛星
            if dst_node in dst_sat_map:
                dst_sat = dst_sat_map[dst_node]
            elif gid0 in gs_map:
                candidates = gs_map[gid0]
                if candidates:
                    dst_sat = candidates[0][1] if isinstance(candidates[0], (list, tuple)) else candidates[0]
                else:
                    continue
            else:
                continue
            
            # 按目標衛星分組
            if dst_sat not in target_sats:
                target_sats[dst_sat] = []
            target_sats[dst_sat].append((u, dst_node, gid0))
        
        # 簡化的接口索引計算
        def simple_isl_if_idx(u, v, G):
            """簡化的接口索引計算"""
            if not G.has_edge(u, v):
                return 0, 0
            neighbors_u = sorted(G.neighbors(u))
            neighbors_v = sorted(G.neighbors(v))
            my_if = neighbors_u.index(v) if v in neighbors_u else 0
            next_if = neighbors_v.index(u) if u in neighbors_v else 0
            return my_if, next_if
        
        # 對每個目標衛星執行一次 single_source_dijkstra（反向路徑）
        if enable_verbose_logs:
            print(f"  > Computing global SPF for {len(target_sats)} unique target satellites...")
        
        for dst_sat, routes in target_sats.items():
            if not sat_net_graph_only_satellites_with_isls.has_node(dst_sat):
                continue
            
            try:
                # 從目標衛星計算到所有節點的最短路徑（反向）
                lengths, paths = nx.single_source_dijkstra(
                    sat_net_graph_only_satellites_with_isls, 
                    dst_sat, 
                    weight='weight'
                )
                
                # 對該目標衛星的所有缺失路由填充
                skipped_due_to_no_isl = 0
                filled_count = 0
                for u, dst_node, gid0 in routes:
                    if u in paths:
                        path = paths[u]
                        # path = [dst_sat, ..., hop2, hop1, u]
                        # 我們需要從 u 的下一跳，即 path 的倒數第二個節點
                        if len(path) >= 2:
                            next_hop = path[-2]  # 倒數第二個是 u 的下一跳
                            # **FIX**: 只有當 u 和 next_hop 之間真的有 ISL 時才寫入
                            if sat_net_graph_only_satellites_with_isls.has_edge(u, next_hop):
                                my_if, next_if = simple_isl_if_idx(u, next_hop, sat_net_graph_only_satellites_with_isls)
                                fstate[(u, dst_node)] = (next_hop, my_if, next_if)
                                filled_count += 1
                            else:
                                skipped_due_to_no_isl += 1
                
                if enable_verbose_logs and skipped_due_to_no_isl > 0:
                    print(f"    [WARN] Skipped {skipped_due_to_no_isl} routes for dst_sat={dst_sat} (no ISL). Filled: {filled_count}")
                
            except (nx.NetworkXNoPath, nx.NodeNotFound, nx.NetworkXError):
                # 該目標衛星不可達，跳過
                pass

    # ==================== 最終 2-CYCLE 清理 ====================
    # **關鍵修復**: Holdover 和 Global SPF 可能重新引入 2-cycles
    # 必須在所有路由填充完成後，再次執行 _break_2cycles
    if enable_verbose_logs:
        print("  > Final 2-cycle cleanup after Holdover and Global fallback...")
    
    # 創建 ISL interface 索引函數（直接實現，避免閉包問題）
    def final_isl_if_idxs(u: int, v: int) -> tuple:
        """計算 ISL 接口索引"""
        G = sat_net_graph_only_satellites_with_isls
        if not G.has_edge(u, v):
            return 0, 0
        neighbors_u = sorted(G.neighbors(u))
        neighbors_v = sorted(G.neighbors(v))
        my_if = neighbors_u.index(v) if v in neighbors_u else 0
        next_if = neighbors_v.index(u) if u in neighbors_v else 0
        return my_if, next_if
    
    # 執行最終 2-cycle 清理（使用更多迭代次數確保完全清除）
    fstate = _break_2cycles(
        fstate, 
        sat_net_graph_only_satellites_with_isls, 
        sat_to_pid, 
        _ROUTER, 
        num_sats, 
        dst_sat_map, 
        final_isl_if_idxs,  # ★ 修復：使用閉包函數
        lambda *args, **kwargs: None,  # no-op log
        max_iterations=20  # 進一步增加迭代次數（從10→20）
    )

    # ==================== 移除最終強制刪除機制 ====================
    # 原因：強制刪除會導致路徑斷裂，造成不可達
    # _break_2cycles 應該已經處理了所有循環
    # 如果仍有殘留循環，說明算法本身有問題，需要修復算法而非強制刪除

    # 寫入 fstate 文件（寫入所有路由，包含 holdover 和 global fallback）
    output_filename = output_dynamic_state_dir + "/fstate_" + str(time_since_epoch_ns) + ".txt"
    if enable_verbose_logs:
        print("  > Writing LoHi forwarding state to: " + output_filename)
    with open(output_filename, "w+") as f_out:
        for (src, dst), decision in sorted(fstate.items()):
            # decision = (next_hop, my_if, next_if)
            f_out.write("%d,%d,%d,%d,%d\n" % (
                src, dst,
                decision[0],  # next_hop
                decision[1],  # my_if
                decision[2]   # next_if
            ))

    # (6) 路由差分
    flat = {(u,d): nh[0] for (u,d), nh in fstate.items()} if fstate else {}
    total = len(flat)
    changed = 0
    if hasattr(_ROUTER, '_prev_flat_fstate') and _ROUTER._prev_flat_fstate:
        prev = _ROUTER._prev_flat_fstate
        keys = set(prev.keys()) | set(flat.keys())
        for k in keys:
            if prev.get(k) != flat.get(k):
                changed += 1
    else:
        changed = total
    _ROUTER._prev_flat_fstate = flat
    _SIGNALING.record_routing_update(snapshot_idx, step_ms*snapshot_idx, changed, total)

    # 輸出統計
    stats_dir = 'analytic_result'
    os.makedirs(stats_dir, exist_ok=True)
    with open(os.path.join(stats_dir, f"lohi_signaling_stats_pure_p{PLANES_PER_GROUP}_s{SATS_PER_PLANE_IN_GROUP}.json"), 'w', encoding='utf-8') as f:
        json.dump({
            'algorithm': 'algorithm_lohi_pure',
            'algorithm_display_name': f'LoHi (p={PLANES_PER_GROUP}, s={SATS_PER_PLANE_IN_GROUP})',  # ✅ 新增顯示名稱
            'p': PLANES_PER_GROUP,
            's': SATS_PER_PLANE_IN_GROUP,
            'timestamp': _dt.datetime.now().isoformat(),
            **_SIGNALING.to_json()
        }, f, indent=2, ensure_ascii=False)

    return {'fstate': fstate, 'signaling_stats': _SIGNALING.to_json()}

# ==========================
# Utilities
# ==========================

def _infer_constellation_config(num_sats: int) -> Optional[Tuple[int, int]]:
    """推斷星座配置（num_orbits, num_sats_per_orbit）基於總衛星數
    
    常見配置：
    - Starlink-550: 72 orbits × 22 sats = 1584
    - OneWeb-1200: 18 orbits × 40 sats = 720
    - Kuiper-630: 34 orbits × 34 sats = 1156
    - Telesat-1015: 27 orbits × 13 sats = 351
    
    如果無法匹配，嘗試因數分解找合理的配置
    """
    # 已知星座配置
    known_configs = {
        1584: (72, 22),  # Starlink-550
        720: (18, 40),   # OneWeb-1200
        1156: (34, 34),  # Kuiper-630
        351: (27, 13),   # Telesat-1015
        # 可以添加更多
    }
    
    if num_sats in known_configs:
        return known_configs[num_sats]
    
    # 嘗試因數分解找接近正方形的配置
    # 優先選擇接近 sqrt(n) 的因數對
    best_factor = None
    min_diff = float('inf')
    sqrt_n = int(math.sqrt(num_sats))
    
    for i in range(max(1, sqrt_n - 20), sqrt_n + 20):
        if num_sats % i == 0:
            j = num_sats // i
            diff = abs(i - j)
            if diff < min_diff:
                min_diff = diff
                best_factor = (i, j)
    
    return best_factor if best_factor else None


def _normalize_gs_range_candidates(raw_map, satellites, ground_stations):
    num_sats = len(satellites) if not isinstance(satellites,int) else satellites
    num_gs = len(ground_stations) if not isinstance(ground_stations,int) else ground_stations
    out = {i: [] for i in range(num_gs)}
    if raw_map is None:
        return out
    if isinstance(raw_map, (list, tuple)):
        for gid0 in range(min(len(raw_map), num_gs)):
            vals = raw_map[gid0]
            out[gid0] = list(vals) if not isinstance(vals, list) else vals
        return out
    if isinstance(raw_map, dict) and raw_map:
        ks = list(raw_map.keys())
        if all(isinstance(k, int) and 0 <= k < num_gs for k in ks):
            for gid0 in range(num_gs):
                vals = raw_map.get(gid0, [])
                out[gid0] = list(vals) if not isinstance(vals, list) else vals
            return out
        if all(isinstance(k, int) and num_sats <= k < num_sats+num_gs for k in ks):
            for gnode, vals in raw_map.items():
                gid0 = gnode - num_sats
                if 0 <= gid0 < num_gs:
                    out[gid0] = list(vals) if not isinstance(vals, list) else vals
            return out
        for key, vals in raw_map.items():
            if not isinstance(key, int):
                continue
            if 0 <= key < num_gs:
                out[key] = list(vals) if not isinstance(vals, list) else vals
            elif num_sats <= key < num_sats+num_gs:
                gid0 = key - num_sats
                out[gid0] = list(vals) if not isinstance(vals, list) else vals
    return out

# Aliases
run = algorithm_lohi
route_snapshot = algorithm_lohi
