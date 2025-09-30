"""
Virtual PID‑based hierarchical router for LEO constellations.

This module defines a ``VirtualPIDRouter`` class implementing a virtual master
concept inspired by the LoHi (Load‑aware Hierarchical Information‑centric) routing
architecture.  Instead of electing a single physical satellite as the master for
each geographic group, we assign a *logical* identifier – a PID – to each
geographic region.  Each PID persists over time and is temporarily
*represented* by an in‑orbit satellite (an agent).  When an agent leaves the
region, another satellite takes over without changing the PID.  Inter‑group
paths are computed on a PID‑level graph, while intra‑group traffic is routed
through the current agent.  This design minimizes control‑plane churn and
better captures the spirit of LoHi, which decouples logical routing links from
transient physical nodes【320652751058504†L150-L176】.


Example usage::

    router = VirtualPIDRouter(grid_deg=10)
    router.get_sat_latlon = my_sat_latlon_fn
    router.get_sat_neighbors = my_neighbors_fn
    router.update_pid_members_and_agents(t_now, list_of_sat_ids)
    next_hop = router.next_hop_sat(t_now, src_sat_id, dest_pid)

This class does *not* rely on any external dependencies beyond ``math`` and
Python’s built‑in types.  It can be integrated into the existing
satgenpy/hypatia codebase by replacing the fixed master selection and routing
logic with PID‑level decisions.
"""

from typing import Dict, List, Optional, Set, Tuple
import math
import os
import pickle
import ephem
from datetime import datetime, timezone
from astropy.time import Time
import numpy as np
import networkx as nx

# 簡化版本：移除詳細調試日志以提高性能
class GatewayCache:
    """
    Cache of best gateway satellites between neighboring PIDs.
    每對 (pidA, pidB) 保留多個候選 gateway: [(satA, satB, cost), ...]，按 cost 排序。
    """

    def __init__(self, graph, router, sat_ids, pid_of_sat_fn, weight: str = "weight"):
        """
        graph: nx.Graph 衛星圖 (satellite-only with ISLs)
        router: VirtualPIDRouter instance
        sat_ids: 所有衛星的 ID list
        weight: edge 屬性，用於計算 cost
        """
        self.gateways: Dict[Tuple[int, int], List[Tuple[int, int, float]]] = {}
       
        # 預先映射：sat → pid
        sat_to_pid: Dict[int, Optional[int]] = {}
        for sat in sat_ids:
            sat_to_pid[sat] = pid_of_sat_fn(sat)

        # 掃描所有 edge，看是不是跨 PID
        for u, v, data in graph.edges(data=True):
            pid_u, pid_v = sat_to_pid[u], sat_to_pid[v]
            if pid_u is None or pid_v is None:
                continue
            if pid_u == pid_v:
                continue

            # 確認兩 PID 是否相鄰 (根據 router.pid_neighbors)
            if pid_v not in router.pid_neighbors.get(pid_u, []):
                continue

            cost = data.get(weight, 1.0)

            # 添加到候選列表 u→v
            key = (pid_u, pid_v)
            if key not in self.gateways:
                self.gateways[key] = []
            self.gateways[key].append((u, v, cost))

            # 添加到候選列表 v→u
            key = (pid_v, pid_u)
            if key not in self.gateways:
                self.gateways[key] = []
            self.gateways[key].append((v, u, cost))

        # 對每個方向的候選gateway按cost排序
        for key in self.gateways:
            self.gateways[key].sort(key=lambda x: x[2])

    def get_gateways(self, pidA: int, pidB: int) -> List[Tuple[int, int, float]]:
        """取得從 pidA 到 pidB 的候選 gateway list，按cost排序"""
        return self.gateways.get((pidA, pidB), [])

def _to_ephem_date(epoch_obj):
    # 已經是 ephem.Date
    if isinstance(epoch_obj, ephem.Date):
        return epoch_obj

    # Astropy Time
    try:
        if isinstance(epoch_obj, Time):
            t_utc = epoch_obj.utc       # 轉成 UTC
            dt = t_utc.to_datetime()    # 不加 timezone，避免 ScaleValueError
            return ephem.Date(dt)
    except ImportError:
        pass

    # 直接丟給 ephem.Date (支援 datetime/字串)
    try:
        return ephem.Date(epoch_obj)
    except Exception:
        pass

    # numpy.datetime64
    try:
        if isinstance(epoch_obj, np.datetime64):
            ts = (epoch_obj - np.datetime64('1970-01-01T00:00:00Z')) / np.timedelta64(1, 's')
            return ephem.Date(datetime.fromtimestamp(float(ts), tz=timezone.utc))
    except Exception:
        pass

    # 字串 (ISO 格式)
    if isinstance(epoch_obj, str):
        try:
            return ephem.Date(epoch_obj)
        except Exception:
            s = epoch_obj.strip().replace('Z', '+00:00')
            dt = datetime.fromisoformat(s)
            return ephem.Date(dt)

    # 數字 (可能是秒/ms/ns)
    if isinstance(epoch_obj, (int, float)):
        x = float(epoch_obj)
        if x > 1e12:     # ns
            x /= 1e9
        elif x > 1e10:   # ms
            x /= 1e3
        return ephem.Date(datetime.fromtimestamp(x, tz=timezone.utc))

    raise ValueError(f"Unsupported epoch type for ephem.Date: {type(epoch_obj)}")


class VirtualPIDRouter:
    """Virtual PID-based router for hierarchical LEO routing."""

    def __init__(self, grid_deg: int = 15, lon_min: int = -180, lon_max: int = 180,
                 lat_min: int = -90, lat_max: int = 90, allow_diagonal_neighbor: bool = False) -> None:
        self.grid_deg = grid_deg
        self.lon_min, self.lon_max = lon_min, lon_max
        self.lat_min, self.lat_max = lat_min, lat_max
        self.allow_diag = allow_diagonal_neighbor

        # Static
        self.pids: List[Tuple[int, int]] = []
        self.pid_index: Dict[Tuple[int, int], int] = {}
        self.pid_neighbors: Dict[int, Set[int]] = {}

        # Dynamic
        self.pid_agent_sat: Dict[int, Optional[int]] = {}
        self.pid_members: Dict[int, Set[int]] = {}
        self._prev_pid_agent_sat: Dict[int, Optional[int]] = {}
        self._hop_cache: Dict[Tuple[int, int, int], Optional[int]] = {}  # (t, src, dst_pid)

        # External hooks
        self.get_sat_latlon = None
        self.get_sat_neighbors = None

        self._build_static_pid_grid()

    def _build_static_pid_grid(self):
        lat_bins = list(range(self.lat_min, self.lat_max, self.grid_deg))
        lon_bins = list(range(self.lon_min, self.lon_max, self.grid_deg))
        for i, lat in enumerate(lat_bins):
            for j, lon in enumerate(lon_bins):
                pid = (i, j)
                idx = len(self.pids)
                self.pids.append(pid)
                self.pid_index[pid] = idx
        for (i, j), u in self.pid_index.items():
            nbrs = []
            dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if self.allow_diag:
                dirs += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            for di, dj in dirs:
                ii, jj = i + di, j + dj
                if (ii, jj) in self.pid_index:
                    nbrs.append(self.pid_index[(ii, jj)])
            self.pid_neighbors[u] = set(nbrs)

    def latlon_to_pid(self, lat: float, lon: float) -> Optional[int]:
        if not (self.lat_min <= lat < self.lat_max and self.lon_min <= lon < self.lon_max):
            return None
        gi = int((lat - self.lat_min) // self.grid_deg)
        gj = int((lon - self.lon_min) // self.grid_deg)
        return self.pid_index.get((gi, gj))

    def update_pid_members_and_agents(self, t: float, sat_ids: List[int]) -> None:
        self._prev_pid_agent_sat = dict(self.pid_agent_sat)
        self._hop_cache.clear()
        self.pid_members = {u: set() for u in range(len(self.pids))}
        for s in sat_ids:
            if self.get_sat_latlon is None:
                continue
            lat, lon = self.get_sat_latlon(s, t)
            u = self.latlon_to_pid(lat, lon)
            if u is not None:
                self.pid_members[u].add(s)
        new_agents = {}
        for u in range(len(self.pids)):
            members = self.pid_members[u]
            if members:
                new_agents[u] = min(members)
            else:
                prev = self._prev_pid_agent_sat.get(u)
                new_agents[u] = prev if prev is not None else None
        self.pid_agent_sat = new_agents

    def active_pid_edges(self, t: float) -> Dict[int, Set[int]]:
        edges = {u: set() for u in range(len(self.pids))}
        for u in range(len(self.pids)):
            su = self.pid_agent_sat.get(u)
            if su is None: continue
            for v in self.pid_neighbors[u]:
                sv = self.pid_agent_sat.get(v)
                if sv is None: continue
                if sv in self.get_sat_neighbors(su, t):
                    edges[u].add(v)
        return edges

    def build_pid_next_table(self, t: int) -> Dict[int, Dict[int, int]]:
        active = self.active_pid_edges(t)
        pid_next = {u: {} for u in range(len(self.pids))}
        from collections import deque
        for src in range(len(self.pids)):
            prev = {src: -1}
            q = deque([src])
            while q:
                u = q.popleft()
                for v in active[u]:
                    if v in prev: continue
                    prev[v] = u
                    q.append(v)
            for dst in range(len(self.pids)):
                if dst == src or dst not in prev: continue
                cur = dst
                while prev[cur] != src:
                    cur = prev[cur]
                pid_next[src][dst] = cur
        return pid_next

    def _first_hop_towards(self, src: int, dst: int, t: float) -> Optional[int]:
        nbrs = self.get_sat_neighbors(src, t)
        if dst in nbrs:
            return dst
        dlat, dlon = self.get_sat_latlon(dst, t)
        best, best_d = None, float("inf")
        for nb in nbrs:
            nlat, nlon = self.get_sat_latlon(nb, t)
            d = self._haversine_deg(nlat, nlon, dlat, dlon)
            if d < best_d:
                best, best_d = nb, d
        return best

    @staticmethod
    def _haversine_deg(lat1, lon1, lat2, lon2):
        R = 6371.0
        def rad(x): return x * math.pi / 180.0
        dlat, dlon = rad(lat2 - lat1), rad(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(rad(lat1))*math.cos(rad(lat2))*math.sin(dlon/2)**2
        return 2*R*math.asin(math.sqrt(a))

    def next_hop_sat(self, t: int, src: int, dst_pid: int, pid_next=None, dst_sat=None) -> Optional[int]:
        """
        改進版路由邏輯：
        1. 同PID內：直接使用地理最近鄰路由，不強制經過agent
        2. 跨PID：優先使用早退機制（相鄰PID直接gateway跳轉）
        3. 多跳骨幹：通過agent規劃
        """
        k = (int(t), src, dst_pid, dst_sat)
        if k in self._hop_cache:
            return self._hop_cache[k]
            
        lat, lon = self.get_sat_latlon(src, t)
        here_pid = self.latlon_to_pid(lat, lon)
        if here_pid is None: 
            return None
        
        # 🎯 同PID內：直接使用地理最優路由，不經過agent
        if here_pid == dst_pid:
            if dst_sat is not None:
                # 有明確目標衛星：直接地理路由
                nh = self._first_hop_towards(src, dst_sat, t)
                self._hop_cache[k] = nh
                return nh
            else:
                # 沒有目標衛星：已到達目的PID
                self._hop_cache[k] = None
                return None
        
        # 🎯 跨PID：使用PID-level路由表找下一個PID
        next_pid = pid_next.get(here_pid, {}).get(dst_pid, None) if pid_next else None
        if next_pid is None:
            return None
            
        # 獲取下一個PID的agent作為目標
        agent_next = self.pid_agent_sat.get(next_pid)
        if agent_next is None:
            return None
            
        # 🎯 關鍵改進：從當前位置直接路由到下一個PID的agent
        # 不再強制先到當前PID的agent
        nh = self._first_hop_towards(src, agent_next, t)
        self._hop_cache[k] = nh
        return nh


# ============================================================
# Algorithm entry
# ============================================================
def algorithm_hierarchical_virtual_pid(
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
    enable_verbose_logs=True,
    sat_lat_lon=None,
    use_region_grouping=False,
    epoch=None,
    time_step_ns=None
):
    stitch_skip_count = 0
    stitch_skip_samples = []  # 收集少量樣本 (u,v,dst)  
    
    if time_step_ns is None or epoch is None:
        raise ValueError("epoch and time_step_ns are required")

    step = time_since_epoch_ns // time_step_ns
    sat_ids = list(range(len(satellites)))
    epoch_ephem = _to_ephem_date(epoch)

    # 一次性計算所有 sat 的 (lat,lon)
    ns_per_day = 86_400 * 1_000_000_000
    def get_latlon_by_ephem(sat_id, t):
        dt_days = (t * time_step_ns) / ns_per_day
        sat_obj = satellites[sat_id]
        sat_obj.compute(epoch_ephem + dt_days)
        lat = float(sat_obj.sublat) * 180.0 / math.pi
        lon = float(sat_obj.sublong) * 180.0 / math.pi
        if lon >= 180: lon -= 360
        if lon < -180: lon += 360
        return (lat, lon)
    latlon_cache = [get_latlon_by_ephem(sid, step) for sid in sat_ids]

    router = VirtualPIDRouter(grid_deg=15, allow_diagonal_neighbor=False)
    router.get_sat_latlon = lambda sid, _t: latlon_cache[sid]
    router.get_sat_neighbors = lambda sid, _t: list(sat_net_graph_only_satellites_with_isls.neighbors(sid))
    router.update_pid_members_and_agents(step, sat_ids)
    
    # # 🔧 修復：建構PID層級路由表
    # pid_next_table = router.build_pid_next_table(step)
    
    pid_to_sats, pid_to_agent = router.pid_members, router.pid_agent_sat
    sat_neighbor_to_if_map = sat_neighbor_to_if

    # 展開成 fstate - 衛星間路由
    fstate = {}

    # 添加地面站路由支持
    num_satellites = len(sat_ids)
    num_ground_stations = len(ground_stations)

    def gs_idx_to_node_id(gs_idx: int) -> int:
        """將地面站索引(0-based)轉換為全域節點ID"""
        return num_satellites + gs_idx

    def first_reachable_sat(gs_idx: int) -> Optional[int]:
        # ground_station_satellites_in_range[gs_idx] 形式通常是 [(dist_m, sat_id), ...]
        if gs_idx < len(ground_station_satellites_in_range):
            lst = ground_station_satellites_in_range[gs_idx]
        else:
            lst = []
        return lst[0][1] if lst else None

    def gsl_if_index_on_sat_for_gs(sat_id: int, gs_idx: int) -> Optional[int]:
        """
        回傳「衛星端」連到該地面站的 GSL 介面索引。 
        規則：ISL 介面先佔用 [0 .. num_isls_per_sat[sat)-1]，
            GSL 介面從 num_isls_per_sat[sat] 起算。
        若同一顆衛星允許多個 GSL 介面，這裡用地面站在可視列表中的次序當偏移（可重現）。
        """
        base = num_isls_per_sat[sat_id]
        if gs_idx < len(ground_station_satellites_in_range):
            lst = ground_station_satellites_in_range[gs_idx]
        else:
            lst = []
        for idx, (_, sid) in enumerate(lst):
            if sid == sat_id:
                return base + idx
        return None  # 找不到代表不在可視列表（理論上不會走到這）

    def pid_of_sat(sat_id: int) -> Optional[int]:
        lat, lon = router.get_sat_latlon(sat_id, step)
        return router.latlon_to_pid(lat, lon)
    
    gcache = GatewayCache(sat_net_graph_only_satellites_with_isls, router, sat_ids, pid_of_sat)

    def stitch_sat_path(path_nodes: List[int], final_dst_gs_id: int):
        nonlocal stitch_skip_count, stitch_skip_samples
        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]; v = path_nodes[i + 1]
            out_if = sat_neighbor_to_if_map.get((u, v))
            in_if  = sat_neighbor_to_if_map.get((v, u))
            if out_if is None or in_if is None:
                stitch_skip_count += 1
                if len(stitch_skip_samples) < 20:
                    stitch_skip_samples.append((u, v, final_dst_gs_id))
                if enable_verbose_logs:
                    print(f"[STITCH-SKIP] missing ifs for edge {u}->{v} toward dst {final_dst_gs_id}")
                continue
            if (u, final_dst_gs_id) not in fstate:
                fstate[(u, final_dst_gs_id)] = (v, out_if, in_if)

    def validate_isl_if_map(
        graph, 
        sat_neighbor_to_if_map: Dict[Tuple[int, int], int],
        enable_verbose_logs: bool = True,
    ) -> None:
        missing_uv = []
        missing_vu = []
        mism_nodes = set()

        # 逐邊檢查：每條 ISL 邊 (u,v) 必須有 (u->v) 與 (v->u) 兩個介面索引
        for u, v in graph.edges():
            has_uv = (u, v) in sat_neighbor_to_if_map
            has_vu = (v, u) in sat_neighbor_to_if_map
            if not has_uv:
                missing_uv.append((u, v))
                mism_nodes.add(u); mism_nodes.add(v)
            if not has_vu:
                missing_vu.append((v, u))
                mism_nodes.add(u); mism_nodes.add(v)

        if enable_verbose_logs:
            if not missing_uv and not missing_vu:
                print("[CHECK] ISL if-map is symmetric for all graph edges.")
            else:
                print(f"[CHECK] ISL if-map inconsistency: {len(missing_uv)} (u->v) missing, {len(missing_vu)} (v->u) missing")
                # 只列出前幾個，避免刷屏
                for i, (u, v) in enumerate(missing_uv[:20]):
                    print(f"  [MISS] out-if missing for edge {u}->{v}")
                for i, (v, u) in enumerate(missing_vu[:20]):
                    print(f"  [MISS] out-if missing for edge {v}->{u}")
                if len(missing_uv) > 20 or len(missing_vu) > 20:
                    print("  ... (truncated)")

        # 額外提醒：哪些節點出現缺口，方便你聚焦
        if mism_nodes and enable_verbose_logs:
            sample = list(mism_nodes)[:20]
            print(f"[CHECK] Nodes involved in if-map gaps (sample): {sample}")
    
    def validate_gateways_bidirectional(
        gcache, 
        sat_neighbor_to_if_map: Dict[Tuple[int, int], int],
        enable_verbose_logs: bool = True
    ) -> None:
        bad = []
        total = 0
        for (pidA, pidB), lst in gcache.gateways.items():
            if not lst: 
                continue
            for (satA, satB, cost) in lst:
                total += 1
                if (satA, satB) not in sat_neighbor_to_if_map or (satB, satA) not in sat_neighbor_to_if_map:
                    bad.append(((pidA, pidB), satA, satB))
        if enable_verbose_logs:
            if not bad:
                print(f"[CHECK] Gateways OK: {total} candidates are all bidirectional in if-map.")
            else:
                print(f"[CHECK] Gateways with missing if(s): {len(bad)} / {total}")
                for rec in bad[:20]:
                    (pidA, pidB), satA, satB = rec
                    has_uv = (satA, satB) in sat_neighbor_to_if_map
                    has_vu = (satB, satA) in sat_neighbor_to_if_map
                    print(f"  [GW-MISS] PID {pidA}->{pidB} gateway {satA}->{satB} "
                        f"uv={'OK' if has_uv else 'MISS'}, vu={'OK' if has_vu else 'MISS'}")
                if len(bad) > 20:
                    print("  ... (truncated)")
    
    # def add_targeted_routing(intermediate_sat: int, final_destination: int, is_gs_destination: bool = False):
    #     """
    #     為中間衛星添加到最終目的地的路由條目。
    #     使用改進的路由邏輯：同PID內直接子圖最短路徑，跨PID使用早退機制。
        
    #     Args:
    #         intermediate_sat: 中間衛星ID
    #         final_destination: 最終目的地ID（衛星或地面站）  
    #         is_gs_destination: 是否為地面站目的地
    #     """
    #     # 🔧 修復：強制為關鍵中間節點添加路由，解決路由鏈中斷問題
    #     # 不再跳過已存在的路由，確保所有關鍵路由被正確設置

    #     intermediate_pid = pid_of_sat(intermediate_sat)
    #     if intermediate_pid is None:
    #         return
        
    #     # 確定目標衛星和PID
    #     if is_gs_destination:
    #         # 地面站：需要通過下行衛星
    #         gs_idx = final_destination - num_satellites
    #         target_sat = first_reachable_sat(gs_idx) 
    #         if target_sat is None:
    #             return
    #     else:
    #         # 衛星目的地
    #         target_sat = final_destination
            
    #     target_pid = pid_of_sat(target_sat)
    #     if target_pid is None:
    #         return
        
    #     try:
    #         # 🎯 使用改進的路由邏輯，傳入目標衛星信息
    #         next_hop = router.next_hop_sat(step, intermediate_sat, target_pid, pid_next_table, target_sat)
    #         if next_hop is None:
    #             return
                
    #         # 獲取interface信息
    #         out_if = sat_neighbor_to_if_map.get((intermediate_sat, next_hop))
    #         in_if = sat_neighbor_to_if_map.get((next_hop, intermediate_sat))
            
    #         if out_if is not None and in_if is not None:
    #             fstate[(intermediate_sat, final_destination)] = (next_hop, out_if, in_if)
                
    #     except Exception:
    #         # 靜默失敗，避免中斷主流程
    #         pass




    # 建 PID-level graph
    pid_graph = nx.Graph()
    for pid, nbrs in router.pid_neighbors.items():
        for n in nbrs:
            pid_graph.add_edge(pid, n)

    validate_isl_if_map(sat_net_graph_only_satellites_with_isls, sat_neighbor_to_if_map, enable_verbose_logs)
    validate_gateways_bidirectional(gcache, sat_neighbor_to_if_map, enable_verbose_logs)

    pid_subgraphs = {}
    pid_sat_comp = {}  # {pid: {sat: comp_id}}

    for pid, sats in pid_to_sats.items():
        subG = sat_net_graph_only_satellites_with_isls.subgraph(sats).copy()
        pid_subgraphs[pid] = subG
        pid_sat_comp[pid] = {}
        for cid, comp_nodes in enumerate(nx.connected_components(subG)):
            for s in comp_nodes:
                pid_sat_comp[pid][s] = cid

    # # 統一的 GS×GS 路由處理
    # intermediate_sats_per_downlink = {}  # downlink_sat -> set of intermediate satellites
    # intermediate_sats_per_gs = {}  # dst_gs_node_id -> set of intermediate satellites (新增)
    
    for src_gid in range(num_ground_stations):
        for dst_gid in range(num_ground_stations):
            if src_gid == dst_gid:
                continue

            # 使用統一的輔助函數轉換為全域節點ID
            src_gs_node_id = gs_idx_to_node_id(src_gid)
            dst_gs_node_id = gs_idx_to_node_id(dst_gid)
            
            # 修正：使用正確的參數 - helper函數需要的是gs_idx索引，不是全域ID
            src_uplink_sat = first_reachable_sat(src_gid)
            dst_downlink_sat = first_reachable_sat(dst_gid)
            if src_uplink_sat is None or dst_downlink_sat is None:
                continue

            # 記錄此路徑會經過的中間衛星
            path_intermediate_sats = set()

            # (1) GS→Sat 上行連接
            gs_out_if = 0
            sat_in_if = num_isls_per_sat[src_uplink_sat]
            fstate[(src_gs_node_id, dst_gs_node_id)] = (src_uplink_sat, gs_out_if, sat_in_if)

            src_pid = pid_of_sat(src_uplink_sat)
            dst_pid = pid_of_sat(dst_downlink_sat)
            
            if src_pid is None or dst_pid is None:
                continue

            # (2) 🎯 重新設計的Sat↔Sat路由邏輯
            try:
                if src_pid == dst_pid:
                    # 同PID內：直接使用子圖最短路徑
                    pid_subgraph = sat_net_graph_only_satellites_with_isls.subgraph(pid_to_sats[src_pid])
                    path = nx.shortest_path(
                        pid_subgraph,
                        src_uplink_sat,
                        dst_downlink_sat,
                        weight="weight"
                    )
                    stitch_sat_path(path, dst_gs_node_id)
                    path_intermediate_sats.update(path[1:-1])
                elif pid_graph.has_edge(src_pid, dst_pid):
                    # 相鄰 PID：與骨幹分支相同的 gateway 流程（先驗證 if），避免 global_shortest_path 混入無 if 的邊
                    pid_path = [src_pid, dst_pid]
                    current_sat = src_uplink_sat
                    current_pid = src_pid

                    for next_pid in pid_path[1:]:
                        candidates = gcache.get_gateways(current_pid, next_pid)
                        gw_used = None

                        # 先挑一個確定雙向 if 都存在的 gateway
                        for satA, satB, gw_cost in candidates:
                            out_if = sat_neighbor_to_if_map.get((satA, satB))
                            in_if  = sat_neighbor_to_if_map.get((satB, satA))
                            if out_if is not None and in_if is not None:
                                gw_used = (satA, satB, gw_cost)
                                break

                        # Fallback：動態掃描可用 gateway
                        if gw_used is None:
                            best = None
                            for u in pid_to_sats[current_pid]:
                                for v in sat_net_graph_only_satellites_with_isls.neighbors(u):
                                    if pid_of_sat(v) != next_pid:
                                        continue
                                    out_if = sat_neighbor_to_if_map.get((u, v))
                                    in_if  = sat_neighbor_to_if_map.get((v, u))
                                    if out_if is None or in_if is None:
                                        continue
                                    cost = sat_net_graph_only_satellites_with_isls[u][v].get("weight", 1.0)
                                    if best is None or cost < best[2]:
                                        best = (u, v, cost)
                            if best is not None:
                                gw_used = best

                        if gw_used is None:
                            # 這個相鄰 PID 邊找不到可用 gateway，放棄這對
                            break

                        satA, satB, gw_cost = gw_used

                        # (1) 來源 PID 子圖：current_sat → satA
                        if current_sat != satA:
                            src_sub = sat_net_graph_only_satellites_with_isls.subgraph(pid_to_sats[current_pid])
                            try:
                                path1 = nx.shortest_path(src_sub, current_sat, satA, weight="weight")
                                stitch_sat_path(path1, dst_gs_node_id)
                                path_intermediate_sats.update(path1[1:-1])
                            except nx.NetworkXNoPath:
                                if enable_verbose_logs:
                                    print(f"[NOPATH] PID={current_pid} subgraph|V|={src_sub.number_of_nodes()} "
                                        f"no path {current_sat}->{satA} toward dst_gs={dst_gs_node_id}")
                                break
                            path1 = nx.shortest_path(src_sub, current_sat, satA, weight="weight")
                            stitch_sat_path(path1, dst_gs_node_id)
                            path_intermediate_sats.update(path1[1:-1])

                        # (2) Gateway 跨越
                        stitch_sat_path([satA, satB], dst_gs_node_id)

                        # 更新
                        current_sat = satB
                        current_pid = next_pid

                    # (3) 目標 PID 子圖：current_sat → dst_downlink_sat
                    if current_pid == dst_pid and current_sat != dst_downlink_sat:
                        dst_sub = sat_net_graph_only_satellites_with_isls.subgraph(pid_to_sats[dst_pid])
                        try:
                            path3 = nx.shortest_path(dst_sub, current_sat, dst_downlink_sat, weight="weight")
                            stitch_sat_path(path3, dst_gs_node_id)
                            path_intermediate_sats.update(path3[1:-1])
                        except nx.NetworkXNoPath:
                            if enable_verbose_logs:
                                print(f"[NOPATH] PID={dst_pid} subgraph|V|={dst_sub.number_of_nodes()} "
                                    f"no path {current_sat}->{dst_downlink_sat} (dst_gs={dst_gs_node_id})")
                            break
                        if dst_sub.has_node(current_sat) and dst_sub.has_node(dst_downlink_sat):
                            path3 = nx.shortest_path(dst_sub, current_sat, dst_downlink_sat, weight="weight")
                            stitch_sat_path(path3, dst_gs_node_id)
                            path_intermediate_sats.update(path3[1:-1])
                else:
                    # 🎯 多跳骨幹路由：通過agent做規劃 + 邊界gateway轉送
                    pid_path = nx.shortest_path(pid_graph, src_pid, dst_pid)
                    current_sat = src_uplink_sat
                    current_pid = src_pid

                    for next_pid in pid_path[1:]:
                        candidates = gcache.get_gateways(current_pid, next_pid)
                        gw_used = None
                        
                        # 嘗試候選gateway，選擇第一個有可用interface的
                        for satA, satB, gw_cost in candidates:
                            out_if = sat_neighbor_to_if_map.get((satA, satB))
                            in_if = sat_neighbor_to_if_map.get((satB, satA))
                            if out_if is not None and in_if is not None:
                                gw_used = (satA, satB, gw_cost)
                                break
                        
                        # Fallback: 動態尋找可用gateway
                        if gw_used is None:
                            best = None
                            for u in pid_to_sats[current_pid]:
                                for v in sat_net_graph_only_satellites_with_isls.neighbors(u):
                                    if pid_of_sat(v) != next_pid:
                                        continue
                                    out_if = sat_neighbor_to_if_map.get((u, v))
                                    in_if = sat_neighbor_to_if_map.get((v, u))
                                    if out_if is None or in_if is None:
                                        continue
                                    cost = sat_net_graph_only_satellites_with_isls[u][v].get("weight", 1.0)
                                    if best is None or cost < best[2]:
                                        best = (u, v, cost)
                            
                            if best is not None:
                                gw_used = best
                        
                        if gw_used is None:
                            break
                        
                        satA, satB, gw_cost = gw_used

                        # PID內路由到gateway A (如果不是已經在gateway A)
                        if current_sat != satA:
                            # 使用PID內子圖最短路徑到gateway
                            current_pid_subgraph = sat_net_graph_only_satellites_with_isls.subgraph(pid_to_sats[current_pid])
                            path_to_gw = nx.shortest_path(
                                current_pid_subgraph,
                                current_sat,
                                satA,
                                weight="weight"
                            )
                            stitch_sat_path(path_to_gw, dst_gs_node_id)
                            path_intermediate_sats.update(path_to_gw[1:-1])
                        
                        # Gateway跨越
                        stitch_sat_path([satA, satB], dst_gs_node_id)
                        
                        # 更新當前位置到下一個PID
                        current_sat = satB
                        current_pid = next_pid
                    
                    # 最後一段：從最後的gateway B到目標衛星  
                    # current_sat應該已經在dst_pid中了
                    if current_sat != dst_downlink_sat and current_pid == dst_pid:
                        final_pid_subgraph = sat_net_graph_only_satellites_with_isls.subgraph(pid_to_sats[dst_pid])
                        if final_pid_subgraph.has_node(current_sat) and final_pid_subgraph.has_node(dst_downlink_sat):
                            final_path = nx.shortest_path(
                                final_pid_subgraph,
                                current_sat,
                                dst_downlink_sat,
                                weight="weight"
                            )
                            stitch_sat_path(final_path, dst_gs_node_id)
                            path_intermediate_sats.update(final_path[1:-1])

            except nx.NetworkXNoPath:
                continue

            # (3) Sat→GS 下行連接
            sat_out_if = gsl_if_index_on_sat_for_gs(dst_downlink_sat, dst_gid)
            if sat_out_if is None:
                continue
            gs_in_if = 0
            fstate[(dst_downlink_sat, dst_gs_node_id)] = (dst_gs_node_id, sat_out_if, gs_in_if)
            

            # 🎯 關鍵修復：正確記錄中間衛星，包括下行衛星本身
            # 對於其他路徑可能需要通過此下行衛星進行路由
            # all_path_satellites = set(path_intermediate_sats)
            
            
            
            # 🔧 添加下行衛星自身作為潛在的中間衛星
            # 這解決了衛星188既是下行衛星又是中間衛星的角色衝突
            # if dst_downlink_sat <= 624:  # 確認是衛星而不是地面站
            #     all_path_satellites.add(dst_downlink_sat)
            
            # # 記錄此下行衛星的中間衛星集合
            # if dst_downlink_sat not in intermediate_sats_per_downlink:
            #     intermediate_sats_per_downlink[dst_downlink_sat] = set()
            # intermediate_sats_per_downlink[dst_downlink_sat].update(path_intermediate_sats)
            
            # # 同時記錄到地面站的中間衛星（包含下行衛星）
            # if dst_gs_node_id not in intermediate_sats_per_gs:
            #     intermediate_sats_per_gs[dst_gs_node_id] = set()
            # intermediate_sats_per_gs[dst_gs_node_id].update(all_path_satellites)

    # 🎯 全面的路由完整性補充：確保所有路由鏈完整
    
    # # 1. 為所有中間衛星添加到地面站的路由
    # for dst_gs_node_id, intermediate_sats in intermediate_sats_per_gs.items():
    #     if intermediate_sats:
    #         for intermediate_sat in intermediate_sats:
    #             add_targeted_routing(intermediate_sat, dst_gs_node_id, is_gs_destination=True)
    
    # # 2. 為下行衛星的中間衛星補充到下行衛星的路由
    # for downlink_sat, intermediate_sats in intermediate_sats_per_downlink.items():
    #     if intermediate_sats:
    #         for intermediate_sat in intermediate_sats:
    #             if intermediate_sat != downlink_sat:
    #                 add_targeted_routing(intermediate_sat, downlink_sat, is_gs_destination=False)
    
    # 3. 🔧 關鍵修復：為所有已存在路由中的中間節點補充路由完整性
    # 掃描現有路由，為所有中間節點添加到最終目的地的路由
    routing_chains = {}  # final_destination -> set of intermediate satellites
    
    for (src, dst), (next_hop, out_if, in_if) in fstate.items():
        # 只處理地面站作為最終目的地的路由
        if dst >= num_satellites:
            if dst not in routing_chains:
                routing_chains[dst] = set()
            
            # 如果當前節點是衛星且不是最終目的地，將其加入中間節點
            if src < num_satellites:
                routing_chains[dst].add(src)
            if next_hop < num_satellites and next_hop != dst:
                routing_chains[dst].add(next_hop)
    
    # # 為所有發現的中間衛星添加路由
    # for final_dst, intermediate_sats in routing_chains.items():
    #     for intermediate_sat in intermediate_sats:
    #         add_targeted_routing(intermediate_sat, final_dst, is_gs_destination=True)
    
    # 4. 🔧 最終修復：直接掃描所有路由鏈並補充缺失的關鍵路由
    
    def trace_and_fix_routing_chains():
        """追蹤所有路由鏈並修復缺失的中間路由"""
        print("🔧 開始修復路由鏈完整性...")
        
        # 為每個地面站追蹤完整的路由鏈
        for dst_gid in range(num_ground_stations):
            dst_gs_node_id = gs_idx_to_node_id(dst_gid)
            
            # 收集所有指向該地面站的路由起點
            sources_to_gs = []
            for (src, dst) in fstate.keys():
                if dst == dst_gs_node_id and src < num_satellites:  # 衛星到地面站
                    sources_to_gs.append(src)
            
            # 為每個源追蹤完整路由鏈
            for src in sources_to_gs:
                path = [src]
                current = src
                visited = set()
                
                # 追蹤路由鏈直到地面站或發現循環
                while current != dst_gs_node_id and current not in visited:
                    visited.add(current)
                    if (current, dst_gs_node_id) in fstate:
                        next_hop, _, _ = fstate[(current, dst_gs_node_id)]
                        if next_hop != dst_gs_node_id and next_hop < num_satellites:
                            path.append(next_hop)
                            current = next_hop
                        else:
                            break
                    else:
                        # 路由鏈中斷，需要修復
                        break
                
                # # 為路徑上的所有中間節點添加到目標地面站的路由
                # for i, intermediate_node in enumerate(path):
                #     if intermediate_node < num_satellites and (intermediate_node, dst_gs_node_id) not in fstate:
                #         # 強制為缺失的中間節點添加路由
                #         add_targeted_routing(intermediate_node, dst_gs_node_id, is_gs_destination=True)
        
    
    # 執行路由鏈修復
    trace_and_fix_routing_chains()
    
    # print("🔧 為關鍵節點強制添加路由...")
    # for node in critical_nodes:
    #     for dest_gid in range(num_ground_stations):
    #         dest_gs_node_id = gs_idx_to_node_id(dest_gid)
    #         if dest_gid in [1, 2]:  # 626, 627對應地面站索引1, 2
    #             add_targeted_routing(node, dest_gs_node_id, is_gs_destination=True)
    

    # GSL 帶寬設定
    gsl_if_bandwidth = {}
    for sat in sat_ids:
        gsl_if_bandwidth[(sat, 0)] = 1.0
    
    # 地面站 GSL 帶寬
    for gid in range(num_ground_stations):
        gs_node_id = gs_idx_to_node_id(gid)
        gsl_if_bandwidth[(gs_node_id, 0)] = 1.0

    # 寫入 fstate 文件
    output_filename_fstate = output_dynamic_state_dir + "/fstate_" + str(time_since_epoch_ns) + ".txt"
    with open(output_filename_fstate, "w+") as f_out:
        for (src, dst), (next_hop, out_if, in_if) in fstate.items():
            f_out.write(f"{src},{dst},{next_hop},{out_if},{in_if}\n")

    # 寫入 GSL 帶寬文件
    output_filename_gsl = output_dynamic_state_dir + "/gsl_if_bandwidth_" + str(time_since_epoch_ns) + ".txt"
    with open(output_filename_gsl, "w+") as f_out:
        for (sat, if_idx), bandwidth in gsl_if_bandwidth.items():
            f_out.write(f"{sat},{if_idx},{bandwidth}\n")

    # 在第一個時間步驟時保存群組數據供分析使用
    if time_since_epoch_ns == 0:
        data_dir = output_dynamic_state_dir.replace("dynamic_state_", "").replace("100ms_for_10s", "").replace("100ms_for_50s", "").replace("100ms_for_200s", "").replace("50ms_for_100s", "")
        data_dir = data_dir.rstrip("/") + "/data"
        os.makedirs(data_dir, exist_ok=True)
        
        # 保存群組分配數據
        with open(os.path.join(data_dir, "satellite_groups.pickle"), 'wb') as f:
            pickle.dump(pid_to_sats, f)
        
        # 保存master分配數據
        with open(os.path.join(data_dir, "satellite_group_to_master.pickle"), 'wb') as f:
            pickle.dump(pid_to_agent, f)
        
    if enable_verbose_logs:
        if stitch_skip_count == 0:
            print("[STITCH] No edges skipped.")
    else:
        print(f"[STITCH] Skipped edges: {stitch_skip_count} (showing up to 20 samples)")
        for (u,v,dg) in stitch_skip_samples:
            print(f"  [SKIP-SAMPLE] {u}->{v} (dst_gs={dg})")

    return {
        "fstate": fstate,
        "region_to_sats": pid_to_sats,
        "group_to_master": pid_to_agent,
        "gsl_if_bandwidth": gsl_if_bandwidth,
    }