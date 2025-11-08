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
import math
import os
import json
import datetime as _dt
import networkx as nx

# ==========================
# Tunables (LoHi p×s fixed)
# ==========================
PLANES_PER_GROUP = 6                   # p
SATS_PER_PLANE_IN_GROUP = 10           # s

# Intra-PID queue-aware weights
BETA_Q = float(os.environ.get('LOHI_BETA_Q', 1.0))   # [3]
BETA_S = float(os.environ.get('LOHI_BETA_S', 0.0))   # [3]

# Enforce management-hop at every group (LoHi management behavior)
ENFORCE_MGMT_HOP = os.environ.get('LOHI_ENFORCE_MGMT_HOP', '1') not in ['0','false','False']

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

    def record_pid_rebuild(self, snapshot, ms, changed_pids:int, per_pid_bytes:int=64):
        self.pid_rebuilds += 1
        self._append(EventRow(snapshot, ms, 'pid_rebuild', 1, changed_pids*per_pid_bytes,
                              {'changed_pids': changed_pids}))

    def record_topology_change(self, snapshot, ms, delta_group_edges:int, per:int=16):
        self.topology_changes += 1
        self._append(EventRow(snapshot, ms, 'topology_change', 1,
                              abs(delta_group_edges)*per,
                              {'delta_group_edges': delta_group_edges}))

    def record_routing_update(self, snapshot, ms, changed:int, total:int, per_entry:int=16):
        self.routing_updates += 1
        self._append(EventRow(snapshot, ms, 'routing_update', 1,
                              changed*per_entry,
                              {'changed_entries': changed, 'total_entries': total}))

    def to_json(self):
        return {
            'summary': {
                'total_events': self.total_events,
                'total_bytes': self.total_bytes,
                'pid_rebuilds': self.pid_rebuilds,
                'routing_updates': self.routing_updates,
                'topology_changes': self.topology_changes,
            },
            'timeline': [row.__dict__ for row in self.timeline]
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
    """
    def __init__(self):
        self.pid_members: Dict[int, Set[int]] = {}
        self.pid_key_map: Dict[int, Tuple[int,int]] = {}
        self.pid_of_sat: Dict[int,int] = {}
        self.pid_subgraphs: Dict[int, nx.Graph] = {}
        self.pid_sat_comp: Dict[int, Dict[int,int]] = {}
        self.pid_mgmt_sat: Dict[int, int] = {}
        self._prev_pid_of_sat: Dict[int,int] = {}
        self._snapshot_ms = 100
        self._snapshot_idx = 0

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
        pid_counter = 0
        self.pid_members.clear(); self.pid_key_map.clear(); self.pid_of_sat.clear(); self.pid_mgmt_sat.clear()
        
        # 建立 gkey -> pid_int 的反向映射（避免迭代時修改字典）
        gkey_to_pid: Dict[Tuple[int,int], int] = {}
        
        # 掃描節點，依 plane/pos 產生 group_key
        for sid, attrs in G_sat.nodes(data=True):
            plane, pos = self._infer_plane_and_pos(attrs)
            if plane is None or pos is None:
                plane_block_id = -1
                seg_id_in_plane = (sid // max(1,SATS_PER_PLANE_IN_GROUP)) % SATS_PER_PLANE_IN_GROUP
            else:
                plane_block_id = plane // PLANES_PER_GROUP
                seg_id_in_plane = pos // SATS_PER_PLANE_IN_GROUP
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
        """
        self._build_pid_from_plane_blocks(G_sat)
        # 建群內子圖/分量
        self.pid_subgraphs.clear(); self.pid_sat_comp.clear()
        for pid, mem in self.pid_members.items():
            if not mem:
                self.pid_subgraphs[pid] = nx.Graph(); self.pid_sat_comp[pid] = {}
                continue
            Gp = G_sat.subgraph(mem).copy()
            self.pid_subgraphs[pid] = Gp
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
                    changed_pids.add(p_prev); changed_pids.add(p_now)
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
    """
    def __init__(self):
        self.group_graph = nx.Graph()
        self.prev_edges: Set[Tuple[int,int]] = set()
        self.edge_meta: Dict[Tuple[int,int], Dict[str, any]] = {}  # {(a,b): {'pid_id':int,'links':int,'isl_pairs':[(u,v),...]}}
        self._snapshot_idx = 0
        self._snapshot_ms = 100
        self._pid_counter = 0

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
        GG = nx.Graph()
        edge_count: Dict[Tuple[int,int], int] = {}
        isl_pairs: Dict[Tuple[int,int], List[Tuple[int,int]]] = {}
        for u, v, d in G_sat.edges(data=True):
            pa, pb = pid_of_sat.get(u), pid_of_sat.get(v)
            if pa is None or pb is None or pa == pb:
                continue
            a, b = (pa, pb) if pa < pb else (pb, pa)
            edge_count[(a,b)] = edge_count.get((a,b),0) + 1
            isl_pairs.setdefault((a,b), []).append((u,v))
        self.edge_meta.clear()
        for (a,b), cnt in edge_count.items():
            if cnt <= 0:
                continue
            base = 1.0 if cost_mode != 'invlinks' else 1.0/max(1,cnt)
            Tg = self._compute_Tg(cnt)
            w = base + TG_SCALE * Tg
            GG.add_edge(a,b, weight=w, links=cnt, Tg=Tg)
            # assign an id per (a,b) meta PID (logical inter-group path id)
            pid_id = self._pid_counter; self._pid_counter += 1
            self.edge_meta[(a,b)] = {'pid_id': pid_id, 'links': cnt, 'isl_pairs': isl_pairs.get((a,b), [])}
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

# ==========================
# [6] 邊界挑選
# ==========================
class BorderSelector:
    """從 src_PID 指向 next_PID 的所有實體跨邊中，挑一組 (u_in_src, v_in_next)。[6]

    策略：選擇最短 geo_len_m 的邊界對（符合 LoHi 原意）
    """
    @staticmethod
    def pick_border_pair(G_sat: nx.Graph,
                         gplanner: 'GroupPlanner',
                         src_pid:int,
                         next_pid:int,
                         sat_pid: Dict[int, int]) -> Optional[Tuple[int,int]]:
        meta = gplanner.get_edge_meta(src_pid, next_pid)
        if not meta:
            return None
        
        best = None
        best_w = float('inf')
        
        for (u, v) in meta.get('isl_pairs', []):
            # 確保方向正確：u 在 src_pid，v 在 next_pid
            if sat_pid.get(u) == next_pid and sat_pid.get(v) == src_pid:
                u, v = v, u  # 交換方向
            
            d = G_sat.get_edge_data(u, v, default={})
            w = float(d.get('geo_len_m', d.get('weight', 1.0)))
            
            if w < best_w:
                best_w = w
                best = (u, v)
        
        return best

# ==========================
# [7] 端到端 fstate 拼接
# ==========================

def _dijkstra_in_pid(G_pid: nx.Graph, src: int, dst: int) -> List[int]:
    try:
        return nx.shortest_path(G_pid, src, dst, weight='weight')
    except Exception:
        return []


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
) -> Dict[Tuple[int,int], Tuple[int,int,int]]:
    """產生 fstate（第一跳）：以 (u,dst) -> (next_hop, my_if, next_if) 的型式返回  [7]

    決策強制包含管理衛星跳點（ENFORCE_MGMT_HOP=True）：
      - 每次欲跨群時，固定：當前節點 → 管理衛星 → 出口邊界衛星
      - 進入新群後重覆同樣規則，直到目的群
    """
    num_sats = len(satellites) if not isinstance(satellites,int) else satellites
    num_gs = len(ground_stations) if not isinstance(ground_stations,int) else ground_stations

    # 目的集合：將每個 GS 投影到其候選可視衛星所在 PID
    dst_pid_map: Dict[int,int] = {}
    dst_sat_map: Dict[int,int] = {}  # GS node -> best satellite
    for gid0 in range(num_gs):
        candidates = ground_station_satellites_in_range.get(gid0, []) if isinstance(ground_station_satellites_in_range, dict) else []
        if not candidates:
            continue
        sat_candidate = candidates[0][1] if isinstance(candidates[0], (list,tuple)) and len(candidates[0])>1 else candidates[0]
        if sat_candidate in sat_pid:
            dst_pid_map[num_sats + gid0] = sat_pid[sat_candidate]
            dst_sat_map[num_sats + gid0] = sat_candidate

    fstate: Dict[Tuple[int,int], Tuple[int,int,int]] = {}

    def _first_step_to(Gp: nx.Graph, cur:int, target:int, sat_neighbor_to_if) -> Optional[Tuple[int,int,int]]:
        """返回 (next_hop, my_if, next_if)"""
        if cur == target:
            return None
        try:
            path = nx.shortest_path(Gp, cur, target, weight='weight')
            if len(path) < 2:
                return None
            next_hop = path[1]
            my_if = sat_neighbor_to_if.get((cur, next_hop), 0)
            next_if = sat_neighbor_to_if.get((next_hop, cur), 0)
            return (next_hop, my_if, next_if)
        except Exception:
            return None

    # 建立 sat_neighbor_to_if 映射（如果不存在）
    sat_neighbor_to_if = {}
    for u in G_sat.nodes():
        if_idx = 0
        for v in G_sat.neighbors(u):
            if (u, v) not in sat_neighbor_to_if:
                sat_neighbor_to_if[(u, v)] = if_idx
                if_idx += 1

    # Satellites to ground stations
    for u in range(num_sats):
        src_pid = sat_pid.get(u)
        if src_pid is None:
            continue
        Gp_src = router.pid_subgraphs.get(src_pid, nx.Graph())
        mgmt_src = router.pid_mgmt_sat.get(src_pid)
        for gid0 in range(num_gs):
            dst_node = num_sats + gid0
            dst_pid = dst_pid_map.get(dst_node)
            if dst_pid is None:
                continue
            pid_path = gplanner.shortest_group_path(src_pid, dst_pid)
            if not pid_path:
                continue
            # 同群：LoHi 管理衛星機制
            if len(pid_path) == 1:
                # 如果當前就是目標衛星，直接到 GS
                dst_sat = dst_sat_map.get(dst_node)
                if u == dst_sat:
                    my_if = num_isls_per_sat[u] + gid_to_sat_gsl_if_idx[gid0]
                    fstate[(u, dst_node)] = (dst_node, my_if, 0)
                    continue
                
                # LoHi 管理衛星邏輯：
                # - 如果當前是管理衛星，直接路由到目標
                # - 如果不是管理衛星且開啟 ENFORCE_MGMT_HOP，先到管理衛星
                if u == mgmt_src:
                    # 管理衛星直接到目標衛星
                    if dst_sat is not None and dst_sat in Gp_src:
                        result = _first_step_to(Gp_src, u, dst_sat, sat_neighbor_to_if)
                        if result is not None:
                            fstate[(u, dst_node)] = result
                elif ENFORCE_MGMT_HOP and mgmt_src is not None and mgmt_src in Gp_src:
                    # 普通衛星先到管理衛星
                    result = _first_step_to(Gp_src, u, mgmt_src, sat_neighbor_to_if)
                    if result is not None:
                        fstate[(u, dst_node)] = result
                else:
                    # 沒有管理衛星或不強制，直接到目標
                    if dst_sat is not None and dst_sat in Gp_src:
                        result = _first_step_to(Gp_src, u, dst_sat, sat_neighbor_to_if)
                        if result is not None:
                            fstate[(u, dst_node)] = result
                continue

            # 跨群：LoHi 管理衛星機制
            next_pid = pid_path[1]
            border = BorderSelector.pick_border_pair(G_sat, gplanner, src_pid, next_pid, sat_pid)
            if not border:
                continue
            u_border, v_border = border

            # 如果當前節點就是邊界衛星，直接跨群
            if u == u_border:
                my_if = sat_neighbor_to_if.get((u, v_border), 0)
                next_if = sat_neighbor_to_if.get((v_border, u), 0)
                fstate[(u, dst_node)] = (v_border, my_if, next_if)
                continue
            
            # LoHi 跨群路由邏輯：
            # - 如果當前是管理衛星，直接路由到邊界衛星
            # - 如果不是管理衛星且開啟 ENFORCE_MGMT_HOP，先到管理衛星
            if u == mgmt_src:
                # 管理衛星直接到邊界衛星
                result = _first_step_to(Gp_src, u, u_border, sat_neighbor_to_if)
                if result is not None:
                    fstate[(u, dst_node)] = result
            elif ENFORCE_MGMT_HOP and mgmt_src is not None and mgmt_src in Gp_src:
                # 普通衛星先到管理衛星（管理衛星會負責到邊界）
                result = _first_step_to(Gp_src, u, mgmt_src, sat_neighbor_to_if)
                if result is not None:
                    fstate[(u, dst_node)] = result
            else:
                # 沒有管理衛星或不強制，直接到邊界
                result = _first_step_to(Gp_src, u, u_border, sat_neighbor_to_if)
                if result is not None:
                    fstate[(u, dst_node)] = result
    
    # Ground stations to ground stations
    for src_gid in range(num_gs):
        src_gs_node = num_sats + src_gid
        # 找最近的源衛星
        candidates = ground_station_satellites_in_range.get(src_gid, []) if isinstance(ground_station_satellites_in_range, dict) else []
        if not candidates:
            continue
        src_sat = candidates[0][1] if isinstance(candidates[0], (list,tuple)) and len(candidates[0])>1 else candidates[0]
        
        for dst_gid in range(num_gs):
            if src_gid == dst_gid:
                continue
            dst_gs_node = num_sats + dst_gid
            # 從 GS 到最近的衛星
            my_if = 0
            next_if = num_isls_per_sat[src_sat] + gid_to_sat_gsl_if_idx[src_gid]
            fstate[(src_gs_node, dst_gs_node)] = (src_sat, my_if, next_if)
    
    return fstate

# ==========================
# Hypatia adapter）
# ==========================
_ROUTER: Optional[VirtualPIDRouterPlaneBlock] = None
_GPLANNER: Optional[GroupPlanner] = None


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

    _ROUTER = VirtualPIDRouterPlaneBlock()
    _GPLANNER = GroupPlanner()
    _SIGNALING.reset()
    return {'ok': True, 'msg': 'algorithm_lohi (pure-LoHi p×s=6×10) initialized'}


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
    
    # 前一次的 fstate（用於只寫差異）
    prev_fstate = None
    if prev_output is not None and 'fstate' in prev_output:
        prev_fstate = prev_output['fstate']
    
    fstate = build_fstate_lohi(
        sat_net_graph_only_satellites_with_isls,
        sat_to_pid,
        _ROUTER,
        _GPLANNER,
        gs_map,
        satellites,
        ground_stations,
        num_isls_per_sat,
        gid_to_sat_gsl_if_idx,
    )
    
    # 寫入 fstate 文件
    output_filename = output_dynamic_state_dir + "/fstate_" + str(time_since_epoch_ns) + ".txt"
    if enable_verbose_logs:
        print("  > Writing LoHi forwarding state to: " + output_filename)
    with open(output_filename, "w+") as f_out:
        for (src, dst), decision in sorted(fstate.items()):
            # decision = (next_hop, my_if, next_if)
            if not prev_fstate or prev_fstate.get((src, dst)) != decision:
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
    - Kuiper-630: 34 orbits × 34 sats = 1156
    - Telesat-1015: 27 orbits × 13 sats = 351
    
    如果無法匹配，嘗試因數分解找合理的配置
    """
    # 已知星座配置
    known_configs = {
        1584: (72, 22),  # Starlink-550
        1156: (34, 34),  # Kuiper-630
        351: (27, 13),   # Telesat-1015
        # 可以添加更多
    }
    
    if num_sats in known_configs:
        return known_configs[num_sats]
    
    # 嘗試因數分解找接近正方形的配置
    # 優先選擇接近 sqrt(n) 的因數對
    import math
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
