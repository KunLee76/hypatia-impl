"""
Virtual PID‑based hierarchical router for LEO constellations.

Fixed and cleaned version of the hierarchical virtual PID algorithm.
"""

from typing import Dict, List, Optional, Set, Tuple
import math
import os
import pickle
import ephem
from datetime import datetime, timezone
try:
    from astropy.time import Time
    ASTROPY_AVAILABLE = True
except ImportError:
    ASTROPY_AVAILABLE = False
import numpy as np
import networkx as nx

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
    if ASTROPY_AVAILABLE:
        try:
            if isinstance(epoch_obj, Time):
                t_utc = epoch_obj.utc
                dt = t_utc.to_datetime()
                return ephem.Date(dt)
        except Exception:
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
        self._hop_cache: Dict[Tuple[int, int, int], Optional[int]] = {}

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
            if su is None:
                continue
            for v in self.pid_neighbors[u]:
                sv = self.pid_agent_sat.get(v)
                if sv is None:
                    continue
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
                    if v in prev:
                        continue
                    prev[v] = u
                    q.append(v)
            for dst in range(len(self.pids)):
                if dst == src or dst not in prev:
                    continue
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
        def rad(x):
            return x * math.pi / 180.0
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
        
        # 同PID內：直接使用地理最優路由，不經過agent
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
        
        # 跨PID：使用PID-level路由表找下一個PID
        next_pid = pid_next.get(here_pid, {}).get(dst_pid, None) if pid_next else None
        if next_pid is None:
            return None
            
        # 獲取下一個PID的agent作為目標
        agent_next = self.pid_agent_sat.get(next_pid)
        if agent_next is None:
            return None
            
        # 從當前位置直接路由到下一個PID的agent
        nh = self._first_hop_towards(src, agent_next, t)
        self._hop_cache[k] = nh
        return nh


# ============================================================
# Algorithm entry
# ============================================================
def algorithm_hierarchical_virtual_pid_clean(
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
        if lon >= 180:
            lon -= 360
        if lon < -180:
            lon += 360
        return (lat, lon)
    
    latlon_cache = [get_latlon_by_ephem(sid, step) for sid in sat_ids]

    router = VirtualPIDRouter(grid_deg=15, allow_diagonal_neighbor=False)
    router.get_sat_latlon = lambda sid, _t: latlon_cache[sid]
    router.get_sat_neighbors = lambda sid, _t: list(sat_net_graph_only_satellites_with_isls.neighbors(sid))
    router.update_pid_members_and_agents(step, sat_ids)
    
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
        if gs_idx < len(ground_station_satellites_in_range):
            lst = ground_station_satellites_in_range[gs_idx]
        else:
            lst = []
        return lst[0][1] if lst else None

    def gsl_if_index_on_sat_for_gs(sat_id: int, gs_idx: int) -> Optional[int]:
        """回傳「衛星端」連到該地面站的 GSL 介面索引"""
        base = num_isls_per_sat[sat_id]
        if gs_idx < len(ground_station_satellites_in_range):
            lst = ground_station_satellites_in_range[gs_idx]
        else:
            lst = []
        for idx, (_, sid) in enumerate(lst):
            if sid == sat_id:
                return base + idx
        return None

    def pid_of_sat(sat_id: int) -> Optional[int]:
        lat, lon = router.get_sat_latlon(sat_id, step)
        return router.latlon_to_pid(lat, lon)
    
    gcache = GatewayCache(sat_net_graph_only_satellites_with_isls, router, sat_ids, pid_of_sat)

    def stitch_sat_path(path_nodes: List[int], final_dst_gs_id: int):
        """
        沿著節點序列 (n0 -> n1 -> ... -> nk)，
        以 (u, 最終目的地地面站) 為 key 寫入第一跳 (v, out_if, in_if)。
        """
        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]
            v = path_nodes[i + 1]
            out_if = sat_neighbor_to_if_map.get((u, v))
            in_if = sat_neighbor_to_if_map.get((v, u))
            if out_if is None or in_if is None:
                continue
            if (u, final_dst_gs_id) not in fstate:
                fstate[(u, final_dst_gs_id)] = (v, out_if, in_if)

    # 建 PID-level graph
    pid_graph = nx.Graph()
    for pid, nbrs in router.pid_neighbors.items():
        for n in nbrs:
            pid_graph.add_edge(pid, n)

    # 統一的 GS×GS 路由處理
    stitch_skip_count = 0
    stitch_skip_samples = []
    
    for src_gid in range(num_ground_stations):
        for dst_gid in range(num_ground_stations):
            if src_gid == dst_gid:
                continue

            src_gs_node_id = gs_idx_to_node_id(src_gid)
            dst_gs_node_id = gs_idx_to_node_id(dst_gid)
            
            src_uplink_sat = first_reachable_sat(src_gid)
            dst_downlink_sat = first_reachable_sat(dst_gid)
            if src_uplink_sat is None or dst_downlink_sat is None:
                continue

            # (1) GS→Sat 上行連接
            gs_out_if = 0
            sat_in_if = num_isls_per_sat[src_uplink_sat]
            fstate[(src_gs_node_id, dst_gs_node_id)] = (src_uplink_sat, gs_out_if, sat_in_if)

            src_pid = pid_of_sat(src_uplink_sat)
            dst_pid = pid_of_sat(dst_downlink_sat)
            
            if src_pid is None or dst_pid is None:
                continue

            # (2) 🎯 簡化的Sat↔Sat路由邏輯
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
                else:
                    # 跨PID：使用全局最短路徑
                    try:
                        global_shortest_path = nx.shortest_path(
                            sat_net_graph_only_satellites_with_isls,
                            src_uplink_sat,
                            dst_downlink_sat,
                            weight="weight"
                        )
                        stitch_sat_path(global_shortest_path, dst_gs_node_id)
                    except nx.NetworkXNoPath:
                        # 如果全局路徑不存在，使用PID級別路由
                        if not pid_graph.has_path(src_pid, dst_pid):
                            continue
                            
                        pid_path = nx.shortest_path(pid_graph, src_pid, dst_pid)
                        current_sat = src_uplink_sat
                        current_pid = src_pid

                        for next_pid in pid_path[1:]:
                            candidates = gcache.get_gateways(current_pid, next_pid)
                            gw_used = None
                            
                            # 選擇第一個有效的gateway
                            for satA, satB, gw_cost in candidates:
                                out_if = sat_neighbor_to_if_map.get((satA, satB))
                                in_if = sat_neighbor_to_if_map.get((satB, satA))
                                if out_if is not None and in_if is not None:
                                    gw_used = (satA, satB, gw_cost)
                                    break
                            
                            if gw_used is None:
                                break
                            
                            satA, satB, _ = gw_used

                            # PID內路由到gateway A
                            if current_sat != satA:
                                current_pid_subgraph = sat_net_graph_only_satellites_with_isls.subgraph(pid_to_sats[current_pid])
                                try:
                                    path_to_gw = nx.shortest_path(
                                        current_pid_subgraph,
                                        current_sat,
                                        satA,
                                        weight="weight"
                                    )
                                    stitch_sat_path(path_to_gw, dst_gs_node_id)
                                except nx.NetworkXNoPath:
                                    break

                            # Gateway跨越
                            stitch_sat_path([satA, satB], dst_gs_node_id)
                            
                            current_sat = satB
                            current_pid = next_pid

                        # 最後一段：到目標衛星
                        if current_sat != dst_downlink_sat and current_pid == dst_pid:
                            final_pid_subgraph = sat_net_graph_only_satellites_with_isls.subgraph(pid_to_sats[dst_pid])
                            try:
                                final_path = nx.shortest_path(
                                    final_pid_subgraph,
                                    current_sat,
                                    dst_downlink_sat,
                                    weight="weight"
                                )
                                stitch_sat_path(final_path, dst_gs_node_id)
                            except nx.NetworkXNoPath:
                                pass

            except nx.NetworkXNoPath:
                stitch_skip_count += 1
                if len(stitch_skip_samples) < 20:
                    stitch_skip_samples.append((src_uplink_sat, dst_downlink_sat, dst_gs_node_id))
                continue

            # (3) Sat→GS 下行連接
            sat_out_if = gsl_if_index_on_sat_for_gs(dst_downlink_sat, dst_gid)
            if sat_out_if is None:
                continue
            gs_in_if = 0
            fstate[(dst_downlink_sat, dst_gs_node_id)] = (dst_gs_node_id, sat_out_if, gs_in_if)

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
            for (u, v, dg) in stitch_skip_samples:
                print(f"  [SKIP-SAMPLE] {u}->{v} (dst_gs={dg})")

    return {
        "fstate": fstate,
        "region_to_sats": pid_to_sats,
        "group_to_master": pid_to_agent,
        "gsl_if_bandwidth": gsl_if_bandwidth,
    }