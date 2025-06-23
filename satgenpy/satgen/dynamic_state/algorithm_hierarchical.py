from .fstate_calculation import calculate_fstate_shortest_path_without_gs_relaying
import math
import networkx as nx

def algorithm_hierarchical(
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
):
    """
    ROUTING ALGO

    1. 依照星座分群，每群選出一個 master 衛星
    2. 對外路由：master 與 master 之間尋找下一跳 master
    3. 群內路由：由 master 計算群內最短路徑並找到接近邊界的衛星
    4. 最後在 master 決定的邊界衛星與外部 master 之間建立轉發。
    """

    if enable_verbose_logs:
        print("\nALGORITHM: HIERARCHICAL")

    n_orbits, n_sats_per_orbit = _infer_orbit_structure(satellites)
    # 計算 master 之間的路徑 (下面各註解部分尚未完成，記得要再細部定義!!)
    master_nodes = select_master_nodes(satellites, n_orbits, n_sats_per_orbit)
    # master_graph = build_master_graph(master_nodes, sat_net_graph_only_satellites_with_isls)

    # 群外forwarding，決定各 master 的下一個 master
    master_fstate = compute_master_forwarding(sat_net_graph_only_satellites_with_isls,
        master_nodes, sat_neighbor_to_if)

    # 群內forwarding，從 master 到邊界衛星
    group_fstate = compute_intra_group_paths(
        satellites,
        master_nodes,
        sat_net_graph_only_satellites_with_isls,
        n_sats_per_orbit,
        sat_neighbor_to_if
    )

    # 合併兩種 forwarding state
    fstate = merge_fstate(master_fstate, group_fstate)

    # 輸出檔案
    output_filename = output_dynamic_state_dir + f"/fstate_{time_since_epoch_ns}.txt"
    write_fstate_to_file(fstate, output_filename)

    return {"fstate": fstate}

def _infer_orbit_structure(satellites):
    """Infer number of orbits and satellites per orbit from TLE data."""
    raans = sorted({round(s._raan, 6) for s in satellites})
    n_orbits = len(raans) if raans else 1
    if len(satellites) % n_orbits != 0:
        raise ValueError("Cannot infer satellites per orbit from TLEs")
    return n_orbits, len(satellites) // n_orbits

def select_master_nodes(satellites, n_orbits, n_sats_per_orbit):
    # 用TLE依軌道編號遞增，挑選第一顆 master 衛星
    if len(satellites) != n_orbits * n_sats_per_orbit:
        raise ValueError("satellites' number error")
    masters = []
    for orbit_id in range(n_orbits):
        # 由於 TLE 依 orbit 編號遞增，軌道的第一顆衛星 ID 即 orbit_id * n_sats_per_orbit
        master_sid = orbit_id * n_sats_per_orbit
        masters.append(master_sid)
    return masters

def build_master_graph(masters, full_graph):
    # 依 masters 畫簡化後的 master-to-master 圖，邊的權重為圖中2 master 之間的最短路徑距離
    dist = nx.floyd_warshall_numpy(full_graph)

    master_graph = nx.Graph()
    master_graph.add_nodes_from(masters)

    for i in range(len(masters)):
        for j in range(i + 1, len(masters)):
            m1 = masters[i]
            m2 = masters[j]
            distance = dist[m1, m2]
            # 若無法到達，可依需求忽略或視為斷鏈
            if math.isinf(distance):
                continue
            # 權重採用在原圖上的最短距離
            master_graph.add_edge(m1, m2, weight=distance)
    return master_graph

def compute_master_forwarding(full_graph, masters, sat_neighbor_to_if):
    # 計算 masters 之間的路徑 (最短路徑...等等)
    # 用邊權重為距離，算最短路徑，並取得第一個master下一跳
    # 先計算 master_graph 內的兩兩最短路徑
    paths = dict(nx.all_pairs_dijkstra_path(full_graph, weight="weight"))
    forwarding = {}
    for src in masters:
        for dst in masters:
            if src == dst:
                continue
            path = paths[src][dst]
            if len(path) >= 2:
                nxt = path[1]
                forwarding[(src, dst)] = (
                    nxt,
                    sat_neighbor_to_if[(src, nxt)],
                    sat_neighbor_to_if[(nxt, src)]
                )

    return forwarding

def group_of(sid, n_sats_per_orbit):
    """回傳衛星 sid 所屬的群組(軌道)編號。"""
    return sid // n_sats_per_orbit

def compute_intra_group_paths(sats, masters, full_graph, n_sats_per_orbit, sat_neighbor_to_if):
    # 在各群內決定 master 到邊界衛星的路由
    # full_graph 含有all衛星與 ISL 的圖
    forwarding = {}
    for master in masters:
        group_nodes = [n for n in range(len(sats)) if group_of(n, n_sats_per_orbit) == group_of(master, n_sats_per_orbit)]
        for dst in group_nodes:
            if dst == master:
                continue
            path = nx.shortest_path(full_graph, master, dst, weight="weight")
            if len(path) >= 2:
                nxt = path[1]
                forwarding[(master, dst)] = (
                    nxt,
                    sat_neighbor_to_if[(master, nxt)],
                    sat_neighbor_to_if[(nxt, master)]
                )
    
    return forwarding

def merge_fstate(master_fstate, group_fstate):
    # 將群內、群外table合併
    merged = dict(master_fstate)               # 先複製 master 的內容
    for key, val in group_fstate.items():
        if key in merged and merged[key] != val:
            raise ValueError(f"Conflict for {key}: {merged[key]} vs {val}")
        merged[key] = val
        
    return merged

def write_fstate_to_file(fstate, filename):
    """Write forwarding state to text file."""
    with open(filename, "w+") as f:
        for (src, dst), (nxt, out_if, in_if) in fstate.items():
            f.write(f"{src},{dst},{nxt},{out_if},{in_if}\n")
