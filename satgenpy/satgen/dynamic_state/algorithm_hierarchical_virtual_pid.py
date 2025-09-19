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
import ephem
from datetime import datetime, timezone
from astropy.time import Time
import numpy as np

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

    def __init__(self, grid_deg: int = 10, lon_min: int = -180, lon_max: int = 180,
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

    router = VirtualPIDRouter(grid_deg=10)
    router.get_sat_latlon = lambda sid, _t: latlon_cache[sid]
    router.get_sat_neighbors = lambda sid, _t: list(sat_net_graph_only_satellites_with_isls.neighbors(sid))
    router.update_pid_members_and_agents(step, sat_ids)
    pid_to_sats, pid_to_agent = router.pid_members, router.pid_agent_sat
    sat_neighbor_to_if_map = sat_neighbor_to_if

    # 優化: 預先計算 PID→PID 表
    pid_next = router.build_pid_next_table(step)
    valid_pids = [pid for pid, ag in pid_to_agent.items() if ag is not None and pid_to_sats[pid]]

    # 預先計算 src→pid agent 的 next hop
    src_pid_next_hop = {}
    for src in sat_ids:
        for pid in valid_pids:
            nh = router.next_hop_sat(step, src, pid, pid_next=pid_next)
            src_pid_next_hop[(src, pid)] = nh

    # 展開成 fstate
    fstate = {}
    for pid in valid_pids:
        members = pid_to_sats[pid]
        for src in sat_ids:
            nh = src_pid_next_hop[(src, pid)]
            if nh is None: continue
            out_if = sat_neighbor_to_if_map.get((src, nh))
            in_if = sat_neighbor_to_if_map.get((nh, src))
            if out_if is None or in_if is None: continue
            for dst in members:
                if dst == src: continue
                fstate[(src, dst)] = (nh, out_if, in_if)

    # 先暫定 GSL 帶寬，每個衛星對應一個 GSL interface，1.0代表
    gsl_if_bandwidth = {}
    for sat in sat_ids:
        gsl_if_bandwidth[(sat, 0)] = 1.0

    return {
    "fstate": fstate,
    "region_to_sats": pid_to_sats,
    "group_to_master": pid_to_agent,
    "gsl_if_bandwidth": gsl_if_bandwidth,
}