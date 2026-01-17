# ============================================
# algorithm_hierarchical_virtual_gid_clean_fixed.py
# ============================================

from typing import Dict, Set, Tuple, List, Optional, Callable, Any
from dataclasses import dataclass
import math
import networkx as nx
from .fstate_calculation import calculate_fstate_shortest_path_without_gs_relaying
import os
import io
import sys
import tempfile
import datetime as _dt
import csv, json
import threading

# -------------------------------
# 全域設定（可依實驗需要調整）
# -------------------------------
# 優先從環境變數讀取，否則使用預設值
GRID_DEG = int(os.environ.get('SATGEN_GRID_DEG', 15))  # 外部指定網格大小
ALLOW_DIAGONAL_NEIGHBOR = True          # ★ GID 8-鄰（含對角）以對應斜向跨面 ISL
ALLOW_GLOBAL_FALLBACK = False           # ★ 預設關閉全域最短路兜底（GID 圖斷了才開）
K_BEST_GATEWAYS = int(os.environ.get('K_BEST_GATEWAYS', 8))  # 每對相鄰 GID 保留的 gateway 候選數（999=保留全部）
GEO_ALPHA = 0.08                        # 地理方向偏好係數（小：不拉歪主成本，建議 0.05~0.1）
MIN_AGENT_HOLD_STEPS = 2                # agent 抖動抑制步數（若你需要 agent）
EARTH_R_KM = 6371.0
MODE_SP_OVER_GID_QUOTIENT = True        # 要逐跳分層，把它改成 False
GWC_REBUILD_PERIOD_SNAPSHOTS = 10      # 每 10 個 snapshot（~1s）才重建候選
GWC_EMA_ALPHA = 0.8                    # 成本EMA的舊值權重
GWC_PUBLISH_JACCARD_THRESHOLD = 0.15   # 新舊top-k集合Jaccard差異門檻（超過才升版）

# -------------------------------
# 控制信令統計
# -------------------------------
@dataclass
class EventRow:
    snapshot: int
    sim_time_ms: int
    event: str
    count: int = 1
    detail: Optional[Dict[str, Any]] = None
    bytes: int = 0

class ControlSignalingStats:
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置統計數據"""
        self.routing_updates = 0        # 路由表更新次數
        self.gateway_updates = 0        # Gateway 候選更新次數
        self.gid_rebuilds = 0          # GID 重建次數
        self.topology_changes = 0       # 拓撲變化次數
        self.total_messages = 0         # 總控制信令數
        self.total_bytes = 0
        self.timeline: List[EventRow] = []
    
    def _append(self, row: EventRow):
        self.total_messages += row.count
        self.total_bytes += row.bytes
        self.timeline.append(row)
    
    def record_routing_update(self, snapshot, sim_time_ms,
                              changed_entries:int, total_entries:int=0,
                              bytes=None):
        """記錄路由表更新
        
        Note:
            bytes 計算交給 analyzer 統一處理（HDR + changed_entries*ENTRY）
        """
        self.routing_updates += 1
        b = bytes if bytes is not None else 0
        # 不要在這裡再增加 total_messages；_append 會依 count +1
        self._append(EventRow(snapshot, sim_time_ms, "routing_update",
                            count=1,
                            detail={"changed_entries": changed_entries,
                                    "total_entries": total_entries,
                                    "diff_ratio": (changed_entries/total_entries if total_entries else 0.0)},
                            bytes=b))
    
    def record_gateway_update(self, snapshot, sim_time_ms,
                              changed_pairs:int, k_published:int=None,
                              bytes=None):
        """
        記錄 Gateway 更新
        
        Args:
            snapshot: 快照索引
            sim_time_ms: 模擬時間（毫秒）
            changed_pairs: 變更的 GID 對數量
            k_published: 發布的 k-best 數量
            bytes: 如果提供，直接使用；否則設為 0 讓 analyzer 計算
        
        Note:
            每對 GID 發送一個控制訊息，訊息內含 k 個 gateway entry
            bytes 計算交給 analyzer 統一處理（n_msgs*HDR + n_entries*ENTRY）
        """
        self.gateway_updates += 1
        
        k_used = k_published or 0
        # 提供完整 detail 讓 analyzer 計算，避免推導錯誤
        detail = {
            "k": k_published,
            "k_used": max(k_used, 1),  # 至少為 1，避免 0-entry 的不合理情況
            "changed_pairs": changed_pairs,
            "num_messages": changed_pairs,  # 每對 GID 一個訊息
            "num_entries": changed_pairs * max(k_used, 1)  # 總 entry 數
        }
        
        # bytes 設為提供值或 0（讓 analyzer 重新計算）
        bytes = bytes if bytes is not None else 0
        
        self._append(EventRow(snapshot, sim_time_ms, "gateway_update",
                            count=1,
                            detail=detail,
                            bytes=bytes))
    
    def record_gid_rebuild(self, snapshot, sim_time_ms,
                           changed_gids:int, bytes=None):
        """記錄 GID 重建
        
        Note:
            bytes 計算交給 analyzer 統一處理（HDR + changed_gids*ENTRY）
        """
        self.gid_rebuilds += 1
        b = bytes if bytes is not None else 0
        self._append(EventRow(snapshot, sim_time_ms, "gid_rebuild",
                              count=1,
                              detail={"changed_gids": changed_gids},
                              bytes=b))
    
    def record_topology_change(self, snapshot, sim_time_ms,
                               delta_isl:int, delta_gsl:int, bytes=None):
        """記錄拓撲變化
        
        Note:
            bytes 計算交給 analyzer 統一處理（HDR + (|delta_isl|+|delta_gsl|)*ENTRY）
        """
        self.topology_changes += 1
        b = bytes if bytes is not None else 0
        self._append(EventRow(snapshot, sim_time_ms, "topology_change",
                              count=1,
                              detail={"delta_isl": delta_isl, "delta_gsl": delta_gsl},
                              bytes=b))
    
    def record_event(self, event_type, snapshot, sim_time_ms, count=1, bytes=0, detail=None):
        """
        通用事件記錄器，給需要自定義計算的場合使用
        
        Args:
            event_type: 事件類型字符串
            snapshot: 快照索引
            sim_time_ms: 模擬時間（毫秒）
            count: 事件數量
            bytes: 控制信令字節數
            detail: 額外詳細信息
        """
        # 更新對應的計數器
        if event_type == "routing_update":
            self.routing_updates += count
        elif event_type == "gateway_update":
            self.gateway_updates += count
        elif event_type == "gid_rebuild":
            self.gid_rebuilds += count
        elif event_type == "topology_change":
            self.topology_changes += count
        
        self._append(EventRow(snapshot, sim_time_ms, event_type, count, detail, bytes))
    
    def get_stats_summary(self, start_time_ms=None, end_time_ms=None):
        """
        獲取統計摘要，可以指定時間窗口
        
        Args:
            start_time_ms: 開始時間（毫秒）
            end_time_ms: 結束時間（毫秒）
        
        Returns:
            包含統計信息的字典
        """
        # 如果指定時間窗口，則過濾事件
        events = self.timeline
        if start_time_ms is not None:
            events = [e for e in events if e.sim_time_ms >= start_time_ms]
        if end_time_ms is not None:
            events = [e for e in events if e.sim_time_ms <= end_time_ms]
        
        # 計算統計數據
        by_type = {}
        total_bytes = 0
        total_count = 0
        
        for event in events:
            if event.event not in by_type:
                by_type[event.event] = {"count": 0, "bytes": 0}
            by_type[event.event]["count"] += event.count
            by_type[event.event]["bytes"] += event.bytes
            total_bytes += event.bytes
            total_count += event.count
        
        return {
            "total_events": total_count,
            "total_bytes": total_bytes,
            "by_type": by_type,
            "time_window": {
                "start_ms": start_time_ms,
                "end_ms": end_time_ms,
                "duration_ms": (end_time_ms - start_time_ms) if start_time_ms and end_time_ms else None
            }
        }
    
    def get_timeline_csv(self):
        """獲取時間軸數據的CSV格式字符串"""
        output = io.StringIO()
        output.write("snapshot,time_ms,event_type,count,bytes,detail\n")
        for event in self.timeline:
            detail_str = str(event.detail) if event.detail else ""
            output.write(f"{event.snapshot},{event.sim_time_ms},{event.event},{event.count},{event.bytes},\"{detail_str}\"\n")
        return output.getvalue()
    
    def save_stats_to_file(self, filepath, include_timeline=True):
        """將統計數據保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=== 控制信令統計摘要 ===\n")
            summary = self.get_stats_summary()
            f.write(f"總事件數: {summary['total_events']}\n")
            f.write(f"總字節數: {summary['total_bytes']}\n")
            f.write("\n各類型事件:\n")
            for event_type, stats in summary['by_type'].items():
                f.write(f"  {event_type}: {stats['count']} 次, {stats['bytes']} 字節\n")
            
            if include_timeline:
                f.write("\n=== 事件時間軸 ===\n")
                f.write(self.get_timeline_csv())
    
    def get_stats(self):
        """獲取基本統計數據（向後兼容）"""
        return {
            "routing_updates": self.routing_updates,
            "gateway_updates": self.gateway_updates,
            "gid_rebuilds": self.gid_rebuilds,
            "topology_changes": self.topology_changes,
            "total_messages": self.total_messages,
            "total_bytes": self.total_bytes
        }
    
    def save_csv(self, timeline_path, summary_path):
        """獲取統計數據"""
        with open(timeline_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["snapshot","sim_time_ms","event","count","bytes","detail_json"])
            for r in self.timeline:
                w.writerow([r.snapshot, r.sim_time_ms, r.event, r.count, r.bytes,
                            (json.dumps(r.detail, ensure_ascii=False) if r.detail else "{}")])
        with open(summary_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["routing_updates","gateway_updates","gid_rebuilds","topology_changes","total_messages","total_bytes"])
            w.writerow([self.routing_updates,self.gateway_updates,self.gid_rebuilds,self.topology_changes,self.total_messages,self.total_bytes])
    
    def save_to_file(self, filepath_txt: str, timeline_path: str = None, summary_path: str = None):
        """保存統計數據到文件"""
        stats = {
            "routing_updates": self.routing_updates,
            "gateway_updates": self.gateway_updates,
            "gid_rebuilds": self.gid_rebuilds,
            "topology_changes": self.topology_changes,
            "total_messages": self.total_messages,
            "total_bytes": self.total_bytes,
        }
        with open(filepath_txt, "w", encoding="utf-8") as f:
            f.write("# Control Signaling Statistics (summary)\n")
            for k, v in stats.items():
                f.write(f"{k}={v}\n")
            f.write("\n# Timeline (latest 20)\n")
            for row in self.timeline[-20:]:
                f.write(f"{row.snapshot},{row.sim_time_ms},{row.event},count={row.count},bytes={row.bytes},detail={row.detail}\n")
        # 可選：若有傳入，順便輸出 CSV
        if timeline_path and summary_path:
            self.save_csv(timeline_path, summary_path)

# Process-local 統計對象 (每個進程維護自己的統計)
_thread_local = threading.local()

def _get_process_local_stats():
    """獲取當前進程的統計對象"""
    if not hasattr(_thread_local, 'stats'):
        _thread_local.stats = ControlSignalingStats()
    return _thread_local.stats

def get_grhr_signaling_stats():
    """獲取 GRHR 算法控制信令統計數據"""
    return _get_process_local_stats().get_stats_summary()

# -------------------------------
# 小工具
# -------------------------------
def _wrap_lon_deg(lon: float) -> float:
    return (lon + 180.0) % 360.0 - 180.0

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dl = math.radians(_wrap_lon_deg(lon2 - lon1))
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2*EARTH_R_KM*math.asin(math.sqrt(a))

# -------------------------------
# VirtualGIDRouter：網格、動態歸戶、子圖/分量
# -------------------------------
class VirtualGIDRouter:
    def __init__(self, grid_deg=GRID_DEG, lon_min=-180, lon_max=180, lat_min=-90, lat_max=90,
                 allow_diagonal_neighbor=ALLOW_DIAGONAL_NEIGHBOR):
        self.grid_deg = grid_deg
        self.lon_min, self.lon_max = lon_min, lon_max
        self.lat_min, self.lat_max = lat_min, lat_max
        self.num_lon = int((lon_max - lon_min) // grid_deg)  # 360/15 = 24
        self.num_lat = int((lat_max - lat_min) // grid_deg)  # 180/15 = 12
        self.num_gid = self.num_lon * self.num_lat
        self.allow_diag = allow_diagonal_neighbor

        # 先把「動態狀態」初始化好
        self.gid_members: Dict[int, Set[int]] = {gid: set() for gid in range(self.num_gid)}
        self.gid_subgraphs: Dict[int, nx.Graph] = {}
        self.gid_sat_comp: Dict[int, Dict[int, int]] = {}

        # 若要 agent，可用下列兩個欄位
        self.gid_agent_sat: Dict[int, Optional[int]] = {}
        self._agent_hold_counter: Dict[int, int] = {}

        # 靜態：GID 鄰接（4 或 8 鄰）
        self.gid_neighbors: Dict[int, Set[int]] = self._build_gid_neighbors()
        _alog("[GID] router init", {
            "grid_deg": self.grid_deg,
            "allow_diagonal_neighbor": self.allow_diag,
            "num_pids": self.num_gid,})

    def _wrap_lon_idx(self, i: int) -> int:
        return i % self.num_lon

    def gid_of(self, lat: float, lon: float) -> int:
        lon_adj = lon
        if lon_adj < self.lon_min:
            lon_adj += 360
        if lon_adj >= self.lon_max:
            lon_adj -= 360
        lon_idx = int((lon_adj - self.lon_min) // self.grid_deg)
        lat_clamped = max(self.lat_min, min(self.lat_max - 1e-9, lat))
        lat_idx = int((lat_clamped - self.lat_min) // self.grid_deg)
        
        # 確保索引不超出範圍
        lon_idx = self._wrap_lon_idx(lon_idx)
        lat_idx = min(lat_idx, self.num_lat - 1)  # 防止極地區域溢出
        
        gid = lat_idx * self.num_lon + lon_idx
        
        # 額外安全檢查（防禦性編程）
        if gid >= self.num_gid:
            # Fallback: 返回最後一個有效 GID
            gid = self.num_gid - 1
        
        return gid

    def _build_gid_neighbors(self) -> Dict[int, Set[int]]:
        neigh = {gid: set() for gid in range(self.num_gid)}
        dirs = [(-1,0),(1,0),(0,-1),(0,1)]
        if self.allow_diag:
            dirs += [(-1,-1),(-1,1),(1,-1),(1,1)]
        for lat_idx in range(self.num_lat):
            for lon_idx in range(self.num_lon):
                gid = lat_idx * self.num_lon + lon_idx
                for dx, dy in dirs:
                    nlon = self._wrap_lon_idx(lon_idx + dx)
                    nlat = lat_idx + dy
                    if 0 <= nlat < self.num_lat:
                        npid = nlat * self.num_lon + nlon
                        neigh[gid].add(npid)
        return neigh

    def _gid_center(self, gid: int) -> Tuple[float, float]:
        lat_idx = gid // self.num_lon
        lon_idx = gid % self.num_lon
        lat_c = self.lat_min + (lat_idx + 0.5) * self.grid_deg
        lon_c = _wrap_lon_deg(self.lon_min + (lon_idx + 0.5) * self.grid_deg)
        return lat_c, lon_c

    def refresh_gid_members_and_subgraphs(self,
                                          sat_ids: List[int],
                                          sat_nadir_latlon: Dict[int, Tuple[float,float]],
                                          G_sat_isls: nx.Graph) -> Dict[int, int]:
        # 依當下位置重建 GID 成員
        for gid in range(self.num_gid):
            self.gid_members[gid].clear()

        sat_gid: Dict[int, int] = {}
        for s in sat_ids:
            lat = lon = None
            # 1) 先用 caller 傳進來的 sat_nadir_latlon
            if s in sat_nadir_latlon:
                lat, lon = sat_nadir_latlon[s]
            else:
                # 2) fallback：從圖節點屬性撈
                data = G_sat_isls.nodes[s] if G_sat_isls.has_node(s) else {}
                for klat, klon in [("nadir_lat_deg","nadir_lon_deg"),
                                ("nadir_lat","nadir_lon"),
                                ("lat_deg","lon_deg"),
                                ("lat","lon"),
                                ("latitude","longitude")]:
                    if klat in data and klon in data:
                        lat, lon = data[klat], data[klon]
                        break

            if lat is None or lon is None:
                print(f"[WARNING] Satellite {s} missing position; skip PID assignment this snapshot")
                continue

            p = self.gid_of(float(lat), float(lon))
            self.gid_members[p].add(s)
            sat_gid[s] = p

        # 建子圖與連通分量
        self.gid_subgraphs.clear()
        self.gid_sat_comp.clear()
        for gid, members in self.gid_members.items():
            if not members:
                self.gid_subgraphs[gid] = nx.Graph()
                self.gid_sat_comp[gid] = {}
                continue
            Gp = G_sat_isls.subgraph(members).copy()
            self.gid_subgraphs[gid] = Gp
            comp_map: Dict[int,int] = {}
            for cid, comp in enumerate(nx.connected_components(Gp)):
                for s in comp:
                    comp_map[s] = cid
            self.gid_sat_comp[gid] = comp_map
        _alog("[GID] neighbors stats", {
            "num_pids": len(self.gid_members),
            "nonempty_neighbor_sets": sum(1 for k, v in self.gid_neighbors.items() if v),
            "sample": {k: sorted(list(v))[:4] for k, v in list(self.gid_neighbors.items())[:4]},})
        
        # [SIGNALING_HOOK 1: PID rebuild done]
        try:
            snapshot = getattr(self, "_snapshot_index", 0)
            sim_time_ms = snapshot * getattr(self, "_snapshot_ms", 100)
            changed_gids = 0
            if hasattr(self, "_prev_sat_to_pid") and self._prev_sat_to_pid:
                prev = self._prev_sat_to_pid
                changed_pid_set = set()
                for s, pid_now in sat_gid.items():
                    pid_prev = prev.get(s)
                    if pid_prev is not None and pid_prev != pid_now:
                        changed_pid_set.add(pid_now); changed_pid_set.add(pid_prev)
                changed_gids = len(changed_pid_set)
            else:
                changed_gids = len(self.gid_members)  # 冷啟動：以全部 PID 視為一次 rebuild
            _get_process_local_stats().record_gid_rebuild(snapshot, sim_time_ms,
                                               changed_gids=changed_gids)
            self._prev_sat_to_pid = dict(sat_gid)
        except Exception:
            pass

        return sat_gid

    # （可選）agent：以幾何中心選最近的衛星 + 抖動抑制
    def select_gid_agents_by_geo_center(self,
                                        sat_nadir_latlon: Dict[int, Tuple[float,float]],
                                        dist_switch_threshold_km: float = 100.0):
        new_agents: Dict[int, Optional[int]] = {}
        for gid, members in self.gid_members.items():
            if not members:
                new_agents[gid] = None
                self._agent_hold_counter[gid] = 0
                continue
            lat_c, lon_c = self._gid_center(gid)
            best_sat, best_d = None, float('inf')
            for s in members:
                lat, lon = sat_nadir_latlon[s]
                d = haversine_km(lat, lon, lat_c, lon_c)
                if d < best_d:
                    best_d, best_sat = d, s
            old = self.gid_agent_sat.get(gid)
            if old in members and old is not None:
                held = self._agent_hold_counter.get(gid, 0)
                lat_o, lon_o = sat_nadir_latlon[old]
                d_old = haversine_km(lat_o, lon_o, lat_c, lon_c)
                if held < MIN_AGENT_HOLD_STEPS or best_d + dist_switch_threshold_km >= d_old:
                    new_agents[gid] = old
                    self._agent_hold_counter[gid] = held + 1
                    continue
            new_agents[gid] = best_sat
            self._agent_hold_counter[gid] = 1
        self.gid_agent_sat = new_agents

# -------------------------------
# GatewayCache：依「當下 ISL」重建跨 GID 候選
# -------------------------------
class GatewayCache:
    def __init__(self, k_best=K_BEST_GATEWAYS):
        self.k_best = k_best
        # 建構期暫存（本次重建的原始候選，未必發布）
        self.candidates: Dict[Tuple[int,int], List[Tuple[int,int,float]]] = {}
        # 已發布（VA對外生效的候選）
        self.published_candidates: Dict[Tuple[int,int], List[Tuple[int,int,float]]] = {}
        self.published_version: int = 0
        # EMA 成本（跨重建持久化）
        self._ema_cost: Dict[Tuple[int,int], float] = {}
        # 診斷
        self._last_rebuild_stats = {}

    def rebuild(self,
                G_sat_isls: nx.Graph,
                sat_gid: Dict[int,int],
                gid_neighbors: Dict[int, Set[int]],
                edge_cost_func: Callable[[int,int,dict], float]) -> None:
        # 說明：此處不做鄰接過濾（避免前置擋掉），蒐集所有跨PID的ISL，
        # 實際是否採用由建圖時（或此後）依鄰接規則決定。
        self.candidates.clear()
        cross_cnt = 0
        for u, v, data in G_sat_isls.edges(data=True):
            pa, pb = sat_gid.get(u), sat_gid.get(v)
            if pa is None or pb is None or pa == pb:
                continue
            c = float(edge_cost_func(u, v, data))
            # 先做一次EMA成本累積（邊方向視為有向）
            key_uv = (u, v)
            if key_uv in self._ema_cost:
                self._ema_cost[key_uv] = GWC_EMA_ALPHA * self._ema_cost[key_uv] + (1.0 - GWC_EMA_ALPHA) * c
            else:
                self._ema_cost[key_uv] = c
            self._push(pa, pb, (u, v, self._ema_cost[key_uv]))

            # 對稱方向
            key_vu = (v, u)
            if key_vu in self._ema_cost:
                self._ema_cost[key_vu] = GWC_EMA_ALPHA * self._ema_cost[key_vu] + (1.0 - GWC_EMA_ALPHA) * c
            else:
                self._ema_cost[key_vu] = c
            self._push(pb, pa, (v, u, self._ema_cost[key_vu]))
            cross_cnt += 1

        # 對每個PID對挑選top-k（依EMA後成本）
        # 若 k_best >= 999，表示保留全部候選（不限制）
        new_candidates: Dict[Tuple[int,int], List[Tuple[int,int,float]]] = {}
        for key, lst in self.candidates.items():
            sorted_lst = sorted(lst, key=lambda x: x[2])
            if self.k_best >= 999:
                new_candidates[key] = sorted_lst  # 保留全部
            else:
                new_candidates[key] = sorted_lst[:self.k_best]

        # 決定是否「發布」：比較新top-k與已發布的top-k集合差異（Jaccard）
        def _topk_set(d):
            # 用無向識別避免 (u,v)/(v,u) 同時出現；這裡仍保留方向性，對集合用tuple固定方向
            return { (u, v) for (u, v, _) in d }

        changed_pairs = 0
        jacc_sum = 0.0
        pair_cnt = 0

        for key, lst in new_candidates.items():
            new_set = _topk_set(lst)
            old_set = _topk_set(self.published_candidates.get(key, []))
            if not old_set and not new_set:
                continue
            inter = len(new_set & old_set)
            union = len(new_set | old_set) or 1
            jacc = 1.0 - (inter / union)
            jacc_sum += jacc
            pair_cnt += 1
            if old_set != new_set and jacc >= GWC_PUBLISH_JACCARD_THRESHOLD:
                # 超過門檻 → 更新此pair的已發布候選
                self.published_candidates[key] = lst
                changed_pairs += 1

        if (self.published_version == 0) and new_candidates:
            # 冷啟動：直接發布所有
            self.published_candidates = new_candidates
            self.published_version = 1

            # [SIGNALING_HOOK 2: Gateway publish (init)]
            try:
                snapshot = getattr(self, "_snapshot_index", 0)
                sim_time_ms = snapshot * getattr(self, "_snapshot_ms", 100)
                changed_pairs = len(self.published_candidates)
                # 估一個本輪使用的 k（取所有 pair 的最大長度）
                k_used = 0
                for lst in self.published_candidates.values():
                    if lst:
                        k_used = max(k_used, len(lst))
                _get_process_local_stats().record_gateway_update(snapshot, sim_time_ms,
                                                       changed_pairs=changed_pairs,
                                                       k_published=k_used)
            except Exception:
                pass
            # [END HOOK 2]
            _alog("[GW] publish init", {"pairs": len(self.published_candidates)})
        elif changed_pairs > 0:
            self.published_version += 1
            # [SIGNALING_HOOK 2: Gateway publish (update)]
            try:
                snapshot = getattr(self, "_snapshot_index", 0)
                sim_time_ms = snapshot * getattr(self, "_snapshot_ms", 100)
                # 估本輪 k（以 new_candidates 的最大長度）
                k_used = 0
                for lst in new_candidates.values():
                    if lst:
                        k_used = max(k_used, len(lst))
                _get_process_local_stats().record_gateway_update(snapshot, sim_time_ms,
                                                       changed_pairs=changed_pairs,
                                                       k_published=k_used)
            except Exception:
                pass
            # [END HOOK 2]
            _alog("[GW] publish update", {
                "version": self.published_version,
                "changed_pairs": changed_pairs,
                "avg_jaccard_delta": (jacc_sum / max(1, pair_cnt)) if pair_cnt else 0.0,
                "pairs_total": len(new_candidates),
            })
        else:
            _alog("[GW] publish keep", {
                "version": self.published_version,
                "pairs_total": len(new_candidates),
                "avg_jaccard_delta": (jacc_sum / max(1, pair_cnt)) if pair_cnt else 0.0,
            })

        self._last_rebuild_stats = {
            "cross_pid_isl_edges": cross_cnt,
            "num_pid_pairs": len(new_candidates),
            "avg_candidates_per_pair": (sum(len(v) for v in new_candidates.values()) / max(1, len(new_candidates))),
        }

    def _push(self, pa, pb, triplet):
        self.candidates.setdefault((pa, pb), []).append(triplet)

    def get(self, pa, pb, published: bool = True) -> List[Tuple[int,int,float]]:
        # 回傳「已發布」候選（預設）；如必要可 published=False 取本次重建的暫存
        base = self.published_candidates if published else self.candidates
        return base.get((pa, pb), [])
    
    def need_rebuild(self, pid_adj_fp):
        return getattr(self, "_last_pid_adj_fp", None) != pid_adj_fp

    def commit(self, pid_adj_fp):
        self._last_pid_adj_fp = pid_adj_fp

# -------------------------------
# 單源樹快取（群內 shortest）
# -------------------------------
class SSSPCache:
    def __init__(self):
        self.cache: Dict[Tuple[int,int], Dict[int,int]] = {}  # (gid, src) -> prev dict

    def clear_all(self):
        """清掉所有單源樹快取（每個 snapshot 建議呼叫一次）。"""
        self.cache.clear()
    
    def get_path(self, Gp: nx.Graph, gid: int, src: int, dst: int) -> List[int]:
        key = (gid, src)
        if key not in self.cache:
            # 只在快取缺少時計算，直接存入快取
            self.cache[key] = nx.single_source_dijkstra_path(Gp, src, weight="weight")

        paths = self.cache[key]  # 之後一律從快取讀
        if dst not in paths:
            raise nx.NetworkXNoPath(f"no path {src}->{dst} in gid {gid}")
        return paths[dst]

    def invalidate_gid(self, gid: int):
        keys = [k for k in self.cache.keys() if k[0] == gid]
        for k in keys:
            self.cache.pop(k, None)

# -------------------------------
# 方向偏好（弱化的地理權重）
# -------------------------------
def reset_edge_weights_to_geo(G: nx.Graph) -> None:
    """把圖上所有邊的 weight 重置為 geo_len_m（若有），避免跨 pair 累積偏重。"""
    for u, v, d in G.edges(data=True):
        if "geo_len_m" in d:
            d["weight"] = d["geo_len_m"]

def apply_directional_weights(G_sat_isls: nx.Graph,
                              sat_pos_xy: Dict[int, Tuple[float,float]],
                              dst_xy: Tuple[float,float],
                              alpha: float = GEO_ALPHA):
    """
    sat_pos_xy: 衛星在平面上的投影（可用經緯度投影或直接 (lon,lat)）
    dst_xy: 目標方向參考（例如 dst_downlink_sat 的地面投影）
    alpha: 小係數；越小越不影響主成本
    """
    def _norm(x,y):
        n = math.hypot(x,y)
        return (x/n, y/n) if n>0 else (0.0,0.0)

    for u, v, data in G_sat_isls.edges(data=True):
        base = data.get("geo_len_m", data.get("weight", 1.0))
        if u not in sat_pos_xy or v not in sat_pos_xy:
            data["weight"] = base
            continue
        ux, uy = sat_pos_xy[u]
        vx, vy = sat_pos_xy[v]
        dx, dy = dst_xy[0] - ux, dst_xy[1] - uy    # 目的方向（from u）
        uvx, uvy = vx - ux, vy - uy               # 邊向量（u→v）
        dux, duy = _norm(dx, dy)
        eux, euy = _norm(uvx, uvy)
        cos_theta = max(-1.0, min(1.0, dux*eux + duy*euy))
        dir_penalty = 1.0 + alpha * (1.0 - cos_theta)  # 越朝向目標 → 越接近 1
        data["weight"] = base * dir_penalty

# -------------------------------
# 資料面寫入 + 診斷
# -------------------------------
def stitch_sat_path(path_nodes: List[int],
                    dst_gs_node_id: int,
                    sat_neighbor_to_if_map: Dict[Tuple[int,int], Tuple[int,int]],
                    fstate: Dict[Tuple[int,int], Tuple[int, int, int]],
                    stitch_skip_samples: List[Tuple[int,int,int]],
                    max_samples: int = 20):
    for i in range(len(path_nodes) - 1):
        u, v = path_nodes[i], path_nodes[i+1]
        if (u, v) not in sat_neighbor_to_if_map or (v, u) not in sat_neighbor_to_if_map:
            if len(stitch_skip_samples) < max_samples:
                stitch_skip_samples.append((u, v, dst_gs_node_id))
            print(f"[STITCH-SKIP] missing ifs for edge {u}->{v} (dst_gs={dst_gs_node_id})")
            continue
        out_if, in_if = sat_neighbor_to_if_map[(u, v)][0], sat_neighbor_to_if_map[(v, u)][1]
        if (u, dst_gs_node_id) not in fstate:
            fstate[(u, dst_gs_node_id)] = (v, out_if, in_if)

# -------------------------------
# 單對 GS 路由（階層式核心）
# -------------------------------
def route_one_pair(router: VirtualGIDRouter,
                   gcache: GatewayCache,
                   sssp_cache: SSSPCache,
                   sat_graph: nx.Graph,             # 全衛星圖（edge["weight"] 已設）
                   gid_graph: nx.Graph,             # GID 商圖（由 router.gid_neighbors 建）
                   gid_of_sat: Callable[[int], int],
                   gid_subgraphs: Dict[int, nx.Graph],
                   gid_sat_comp: Dict[int, Dict[int,int]],
                   sat_neighbor_to_if_map: Dict[Tuple[int,int], Tuple[int,int]],
                   fstate: Dict[Tuple[int,int], Tuple[int,int,int]],
                   src_uplink_sat: int,
                   dst_downlink_sat: int,
                   src_gid: int,
                   dst_gid: int,
                   dst_gs_node_id: int,
                   t_label: str = "t=0"):
    stitch_skip_samples: List[Tuple[int,int,int]] = []

    def intra(gid: int, a: int, b: int) -> List[int]:
        if a == b:
            return [a]
        Gp = gid_subgraphs[gid]
        try:
            return sssp_cache.get_path(Gp, gid, a, b)
        except nx.NetworkXNoPath:
            inA = (a in Gp)
            inB = (b in Gp)
            comp_a = gid_sat_comp[gid].get(a)
            comp_b = gid_sat_comp[gid].get(b)
            print(
                f"[NOPATH] GID={gid} subgraph|V|={Gp.number_of_nodes()} "
                f"no path {a}->{b} (inA={inA}, inB={inB}, comp_a={comp_a}, comp_b={comp_b})"
            )
            raise

    # 1) 同 GID：直接群內到 downlink（最高效率）
    if src_gid == dst_gid:
        path = intra(src_gid, src_uplink_sat, dst_downlink_sat)
        stitch_sat_path(path, dst_gs_node_id, sat_neighbor_to_if_map, fstate, stitch_skip_samples)
        return

    # 2) GID 商圖上找 src_gid → dst_gid 的路徑（相鄰 GID 早退 + 標準跨區）
    try:
        gid_path = nx.shortest_path(gid_graph, src_gid, dst_gid)
    except nx.NetworkXNoPath:
        # 3) 兜底（僅當允許）：全域最短
        if ALLOW_GLOBAL_FALLBACK:
            print(f"[FALLBACK] PID graph disconnected {src_gid}->{dst_gid}, using global shortest.")
            path_nodes = nx.shortest_path(sat_graph, src_uplink_sat, dst_downlink_sat, weight="weight")
            stitch_sat_path(path_nodes, dst_gs_node_id, sat_neighbor_to_if_map, fstate, stitch_skip_samples)
        else:
            print(f"[NOPATH] PID-graph disconnected {src_gid}->{dst_gid}")
        return

    current_sat = src_uplink_sat
    current_gid = src_gid

    for next_gid in gid_path[1:]:
        # 若在迭代中已進入 dst_gid，立刻 Early-Exit
        if current_gid == dst_gid:
            final_path = intra(dst_gid, current_sat, dst_downlink_sat)
            stitch_sat_path(final_path, dst_gs_node_id, sat_neighbor_to_if_map, fstate, stitch_skip_samples)
            break

        # 候選 gateways
        candidates = gcache.get(current_gid, next_gid)

        # --- 同分量過濾 ---
        comp_cur = gid_sat_comp[current_gid].get(current_sat)
        comp_dst = gid_sat_comp[dst_gid].get(dst_downlink_sat) if next_gid == dst_gid else None

        def ok(trip):
            a, b, c = trip
            comp_a = gid_sat_comp[current_gid].get(a)
            if comp_cur is None or comp_a is None or comp_a != comp_cur:
                return False
            if comp_dst is not None:
                comp_b = gid_sat_comp[dst_gid].get(b)
                if comp_b is None or comp_b != comp_dst:
                    return False
            # 必須真有實體 ISL（雙向 if）
            if (a,b) not in sat_neighbor_to_if_map or (b,a) not in sat_neighbor_to_if_map:
                return False
            return True

        filtered = [g for g in candidates if ok(g)]

        # --- 可達集合 fallback ---
        if not filtered:
            try:
                reachable = nx.single_source_shortest_path_length(gid_subgraphs[current_gid], current_sat)
            except Exception:
                reachable = {current_sat: 0}
            best = None
            for u in reachable.keys():
                for v in sat_graph.neighbors(u):
                    if gid_of_sat(v) != next_gid:
                        continue
                    if (u, v) not in sat_neighbor_to_if_map or (v, u) not in sat_neighbor_to_if_map:
                        continue
                    # 分量約束（嚴格）
                    comp_u = gid_sat_comp[current_gid].get(u)
                    if comp_cur is None or comp_u is None or comp_u != comp_cur:
                        continue
                    if next_gid == dst_gid:
                        comp_v = gid_sat_comp[dst_gid].get(v)
                        if comp_v is None or comp_dst is None or comp_v != comp_dst:
                            continue
                    w = sat_graph[u][v].get("weight", 1.0)
                    cand = (u, v, w)
                    if best is None or w < best[2]:
                        best = cand
            if best:
                filtered = [best]

        # --- 還是沒有？改用「替代 next_gid」：在 current_gid 的其他鄰 PID 找可行 gateway ---
        if not filtered:
            alternatives = []
            for alt_pid in router.gid_neighbors[current_gid]:
                # 必須確保 alt_pid 在 GID 圖上仍能到 dst_gid
                try:
                    _ = nx.shortest_path(gid_graph, alt_pid, dst_gid)
                except nx.NetworkXNoPath:
                    continue
                # 從 (current_gid, alt_pid) 候選中找符合分量且真實 ISL 的
                for (a, b, c) in gcache.get(current_gid, alt_pid):
                    comp_a = gid_sat_comp[current_gid].get(a)
                    if comp_cur is None or comp_a is None or comp_a != comp_cur:
                        continue
                    if (a, b) not in sat_neighbor_to_if_map or (b, a) not in sat_neighbor_to_if_map:
                        continue
                    alternatives.append((alt_pid, a, b, c))
            if alternatives:
                # 取成本最低的替代鄰 PID
                alt_pid, a, b, c = min(alternatives, key=lambda x: x[3])
                print(f"[ALT-NEXTPID] change {current_gid}->{next_gid} to {current_gid}->{alt_pid} due to no gateway from current component")
                next_gid = alt_pid
                filtered = [(a, b, c)]

        if not filtered:
            # 真正無解才報 NOPATH（現在比原本更早攔住不通情況）
            print(f"[NOPATH] no usable gateway {current_gid}->{next_gid} from {current_sat} (comp={comp_cur})")
            return

        gw_used = None
        for (a, b, c) in filtered:
            # 成員資格檢查
            if (a not in gid_subgraphs[current_gid]) or (b not in gid_subgraphs.get(next_gid, nx.Graph())):
                continue
            # 分量一致（安全再檢一次，避免任何不同步）
            comp_a = gid_sat_comp[current_gid].get(a)
            if comp_cur is None or comp_a is None or comp_a != comp_cur:
                continue
            if next_gid == dst_gid:
                comp_b = gid_sat_comp[dst_gid].get(b)
                if comp_dst is None or comp_b is None or comp_b != comp_dst:
                    continue
            # 實體 ISL 存在（雙向 if）
            if (a, b) not in sat_neighbor_to_if_map or (b, a) not in sat_neighbor_to_if_map:
                continue
            gw_used = (a, b)
            break

        if gw_used is None:
            print(f"[NOPATH] filtered gateways unusable after membership/comp checks {current_gid}->{next_gid} from {current_sat}")
            return

        satA, satB = gw_used

        # 群內到 satA
        if current_sat != satA:
            try:
                pathA = intra(current_gid, current_sat, satA)
                stitch_sat_path(pathA, dst_gs_node_id, sat_neighbor_to_if_map, fstate, stitch_skip_samples)
            except nx.NetworkXNoPath:
                return

        # 跨 gateway 一跳
        assert (satA, satB) in sat_neighbor_to_if_map and (satB, satA) in sat_neighbor_to_if_map, \
            f"Gateway {satA}->{satB} has no physical ISL"
        print(f"[GATEWAY] {t_label} PID {current_gid}->{next_gid} via {satA}->{satB}")
        stitch_sat_path([satA, satB], dst_gs_node_id, sat_neighbor_to_if_map, fstate, stitch_skip_samples)

        # 前進
        current_sat = satB
        current_gid = next_gid

        # 進入 dst_gid → 立刻 Early-Exit
        if current_gid == dst_gid:
            try:
                final_path = intra(dst_gid, current_sat, dst_downlink_sat)
                stitch_sat_path(final_path, dst_gs_node_id, sat_neighbor_to_if_map, fstate, stitch_skip_samples)
            except nx.NetworkXNoPath:
                pass
            break

    if len(stitch_skip_samples) > 0:
        print(f"[STITCH] Skipped edges: {len(stitch_skip_samples)} (showing up to 20 samples)")

# -------------------------------
# 建 GID 商圖（from router.gid_neighbors）
# -------------------------------
def build_gid_graph(router: VirtualGIDRouter) -> nx.Graph:
    Gp = nx.Graph()
    Gp.add_nodes_from(range(router.num_gid))
    for a, neighs in router.gid_neighbors.items():
        for b in neighs:
            Gp.add_edge(a, b)  # 無權重；表示相鄰允許
    return Gp

def build_gid_constrained_sat_graph(
    G_sat_isls: nx.Graph,
    sat_gid: Dict[int, int],
    gateway_cache: Optional["GatewayCache"],
    router: VirtualGIDRouter
) -> nx.Graph:
    """
    基於分群規則建立「受限衛星圖」：
      - 保留所有 Intra-PID 的 ISL
      - Inter-PID 僅保留 GatewayCache 的 k-best 實體 ISL（雙向）
    如此可把分層語義轉為“邊限制”，再交給最短路引擎。
    """
    Gc = nx.Graph()
    Gc.add_nodes_from(G_sat_isls.nodes(data=True))
    
    # Inter-PID：只放 Gateway 候選（注意相鄰檢查）
    intra_e, inter_e = 0, 0

    # Intra-PID：同群邊全留
    for u, v, data in G_sat_isls.edges(data=True):
        pa, pb = sat_gid.get(u), sat_gid.get(v)
        if pa is not None and pb is not None and pa == pb:
            Gc.add_edge(u, v, **data)
            intra_e += 1

    # Inter-PID：優先使用「已發布」候選，若尚未發布則 fallback 到暫存 candidates
    if gateway_cache is not None:
        cand_src = None
        if getattr(gateway_cache, "published_candidates", None):
            cand_src = gateway_cache.published_candidates
        elif getattr(gateway_cache, "candidates", None):
            cand_src = gateway_cache.candidates  # 冷啟動 fallback
        if cand_src:
            # 創建副本以避免迭代時修改字典
            for (pa, pb), lst in list(cand_src.items()):
                nbrs = router.gid_neighbors.get(pa, None)
                if nbrs is not None and len(nbrs) > 0 and (pb not in nbrs):
                    continue
                for (a, b, _) in lst:
                    if G_sat_isls.has_edge(a, b):
                        data = G_sat_isls.get_edge_data(a, b).copy()
                        if not Gc.has_edge(a, b):
                            Gc.add_edge(a, b, **data)
                            inter_e += 1

    # === 保底放寬：邊太少就把「相鄰 GID 的實體 ISL」補回來（鄰接集合為空 ⇒ 放寬）===
    MIN_EDGES = max(1000, int(G_sat_isls.number_of_nodes() * 2))
    if Gc.number_of_edges() < MIN_EDGES:
        added_relaxed = 0
        for u, v, data in G_sat_isls.edges(data=True):
            pa = sat_gid.get(u)
            pb = sat_gid.get(v)
            if pa is None or pb is None or pa == pb:
                continue
            nbrs = router.gid_neighbors.get(pa, set())
            if (not nbrs) or (pb in nbrs):
                if not Gc.has_edge(u, v):
                    Gc.add_edge(u, v, **data)
                    added_relaxed += 1
        _alog("[SP] relaxed inter-PID edges appended",
              {"before": (Gc.number_of_edges() - added_relaxed),
               "added_relaxed": added_relaxed,
               "after": Gc.number_of_edges(),
               "threshold": MIN_EDGES})

    _alog("[SP] constrained_graph |V|={} |E|={}".format(Gc.number_of_nodes(), Gc.number_of_edges()), {})
    return Gc

# -------------------------------
# 主入口：每個 snapshot 呼叫一次
# -------------------------------
def route_all_gs_pairs(
        router: VirtualGIDRouter,
        gcache: GatewayCache,
        sssp_cache: SSSPCache,
        sat_ids: List[int],
        sat_nadir_latlon: Dict[int, Tuple[float,float]],
        sat_pos_xy: Dict[int, Tuple[float,float]],  # 給方向偏好用；沒有可傳 {} 跳過
        G_sat_isls: nx.Graph,                        # 全衛星圖（edge["weight"] 建議為 delay 或 geo）
        sat_neighbor_to_if_map: Dict[Tuple[int,int], Tuple[int,int]],
        gs_pairs: List[Tuple[int,int,int,int,int]],  # (src_gs, dst_gs, src_uplink_sat, dst_downlink_sat, t_int)
        fstate: Dict[Tuple[int,int], Tuple[int,int,int]]
    ):
    """
    外部把原本 GS×GS 迴圈中的資訊包成 gs_pairs 傳入。
    """
    # 1) 依當下位置重建 GID 成員與子圖/分量
    # 每個 snapshot 先重置邊權重為幾何長度
    reset_edge_weights_to_geo(G_sat_isls)
    sat_gid = router.refresh_gid_members_and_subgraphs(sat_ids, sat_nadir_latlon, G_sat_isls)
    
    # 清空群內 single-source shortest path 快取，避免用到上一個 snapshot
    sssp_cache.clear_all()

    # 2) （可選）選 agent（若其他模組要用）
    router.select_gid_agents_by_geo_center(sat_nadir_latlon)

    # 3) 重建 Gateway 候選（以當下實體 ISL）
    def edge_cost(u, v, data):
        return data.get("weight", data.get("geo_len_m", 1.0))
    gcache.rebuild(G_sat_isls, sat_gid, router.gid_neighbors, edge_cost)

    # 4) 建 GID 商圖（相鄰允許）
    gid_graph = build_gid_graph(router)

    def _pid_of_sat(s: int) -> int:
        return sat_gid[s]

    # 5) 路由每對 GS
    for (_src_gs_node_id, dst_gs_node_id, src_uplink_sat, dst_downlink_sat, t_int) in gs_pairs:
        # 對「目的地」施加弱化方向偏好（僅當 sat_pos_xy 可用）
        if dst_downlink_sat in sat_pos_xy:
            apply_directional_weights(G_sat_isls, sat_pos_xy, sat_pos_xy[dst_downlink_sat], alpha=GEO_ALPHA)

        # 這些變數只在迴圈內才有
        src_gid = _pid_of_sat(src_uplink_sat)
        dst_gid = _pid_of_sat(dst_downlink_sat)
        t_label = f"t={t_int}"

        # 子圖更新後，清掉該兩個 PID 的群內快取，避免使用舊 prev
        sssp_cache.invalidate_gid(src_gid)
        sssp_cache.invalidate_gid(dst_gid)

        route_one_pair(router, gcache, sssp_cache,
                       G_sat_isls, gid_graph, _pid_of_sat,
                       router.gid_subgraphs, router.gid_sat_comp,
                       sat_neighbor_to_if_map, fstate,
                       src_uplink_sat, dst_downlink_sat,
                       src_gid, dst_gid, dst_gs_node_id,
                       t_label=t_label)

_ROUTER = None
_GCACHE = None
_SSSP = None

def init(config=None):
    """主程式在模擬開始時呼叫一次。"""
    global _ROUTER, _GCACHE, _SSSP
    cfg = config or {}
    # 優先從環境變數讀取 grid_deg（支援自動化腳本動態設定）
    grid_deg = cfg.get("grid_deg", int(os.environ.get('SATGEN_GRID_DEG', GRID_DEG)))
    allow_diag = cfg.get("allow_diagonal_neighbor", ALLOW_DIAGONAL_NEIGHBOR)
    k_best = cfg.get("k_best_gateways", K_BEST_GATEWAYS)

    # （可選）覆寫 VA 發布節奏參數
    global GWC_REBUILD_PERIOD_SNAPSHOTS, GWC_EMA_ALPHA, GWC_PUBLISH_JACCARD_THRESHOLD
    GWC_REBUILD_PERIOD_SNAPSHOTS = cfg.get("gwc_rebuild_period_snapshots", GWC_REBUILD_PERIOD_SNAPSHOTS)
    GWC_EMA_ALPHA = cfg.get("gwc_ema_alpha", GWC_EMA_ALPHA)
    GWC_PUBLISH_JACCARD_THRESHOLD = cfg.get("gwc_publish_jaccard_threshold", GWC_PUBLISH_JACCARD_THRESHOLD)

    _ROUTER = VirtualGIDRouter(grid_deg=grid_deg, allow_diagonal_neighbor=allow_diag)
    _GCACHE = GatewayCache(k_best=k_best)
    _SSSP = SSSPCache()
    
    # 重置統計數據 - 直接調用 process-local 方法
    _get_process_local_stats().reset()
    
    return {"ok": True, "msg": "algorithm_hierarchical_virtual_gid initialized"}

def _alog(msg: str, payload: Optional[dict] = None):
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "Z"
    line = f"{ts} {msg}\n"

    # 在當前目錄生成日誌（應該是 paper/satellite_networks_state）
    log_file = "alg_mode.log"
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        # 如果失敗，只輸出到 stderr 作為備用
        print(f"Warning: Could not write to log file: {e}", file=sys.stderr)



def step(payload: dict):
    """
    主程式每個 snapshot/time-step 呼叫一次。
    若 MODE_SP_OVER_GID_QUOTIENT=True → 走 Hypatia 最短路（在 PID 受限圖上）。
    否則 → 走原本逐跳分層（stitch）流程。
    """
    assert _ROUTER and _GCACHE and _SSSP, "Call init() first."

    # 讓 log 一眼看出現在跑哪種模式
    print(f"[MODE] SP_OVER_PID_QUOTIENT={MODE_SP_OVER_GID_QUOTIENT}")

    _alog(f"[MODE] SP_OVER_PID_QUOTIENT={MODE_SP_OVER_GID_QUOTIENT}", payload)

    # 名稱對齊：有些 main 給的是 sat_neighbor_to_if_map，把它對齊成 Hypatia 的 key
    if "sat_neighbor_to_if" not in payload and "sat_neighbor_to_if_map" in payload:
        payload["sat_neighbor_to_if"] = payload["sat_neighbor_to_if_map"]

    if MODE_SP_OVER_GID_QUOTIENT:
        # 在 SP 模式下，若缺少 Hypatia 需要的欄位，就明確列出並「不要」悄悄回退到逐跳
        required_keys = [
            "output_dynamic_state_dir",
            "time_since_epoch_ns",
            "satellites",
            "ground_stations",
            "G_sat_isls",
            "ground_station_satellites_in_range",
            "num_isls_per_sat",
            "sat_neighbor_to_if",
            "list_gsl_interfaces_info",
            "sat_ids",
            "sat_nadir_latlon",
        ]
        missing = [k for k in required_keys if k not in payload]
        if missing:
            _alog(f"[SP-FALLBACK-BLOCKED] Missing keys for SP-mode: {missing}", payload)
            # ★ 直接返回，不回退到逐跳，避免混淆
            return {"ok": False, "error": f"missing keys: {missing}"}

        # ---------- SP over PID-quotient ----------
        sat_ids = payload["sat_ids"]
        sat_nadir_latlon = payload["sat_nadir_latlon"]
        G_sat_isls = payload["G_sat_isls"]

        # （新增）SP 模式也先把權重重置回幾何長度，確保受限圖的基線一致
        reset_edge_weights_to_geo(G_sat_isls)

        # (1) 分群 / 子圖 / 分量
        sat_gid = _ROUTER.refresh_gid_members_and_subgraphs(sat_ids, sat_nadir_latlon, G_sat_isls)

        # 以 snapshot 為節拍：每 N 個 snapshot 才重建候選；其餘沿用已發布版本
        time_ns = payload["time_since_epoch_ns"]
        time_step_ns = payload.get("time_step_ns", 100_000_000)  # 若未提供，預設 100ms
        snapshot_idx = int(time_ns // time_step_ns)

        # 將 snapshot 時間資訊掛到物件，供各種 signaling hooks 使用
        _ROUTER._snapshot_index = snapshot_idx
        _ROUTER._snapshot_ms = int(time_step_ns // 1_000_000) if time_step_ns else 100
        _GCACHE._snapshot_index = snapshot_idx
        _GCACHE._snapshot_ms = getattr(_ROUTER, "_snapshot_ms", 100)

        # （可選）若偵測到PID成員變更很大，也可觸發重建；這裡先簡化只看節拍
        gid_neighbors = _ROUTER.gid_neighbors
        pid_adj_fingerprint = tuple(sorted((a, tuple(sorted(list(bs)))) for a, bs in gid_neighbors.items()))
        period_hit = (snapshot_idx % GWC_REBUILD_PERIOD_SNAPSHOTS == 0)
        first_time = (_GCACHE.published_version == 0)
        adj_changed = _GCACHE.need_rebuild(pid_adj_fingerprint)

        if first_time or period_hit or adj_changed:
            _alog("[GW] rebuild trigger", {
                "snapshot": snapshot_idx, "first": first_time, "period_hit": period_hit, "adj_changed": adj_changed
            })
            _GCACHE.rebuild(
                G_sat_isls=G_sat_isls,
                sat_gid=sat_gid,
                gid_neighbors=gid_neighbors,
                edge_cost_func=lambda u, v, data: float(data.get("geo_len_m", 1.0))
            )
            _GCACHE.commit(pid_adj_fingerprint)
        else:
            _alog("[GW] rebuild skip", {
                "snapshot": snapshot_idx, "version": _GCACHE.published_version, "adj_changed": False
            })

        G_constrained = build_gid_constrained_sat_graph(G_sat_isls, sat_gid, _GCACHE, _ROUTER)
        # [SIGNALING_HOOK 3: Topology change detection]
        try:
            snapshot = getattr(_ROUTER, "_snapshot_index", 0)
            sim_time_ms = snapshot * getattr(_ROUTER, "_snapshot_ms", 100)
            isl_now, gsl_now = set(), set()
            for (u, v, d) in G_constrained.edges(data=True):
                et = d.get("type")
                a, b = (u, v) if u <= v else (v, u)
                if et == "isl":
                    isl_now.add((a, b))
                elif et == "gsl":
                    gsl_now.add((a, b))
            delta_isl = 0; delta_gsl = 0
            if hasattr(_ROUTER, "_prev_isl_edges"):
                isl_prev = _ROUTER._prev_isl_edges
                delta_isl = len(isl_now - isl_prev) - len(isl_prev - isl_now)
            if hasattr(_ROUTER, "_prev_gsl_edges"):
                gsl_prev = _ROUTER._prev_gsl_edges
                delta_gsl = len(gsl_now - gsl_prev) - len(gsl_prev - gsl_now)
            if (not hasattr(_ROUTER, "_prev_isl_edges")) or isl_now != getattr(_ROUTER, "_prev_isl_edges") \
               or (not hasattr(_ROUTER, "_prev_gsl_edges")) or gsl_now != getattr(_ROUTER, "_prev_gsl_edges"):
                _get_process_local_stats().record_topology_change(snapshot, sim_time_ms,
                                                        delta_isl=delta_isl, delta_gsl=delta_gsl)
            _ROUTER._prev_isl_edges = isl_now
            _ROUTER._prev_gsl_edges = gsl_now
        except Exception:
            pass
        # [END HOOK 3]
        _alog("[SP] constrained_graph |V|={} |E|={}".format(G_constrained.number_of_nodes(), G_constrained.number_of_edges()), {})


        # (4) Hypatia 最短路
        _alog("[SP] calling calculate_fstate_shortest_path_without_gs_relaying on constrained graph", payload)
        _alog(f"[SP] constrained_graph |V|={G_constrained.number_of_nodes()} |E|={G_constrained.number_of_edges()}", payload)
        
        # 調試：檢查原始的 ground_station_satellites_in_range 格式
        raw_gs_range = payload.get("ground_station_satellites_in_range")
        num_sats = len(payload["satellites"]) if not isinstance(payload["satellites"], int) else payload["satellites"]
        num_gs = len(payload["ground_stations"]) if not isinstance(payload["ground_stations"], int) else payload["ground_stations"]
        
        _alog(f"[DEBUG] num_sats={num_sats}, num_gs={num_gs}", payload)
        if isinstance(raw_gs_range, dict):
            sample_keys = list(raw_gs_range.keys())[:5]
            _alog(f"[DEBUG] raw_gs_range type=dict, sample_keys={sample_keys}, total_keys={len(raw_gs_range)}", payload)
        else:
            _alog(f"[DEBUG] raw_gs_range type={type(raw_gs_range)}", payload)
        
        gs_range_norm = _normalize_gs_range_candidates(
            raw_gs_range,
            payload["satellites"],
            payload["ground_stations"],
        )
        
        gs_range_norm_full = {i: list(gs_range_norm.get(i, [])) for i in range(num_gs)}
        
        try:
            empty_keys = sum(1 for k,v in gs_range_norm_full.items() if not v)
            non_empty_sample = {k: len(v) for k, v in list(gs_range_norm_full.items())[:10] if v}
            _alog(f"[SP] gs_range_norm_full total_keys={len(gs_range_norm_full)} "
                  f"empty_keys={empty_keys} non_empty_sample={non_empty_sample}", payload)
        except Exception as e:
            _alog(f"[DEBUG] Error in gs_range logging: {e}", payload)
        
        # Convert list_gsl_interfaces_info to the expected format
        # gid_to_sat_gsl_if_idx should be a list where gid_to_sat_gsl_if_idx[gid] = GSL interface index
        list_gsl_info = payload["list_gsl_interfaces_info"]
        if isinstance(list_gsl_info, list):
            # Simple case: assume one GSL interface per ground station (index 0)
            gid_to_sat_gsl_if_idx = [0] * num_gs
        elif isinstance(list_gsl_info, dict):
            # Convert dict to list format
            gid_to_sat_gsl_if_idx = [list_gsl_info.get(i, 0) for i in range(num_gs)]
        else:
            # Fallback: assume one GSL interface per ground station
            gid_to_sat_gsl_if_idx = [0] * num_gs
        
        _alog(f"[DEBUG] gid_to_sat_gsl_if_idx: type={type(gid_to_sat_gsl_if_idx)}, len={len(gid_to_sat_gsl_if_idx)}, sample={gid_to_sat_gsl_if_idx[:5]}", payload)

        prev_for_sp = None

        fstate = calculate_fstate_shortest_path_without_gs_relaying(
                payload["output_dynamic_state_dir"],
                payload["time_since_epoch_ns"],
                len(payload["satellites"]),                         # num_satellites
                len(payload["ground_stations"]),                    # num_ground_stations
                G_constrained,                                      # sat_net_graph_only_satellites_with_isls
                payload["num_isls_per_sat"],                        # num_isls_per_sat
                gid_to_sat_gsl_if_idx,                              # gid_to_sat_gsl_if_idx (converted to list)
                gs_range_norm_full,                                 # ground_station_satellites_in_range_candidates
                payload["sat_neighbor_to_if"],                      # sat_neighbor_to_if
                prev_for_sp,                                        # prev_fstate
                payload.get("enable_verbose_logs", False)           # enable_verbose_logs
        )
        # [SIGNALING_HOOK 4: FIB diff / routing update]
        try:
            snapshot = getattr(_ROUTER, "_snapshot_index", 0)
            sim_time_ms = snapshot * getattr(_ROUTER, "_snapshot_ms", 100)
            # 以「節點→下一跳」的簡化 map 來比較（視你的 fstate 結構調整）
            current = {}
            for (u, dst), triple in fstate.items():
                # 這裡選用 (u,dst)->next_hop 的顆粒度；若你想比 per-node 的 default nexthop，也可改寫
                next_hop = triple[0]
                current[(u, dst)] = int(next_hop)
            total = len(current)
            changed = 0
            if hasattr(_ROUTER, "_prev_fstate_simple") and _ROUTER._prev_fstate_simple:
                prev = _ROUTER._prev_fstate_simple
                keys = set(prev.keys()) | set(current.keys())
                for k in keys:
                    if prev.get(k) != current.get(k):
                        changed += 1
                if changed > 0:
                    _get_process_local_stats().record_routing_update(snapshot, sim_time_ms,
                                                           changed_entries=changed,
                                                           total_entries=total)
            else:
                if total > 0:
                    _get_process_local_stats().record_routing_update(snapshot, sim_time_ms,
                                                           changed_entries=total,
                                                           total_entries=total)
            _ROUTER._prev_fstate_simple = current
        except Exception:
            pass
        # [END HOOK 4]
        _alog("[SP] done; fstate ready", payload)
        
        # 添加 Terminal 統計輸出
        if payload.get("enable_verbose_logs", False):
            stats_summary = _get_process_local_stats().get_stats_summary()
            print(f"  > [SIGNALING] 累計統計: {stats_summary['total_events']} 事件, {stats_summary['total_bytes']} 字節")
        
        # Process-local 輸出：使用臨時文件，帶進程/線程ID
        thread_id = threading.get_ident()
        pid = os.getpid()
        
        # 統一輸出統計文件到 analytic_result 目錄
        # 從 ROUTER 讀取網格大小（init() 時已正確設定）
        stats_output_dir = "analytic_result"
        os.makedirs(stats_output_dir, exist_ok=True)
        grid_size = _ROUTER.grid_deg
        
        # 臨時文件：用於收集各進程的統計數據
        temp_dir = os.path.join(stats_output_dir, "temp_grhr")
        os.makedirs(temp_dir, exist_ok=True)
        stats_file = os.path.join(temp_dir, f"grhr_stats_pid{pid}_tid{thread_id}.json")
        
        try:
            
            # 保存詳細統計到 JSON 文件
            detailed_stats = {
                "algorithm": "algorithm_hierarchical_virtual_gid",
                "algorithm_display_name": f"Hierarchical GID ({grid_size}°)",
                "grid_deg": grid_size,
                "timestamp": _dt.datetime.now().isoformat(),
                "summary": _get_process_local_stats().get_stats_summary(),
                "timeline": [
                    {
                        "snapshot": row.snapshot,
                        "time_ms": row.sim_time_ms,
                        "event": row.event,
                        "count": row.count,
                        "bytes": row.bytes,
                        "detail": row.detail
                    }
                    for row in _get_process_local_stats().timeline
                ]
            }
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(detailed_stats, f, indent=2, ensure_ascii=False)
                
            _alog(f"[STATS] Saved signaling stats to {stats_file}", payload)
        except Exception as e:
            _alog(f"[STATS-ERROR] Failed to save stats: {e}", payload)
        
        return {"ok": True, "fstate": fstate}

    # ---------- 逐跳（stitch） ----------
    _alog("[STITCH] running route_all_gs_pairs()", payload)
    route_all_gs_pairs(
        _ROUTER,
        _GCACHE,
        _SSSP,
        payload["sat_ids"],
        payload["sat_nadir_latlon"],
        payload.get("sat_pos_xy", {}),
        payload["G_sat_isls"],
        payload.get("sat_neighbor_to_if_map") or payload.get("sat_neighbor_to_if"),
        payload["gs_pairs"],
        payload["fstate"],
    )
    _alog("[STITCH] done", payload)
    
    # 添加 Terminal 統計輸出
    if payload.get("enable_verbose_logs", False):
        stats_summary = _get_process_local_stats().get_stats_summary()
        print(f"  > [SIGNALING] 累計統計: {stats_summary['total_events']} 事件, {stats_summary['total_bytes']} 字節")
    
    # Process-local 輸出：使用臨時文件，帶進程/線程ID
    thread_id = threading.get_ident()
    pid = os.getpid()
    
    # 統一輸出統計文件到 analytic_result 目錄
    # 從 ROUTER 讀取網格大小（init() 時已正確設定）
    stats_output_dir = "analytic_result"
    os.makedirs(stats_output_dir, exist_ok=True)
    grid_size = _ROUTER.grid_deg
    
    # 臨時文件：用於收集各進程的統計數據
    temp_dir = os.path.join(stats_output_dir, "temp_grhr")
    os.makedirs(temp_dir, exist_ok=True)
    stats_file = os.path.join(temp_dir, f"grhr_stats_pid{pid}_tid{thread_id}.json")
    
    try:
        
        # 保存詳細統計到 JSON 文件
        detailed_stats = {
            "algorithm": "algorithm_hierarchical_virtual_gid",
            "algorithm_display_name": f"Hierarchical GID ({grid_size}°)",
            "grid_deg": grid_size,
            "timestamp": _dt.datetime.now().isoformat(),
            "summary": _get_process_local_stats().get_stats_summary(),
            "timeline": [
                {
                    "snapshot": row.snapshot,
                    "time_ms": row.sim_time_ms,
                    "event": row.event,
                    "count": row.count,
                    "bytes": row.bytes,
                    "detail": row.detail
                }
                for row in _get_process_local_stats().timeline
            ]
        }
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_stats, f, indent=2, ensure_ascii=False)
            
        _alog(f"[STATS] Saved signaling stats to {stats_file}", payload)
    except Exception as e:
        _alog(f"[STATS-ERROR] Failed to save stats: {e}", payload)
    
    return {"ok": True}

def _normalize_gs_range_candidates(raw_map, satellites, ground_stations):
    """
    規範化成 {0..(num_gs-1): [sat_id,...]}。
    支援：
      - key 是 0-based gid（0..num_gs-1）
      - key 是全域 node id（num_sats..num_sats+num_gs-1）
      - raw_map 是 list/tuple，長度 = num_gs
    值若是 set/tuple 會轉 list。
    """
    num_sats = len(satellites) if not isinstance(satellites, int) else satellites
    num_gs   = len(ground_stations) if not isinstance(ground_stations, int) else ground_stations

    # 預先建好完整 0..num_gs-1 的鍵，避免 KeyError
    out = {i: [] for i in range(num_gs)}

    if raw_map is None:
        return out

    # Case 1: list/tuple（索引就是 0-based gid）
    if isinstance(raw_map, (list, tuple)):
        for gid0 in range(min(len(raw_map), num_gs)):
            vals = raw_map[gid0]
            out[gid0] = list(vals) if not isinstance(vals, list) else vals
        return out

    # Case 2: dict
    if isinstance(raw_map, dict) and raw_map:
        ks = list(raw_map.keys())
        
        if not ks:
            return out

        # 2a) 已是 0-based gid (0..num_gs-1)
        if all(isinstance(k, int) and 0 <= k < num_gs for k in ks):
            for gid0 in range(num_gs):
                vals = raw_map.get(gid0, [])
                out[gid0] = list(vals) if not isinstance(vals, list) else vals
            return out

        # 2b) 全域 node id：num_sats..num_sats+num_gs-1 (例如: 625-724 for GS)
        if all(isinstance(k, int) and num_sats <= k < num_sats + num_gs for k in ks):
            for gnode, vals in raw_map.items():
                gid0 = gnode - num_sats  # 625 -> 0, 626 -> 1, ..., 724 -> 99
                if 0 <= gid0 < num_gs:
                    out[gid0] = list(vals) if not isinstance(vals, list) else vals
            return out
        
        # 2c) 混合情況或部分符合：嘗試智能轉換
        for key, vals in raw_map.items():
            if not isinstance(key, int):
                continue
            
            # 如果 key 在 0-based 範圍內，直接使用
            if 0 <= key < num_gs:
                out[key] = list(vals) if not isinstance(vals, list) else vals
            # 如果 key 在全域 node ID 範圍內，轉換
            elif num_sats <= key < num_sats + num_gs:
                gid0 = key - num_sats
                out[gid0] = list(vals) if not isinstance(vals, list) else vals

    # 其它未知型態：回預設 out（全鍵存在，但皆為空）
    return out

# 常見別名（有些執行器會找不同名字）
def route_snapshot(payload: dict):
    return step(payload)

def run(payload: dict):
    return step(payload)

def run_algorithm(payload: dict):
    return step(payload)

def get_signaling_stats():
    """獲取控制信令統計數據"""
    return _get_process_local_stats().get_stats()

def save_signaling_stats(filepath):
    """保存控制信令統計數據到文件"""
    _get_process_local_stats().save_to_file(filepath)

# ===== Hypatia 系統適配器函數 =====
def algorithm_hierarchical_virtual_gid(
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
    sat_lat_lon=None,
    use_region_grouping=False,
    epoch=None,
    time_step_ns=None
):
    """
    Hypatia 系統適配器：直接使用 main_25x25_fast.py 已計算好的數據
    """
    global _ROUTER, _GCACHE, _SSSP
    
    # 初始化（如果還沒初始化）
    if _ROUTER is None or _GCACHE is None or _SSSP is None:
        init()
    
    # 準備必要欄位
    num_sats = len(satellites) if not isinstance(satellites, int) else satellites
    sat_ids = list(range(num_sats))

    # ★ 權重歸零，避免跨 pair 累積
    reset_edge_weights_to_geo(sat_net_graph_only_satellites_with_isls)

    # ★ 智能提取衛星位置數據
    def _best_effort_sat_latlon(
        sat_lat_lon_in,
        satellites,
        G_sat_isls: nx.Graph
    ) -> Dict[int, Tuple[float, float]]:
        """
        優先使用呼叫者提供的 sat_lat_lon；
        否則嘗試從圖節點屬性或 satellites 物件上擷取 (lat, lon)。
        回傳 {sat_id: (lat, lon)}；擷取不到則回 {}。
        """
        # 1) 呼叫者已提供
        if isinstance(sat_lat_lon_in, dict) and sat_lat_lon_in:
            return sat_lat_lon_in
        
        out = {}

        # 2) 從圖節點屬性撈
        cand_keys = [
            ("nadir_lat_deg", "nadir_lon_deg"),
            ("lat", "lon"),
            ("nadir_lat", "nadir_lon"),
            ("lat_deg", "lon_deg"),
            ("latitude", "longitude"),
        ]

        try:
            for nid, data in G_sat_isls.nodes(data=True):
                lat = lon = None
                for klat, klon in cand_keys:
                    if klat in data and klon in data:
                        lat, lon = data[klat], data[klon]
                        break
                if lat is not None and lon is not None:
                    out[nid] = (float(lat), float(lon))
        except Exception:
            pass

        # 3) satellites 物件撈（如果 out 不完整）
        try:
            # 可迭代時才逐一嘗試
            for sid, sat in enumerate(satellites):
                if sid in out:
                    continue
                lat = lon = None
                for klat, klon in cand_keys:
                    lat = getattr(sat, klat, None)
                    lon = getattr(sat, klon, None)
                    if lat is not None and lon is not None:
                        out[sid] = (float(lat), float(lon))
                        break
        except TypeError:
            # satellites 不是 iterable（可能是一個數字），略過
            pass
        except Exception:
            pass

        # 4) 絕不塞 (0,0)；允許 out 是部分鍵
        return out

    sat_nadir_latlon = sat_lat_lon if isinstance(sat_lat_lon, dict) and sat_lat_lon else None
    if not sat_nadir_latlon:
        sat_nadir_latlon = _best_effort_sat_latlon(
            sat_lat_lon, satellites, sat_net_graph_only_satellites_with_isls
        )

    if not sat_nadir_latlon:
        _alog("[WARNING] No satellite position data available from caller/graph/satellite objects; continue with empty mapping.",
            {"output_dynamic_state_dir": output_dynamic_state_dir})

    payload = {
        "output_dynamic_state_dir": output_dynamic_state_dir,
        "time_since_epoch_ns": time_since_epoch_ns,
        "satellites": satellites,
        "ground_stations": ground_stations,
        "G_sat_isls": sat_net_graph_only_satellites_with_isls,
        "ground_station_satellites_in_range": ground_station_satellites_in_range,
        "num_isls_per_sat": num_isls_per_sat,
        "sat_neighbor_to_if": sat_neighbor_to_if,
        "list_gsl_interfaces_info": list_gsl_interfaces_info,
        "prev_output": prev_output,
        "enable_verbose_logs": enable_verbose_logs,

        # 分群輸入
        "sat_ids": sat_ids,
        "sat_nadir_latlon": sat_nadir_latlon,

        # 逐跳模式用不到，但保留
        "sat_pos_xy": {},
        "gs_pairs": [],
        "fstate": {},
    }

    _alog("[SP] delegating to step(payload) with constrained PID routing",
        {"has_sat_nadir_latlon": bool(sat_nadir_latlon)})
    ret = step(payload)
    return ret if isinstance(ret, dict) else {"fstate": {}}

