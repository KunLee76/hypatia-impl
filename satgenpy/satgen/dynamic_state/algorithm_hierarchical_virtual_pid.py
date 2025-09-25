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

# PathCache: 每個 time step 重建一次，避免 GS×GS 迴圈重複呼叫 nx.shortest_path
class PathCache:  # [NEW]
    def __init__(self, graph: nx.Graph, agents: List[int], num_sats: int):
        self.graph = graph
        self.num_sats = num_sats

        # Agent ↔ Agent 全對全最短路徑
        all_pairs = nx.all_pairs_dijkstra_path(graph, weight="weight")
        self.agent_paths = {u: v for u, v in all_pairs}

        # to_agent[a][src] = src 往 agent a 的下一跳
        self.to_agent: Dict[int, Dict[int, int]] = {}
        # from_agent[a][dst] = agent a 往 dst 的下一跳
        self.from_agent: Dict[int, Dict[int, int]] = {}

        for a in agents:
            if a is None or a not in graph:
                continue
            # 從 agent 出發的單源樹
            lengths, paths = nx.single_source_dijkstra(graph, a, weight="weight")
            self.from_agent[a] = {}
            for dst, path in paths.items():
                if len(path) >= 2:
                    self.from_agent[a][dst] = path[1]

            # 反向 (sat→agent)
            lengths, paths = nx.single_source_dijkstra(graph, a, weight="weight")
            self.to_agent[a] = {}
            for src, path in paths.items():
                if len(path) >= 2:
                    self.to_agent[a][src] = path[-2]  # 倒數第二個點是往 agent 方向的下一跳
    
        self.to_downlink: Dict[int, Dict[int, int]] = {}  # to_downlink[dst_sat][src_sat] = 下一跳
        for dst in range(num_sats):
            if dst not in graph: continue
            _, paths = nx.single_source_dijkstra(graph, dst, weight="weight")
            self.to_downlink[dst] = {}
            for src, path in paths.items():
                if len(path) >= 2:
                    self.to_downlink[dst][src] = path[-2]  # src 往 dst 的下一跳


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
                 lat_min: int = -90, lat_max: int = 90, allow_diagonal_neighbor: bool = True) -> None:
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

    def next_hop_sat(self, t: int, src: int, dst_pid: int, pid_next=None) -> Optional[int]:
        k = (int(t), src, dst_pid)
        if k in self._hop_cache:
            return self._hop_cache[k]
        lat, lon = self.get_sat_latlon(src, t)
        here_pid = self.latlon_to_pid(lat, lon)
        if here_pid is None: return None
        agent_here = self.pid_agent_sat.get(here_pid)
        if agent_here is None: return None
        if src != agent_here:
            nh = self._first_hop_towards(src, agent_here, t)
            self._hop_cache[k] = nh
            return nh
        if here_pid == dst_pid:
            self._hop_cache[k] = None
            return None
        next_pid = pid_next.get(here_pid, {}).get(dst_pid, None) if pid_next else None
        if next_pid is None: return None
        agent_next = self.pid_agent_sat.get(next_pid)
        if agent_next is None: return None
        nh = self._first_hop_towards(agent_here, agent_next, t)
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
        if lon >= 180: lon -= 360
        if lon < -180: lon += 360
        return (lat, lon)
    latlon_cache = [get_latlon_by_ephem(sid, step) for sid in sat_ids]

    router = VirtualPIDRouter(grid_deg=15)
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

    def first_reachable_sat(gs_id: int) -> Optional[int]:
        # ground_station_satellites_in_range[gs_id] 形式通常是 [(dist_m, sat_id), ...]
        if gs_id < len(ground_station_satellites_in_range):
            lst = ground_station_satellites_in_range[gs_id]
        else:
            lst = []
        return lst[0][1] if lst else None

    def gsl_if_index_on_sat_for_gs(sat_id: int, gs_id: int) -> Optional[int]:
        """
        回傳「衛星端」連到該地面站的 GSL 介面索引。 
        規則：ISL 介面先佔用 [0 .. num_isls_per_sat[sat)-1]，
            GSL 介面從 num_isls_per_sat[sat] 起算。
        若同一顆衛星允許多個 GSL 介面，這裡用地面站在可視列表中的次序當偏移（可重現）。
        """
        base = num_isls_per_sat[sat_id]
        if gs_id < len(ground_station_satellites_in_range):
            lst = ground_station_satellites_in_range[gs_id]
        else:
            lst = []
        for idx, (_, sid) in enumerate(lst):
            if sid == sat_id:
                return base + idx
        return None  # 找不到代表不在可視列表（理論上不會走到這）

    def pid_of_sat(sat_id: int) -> Optional[int]:
        lat, lon = router.get_sat_latlon(sat_id, step)
        return router.latlon_to_pid(lat, lon)

    def stitch_sat_path(path_nodes: List[int], final_dst_gs_id: int):
        """
        沿著節點序列 (n0 -> n1 -> ... -> nk)，
        以 (u, 最終目的地地面站) 為 key 寫入第一跳 (v, out_if, in_if)。
        """
        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]
            v = path_nodes[i + 1]
            out_if = sat_neighbor_to_if_map.get((u, v))
            in_if  = sat_neighbor_to_if_map.get((v, u))
            if out_if is None or in_if is None:
                continue
            if (u, final_dst_gs_id) not in fstate:
                fstate[(u, final_dst_gs_id)] = (v, out_if, in_if)

    # [NEW] 建立 PathCache
    agents = [ag for ag in pid_to_agent.values() if ag is not None]
    cache = PathCache(sat_net_graph_only_satellites_with_isls, agents, len(sat_ids))

    # GS×GS 迴圈
    for src_gid in range(num_ground_stations):
        for dst_gid in range(num_ground_stations):
            if src_gid == dst_gid:
                continue

            src_gs_id = num_satellites + src_gid
            dst_gs_id = num_satellites + dst_gid

            src_uplink_sat = first_reachable_sat(src_gid)
            dst_downlink_sat = first_reachable_sat(dst_gid)
            if src_uplink_sat is None or dst_downlink_sat is None:
                continue

            # (1) GS→Sat 上行
            gs_out_if = 0
            sat_in_if = num_isls_per_sat[src_uplink_sat]
            fstate[(src_gs_id, dst_gs_id)] = (src_uplink_sat, gs_out_if, sat_in_if)

            src_pid = pid_of_sat(src_uplink_sat)
            dst_pid = pid_of_sat(dst_downlink_sat)

            # (2) Sat↔Sat 段
            if src_pid is not None and dst_pid is not None and src_pid == dst_pid:
                if dst_downlink_sat in cache.to_downlink:
                    nh = cache.to_downlink[dst_downlink_sat].get(src_uplink_sat)
                    if nh:
                        out_if = sat_neighbor_to_if.get((src_uplink_sat, nh))
                        in_if = sat_neighbor_to_if.get((nh, src_uplink_sat))
                        if out_if is not None and in_if is not None:
                            fstate[(src_uplink_sat, dst_gs_id)] = (nh, out_if, in_if)
            else:
                src_agent = pid_to_agent.get(src_pid) if src_pid is not None else None
                dst_agent = pid_to_agent.get(dst_pid) if dst_pid is not None else None

                # uplink → src_agent
                if src_agent is not None and src_uplink_sat != src_agent:
                    nh = cache.to_agent.get(src_agent, {}).get(src_uplink_sat)
                    if nh:
                        out_if = sat_neighbor_to_if.get((src_uplink_sat, nh))
                        in_if = sat_neighbor_to_if.get((nh, src_uplink_sat))
                        if out_if is not None and in_if is not None:
                            fstate[(src_uplink_sat, dst_gs_id)] = (nh, out_if, in_if)

                # src_agent → dst_agent
                if src_agent is not None and dst_agent is not None and src_agent != dst_agent:
                    agent_path = cache.agent_paths.get(src_agent, {}).get(dst_agent)
                    if agent_path:
                        stitch_sat_path(agent_path, dst_gs_id)

                # dst_agent → downlink
                if dst_agent is not None and dst_agent != dst_downlink_sat:
                    nh = cache.from_agent.get(dst_agent, {}).get(dst_downlink_sat)
                    if nh:
                        out_if = sat_neighbor_to_if.get((dst_agent, nh))
                        in_if = sat_neighbor_to_if.get((nh, dst_agent))
                        if out_if is not None and in_if is not None:
                            fstate[(dst_agent, dst_gs_id)] = (nh, out_if, in_if)

            # (3) Sat→GS 下行
            sat_out_if = gsl_if_index_on_sat_for_gs(dst_downlink_sat, dst_gid)
            if sat_out_if is None:
                continue
            gs_in_if = 0
            fstate[(dst_downlink_sat, dst_gs_id)] = (dst_gs_id, sat_out_if, gs_in_if)

    # GSL 帶寬設定
    gsl_if_bandwidth = {}
    for sat in sat_ids:
        gsl_if_bandwidth[(sat, 0)] = 1.0
    
    # 地面站 GSL 帶寬
    for gid in range(num_ground_stations):
        gsl_if_bandwidth[(num_satellites + gid, 0)] = 1.0

    # 寫入 fstate 文件
    output_filename_fstate = output_dynamic_state_dir + "/fstate_" + str(time_since_epoch_ns) + ".txt"
    if enable_verbose_logs:
        print(f"  > Writing fstate to: {output_filename_fstate}")
    with open(output_filename_fstate, "w+") as f_out:
        for (src, dst), (next_hop, out_if, in_if) in fstate.items():
            f_out.write(f"{src},{dst},{next_hop},{out_if},{in_if}\n")

    # 寫入 GSL 帶寬文件
    output_filename_gsl = output_dynamic_state_dir + "/gsl_if_bandwidth_" + str(time_since_epoch_ns) + ".txt"
    if enable_verbose_logs:
        print(f"  > Writing GSL bandwidth to: {output_filename_gsl}")
    with open(output_filename_gsl, "w+") as f_out:
        for (sat, if_idx), bandwidth in gsl_if_bandwidth.items():
            f_out.write(f"{sat},{if_idx},{bandwidth}\n")

    if enable_verbose_logs:
        print(f"  > Virtual PID routing: {len(fstate)} fstate entries written")
        print(f"  > Virtual PID routing: {len(gsl_if_bandwidth)} GSL bandwidth entries written")

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
            print(f"  > Saved group data to: {data_dir}")

    return {
        "fstate": fstate,
        "region_to_sats": pid_to_sats,
        "group_to_master": pid_to_agent,
        "gsl_if_bandwidth": gsl_if_bandwidth,
    }