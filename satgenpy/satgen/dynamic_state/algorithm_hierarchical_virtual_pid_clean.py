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
            # Multi-hop backbone with component filtering + reachable fallback
            pid_path = nx.shortest_path(pid_graph, src_pid, dst_pid)
            current_sat = src_uplink_sat
            current_pid = src_pid

            for next_pid in pid_path[1:]:
                candidates = gcache.get_gateways(current_pid, next_pid)
                gw_used = None
                for satA, satB, gw_cost in candidates:
                    if not same_comp(current_pid, current_sat, satA):
                        continue
                    out_if = sat_neighbor_to_if_map.get((satA, satB))
                    in_if  = sat_neighbor_to_if_map.get((satB, satA))
                    if out_if is not None and in_if is not None:
                        gw_used = (satA, satB, gw_cost)
                        break
                if gw_used is None:
                    reach = reachable_in_pid(current_pid, current_sat)
                    best = None
                    for u in reach:
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
                    break

                satA, satB, _ = gw_used

                if current_sat != satA:
                    current_pid_subgraph = pid_subgraphs[current_pid]
                    try:
                        path_to_gw = nx.shortest_path(current_pid_subgraph, current_sat, satA, weight="weight")
                        stitch_sat_path(path_to_gw, dst_gs_id)
                    except nx.NetworkXNoPath:
                        if enable_verbose_logs:
                            print(f"[NOPATH] PID={current_pid} subgraph|V|={current_pid_subgraph.number_of_nodes()} no path {current_sat}->{satA} toward dst_gs={dst_gs_id}")
                        break

                stitch_sat_path([satA, satB], dst_gs_id)

                current_sat = satB
                current_pid = next_pid
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
    
    def :
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