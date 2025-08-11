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

      # --------
    # 接口頻寬狀態
    # --------
    
    output_filename = (
        output_dynamic_state_dir + f"/gsl_if_bandwidth_{time_since_epoch_ns}.txt"
    )
    if enable_verbose_logs:
        print("  > Writing interface bandwidth state to: " + output_filename)
    with open(output_filename, "w+") as f_out:
        if time_since_epoch_ns == 0:
            for node_id, info in enumerate(list_gsl_interfaces_info):
                num_if = info["number_of_interfaces"]
                bw = info["aggregate_max_bandwidth"] / float(num_if)
                for idx in range(num_if):
                    if node_id < len(satellites):
                        if_id = num_isls_per_sat[node_id] + idx
                    else:
                        if_id = idx
                    f_out.write("%d,%d,%f\n" % (node_id, if_id, bw))
                    
    gid_to_sat_gsl_if_idx = [0] * len(ground_stations)
    prev_fstate = None
    if prev_output is not None:
        prev_fstate = prev_output.get("fstate")

    gs_fstate = calculate_hierarchical_path_through_masters(
        output_dynamic_state_dir,
        time_since_epoch_ns,
        len(satellites),
        len(ground_stations),
        sat_net_graph_only_satellites_with_isls,
        num_isls_per_sat,
        gid_to_sat_gsl_if_idx,
        ground_station_satellites_in_range,
        sat_neighbor_to_if,
        prev_fstate,
        enable_verbose_logs,
        master_nodes,  # 增加 master 節點列表
        n_sats_per_orbit,  # 增加軌道結構信息
    )

    # Merge satellite-to-satellite with ground-station related forwarding state
    fstate.update(gs_fstate)

    # --------
    # 輸出 forwarding state
    # --------
    output_filename = output_dynamic_state_dir + f"/fstate_{time_since_epoch_ns}.txt"
    write_fstate_to_file(fstate, output_filename)

    return {"fstate": fstate}

def calculate_hierarchical_path_through_masters(
        output_dynamic_state_dir,
        time_since_epoch_ns,
        num_satellites,
        num_ground_stations,
        sat_net_graph_only_satellites_with_isls,
        num_isls_per_sat,
        gid_to_sat_gsl_if_idx,
        ground_station_satellites_in_range,
        sat_neighbor_to_if,
        prev_fstate,
        enable_verbose_logs,
        master_nodes,
        n_sats_per_orbit,
):
    """
    計算地面站之間通過層次化路由的轉發狀態
    
    與原始方案不同：
    1. 地面站可連接任何可見衛星
    2. 群組內採用最短路徑路由
    3. 跨群組通信需要經過 master 衛星
    """
    if enable_verbose_logs:
        print("  > Calculating forwarding state for ground stations (hierarchical with flexible uplink)")
    
    # 結果字典: (src, dst) -> (next_hop, src_if, next_hop_if)
    fstate = {}
    
    # 確定每個衛星所屬的軌道/群組
    sat_to_group = {sid: sid // n_sats_per_orbit for sid in range(num_satellites)}
    
    # 確定每個群組的 master 衛星
    group_to_master = {}
    for master in master_nodes:
        group = sat_to_group[master]
        group_to_master[group] = master
    
    # 找出每個地面站可以到達的衛星
    gs_to_reachable_sats = {}
    for gid in range(num_ground_stations):
        sat_id_list = []
        if gid < len(ground_station_satellites_in_range):
            for sid in range(num_satellites):
                # 防止索引越界
                try:
                    if ground_station_satellites_in_range[gid][sid]:
                        sat_id_list.append(sid)
                except IndexError:
                    # 越界時跳過該衛星
                    continue
        gs_to_reachable_sats[gid] = sat_id_list
    
    # 為每對地面站計算轉發路徑
    for src_gid in range(num_ground_stations):
        for dst_gid in range(num_ground_stations):
            if src_gid == dst_gid:
                continue
            
            src_node_id = num_satellites + src_gid
            dst_node_id = num_satellites + dst_gid
            
            # 檢查源地面站和目標地面站是否有可達的衛星
            src_reachable = gs_to_reachable_sats[src_gid]
            dst_reachable = gs_to_reachable_sats[dst_gid]
            
            if not src_reachable or not dst_reachable:
                continue  # 若無可達衛星則跳過
            
            # 為源和目標地面站選擇最佳可達衛星（此處可用各種策略，如最短距離）
            # 這裡簡單地選第一個可達衛星
            src_sat = src_reachable[0]
            dst_sat = dst_reachable[0]
            
            # 確定源和目標衛星所屬群組
            src_group = sat_to_group[src_sat]
            dst_group = sat_to_group[dst_sat]
            
            # 地面站到初始衛星的轉發
            fstate[(src_node_id, dst_node_id)] = (
                src_sat,
                gid_to_sat_gsl_if_idx[src_gid],
                num_isls_per_sat[src_sat] + 0 # 假設每個衛星只有一個接口連接地面站
            )
            
            # 如果源和目標在同一群組，使用群組內路由
            if src_group == dst_group:
                try:
                    # 計算群組內的最短路徑
                    path = nx.shortest_path(
                        sat_net_graph_only_satellites_with_isls,
                        src_sat,
                        dst_sat,
                        weight="weight"
                    )
                    
                    # 設置群組內路由
                    for i in range(len(path) - 1):
                        curr = path[i]
                        next_hop = path[i + 1]
                        
                        if (curr, next_hop) not in fstate:
                            fstate[(curr, next_hop)] = (
                                next_hop,
                                sat_neighbor_to_if[(curr, next_hop)],
                                sat_neighbor_to_if[(next_hop, curr)]
                            )
                except nx.NetworkXNoPath:
                    continue  # 如果找不到路徑則跳過
            else:
                # 不同群組，需要通過 master 衛星
                src_master = group_to_master[src_group]
                dst_master = group_to_master[dst_group]
                
                try:
                    # 1. 源衛星到源 master 的路徑
                    if src_sat != src_master:
                        path1 = nx.shortest_path(
                            sat_net_graph_only_satellites_with_isls,
                            src_sat,
                            src_master,
                            weight="weight"
                        )
                        
                        for i in range(len(path1) - 1):
                            curr = path1[i]
                            next_hop = path1[i + 1]
                            
                            if (curr, next_hop) not in fstate:
                                fstate[(curr, next_hop)] = (
                                    next_hop,
                                    sat_neighbor_to_if[(curr, next_hop)],
                                    sat_neighbor_to_if[(next_hop, curr)]
                                )
                    
                    # 2. 源 master 到目標 master 的路徑
                    path2 = nx.shortest_path(
                        sat_net_graph_only_satellites_with_isls,
                        src_master,
                        dst_master,
                        weight="weight"
                    )
                    
                    for i in range(len(path2) - 1):
                        curr = path2[i]
                        next_hop = path2[i + 1]
                        
                        if (curr, next_hop) not in fstate:
                            fstate[(curr, next_hop)] = (
                                next_hop,
                                sat_neighbor_to_if[(curr, next_hop)],
                                sat_neighbor_to_if[(next_hop, curr)]
                            )
                    
                    # 3. 目標 master 到目標衛星的路徑
                    if dst_master != dst_sat:
                        path3 = nx.shortest_path(
                            sat_net_graph_only_satellites_with_isls,
                            dst_master,
                            dst_sat,
                            weight="weight"
                        )
                        
                        for i in range(len(path3) - 1):
                            curr = path3[i]
                            next_hop = path3[i + 1]
                            
                            if (curr, next_hop) not in fstate:
                                fstate[(curr, next_hop)] = (
                                    next_hop,
                                    sat_neighbor_to_if[(curr, next_hop)],
                                    sat_neighbor_to_if[(next_hop, curr)]
                                )
                    
                    # 4. 最後目標衛星到地面站的轉發
                    fstate[(dst_sat, dst_node_id)] = (
                        dst_node_id,
                        num_isls_per_sat[dst_sat] + ground_station_satellites_in_range[dst_gid].index(True),
                        gid_to_sat_gsl_if_idx[dst_gid]
                    )
                    
                except nx.NetworkXNoPath:
                    # 若無法建立完整路徑，嘗試使用全局最短路徑作為備用
                    try:
                        # 計算全局最短路徑（不考慮層次化結構）
                        path = nx.shortest_path(
                            sat_net_graph_only_satellites_with_isls,
                            src_sat,
                            dst_sat,
                            weight="weight"
                        )
                        
                        # 設置路由
                        for i in range(len(path) - 1):
                            curr = path[i]
                            next_hop = path[i + 1]
                            
                            if (curr, next_hop) not in fstate:
                                fstate[(curr, next_hop)] = (
                                    next_hop,
                                    sat_neighbor_to_if[(curr, next_hop)],
                                    sat_neighbor_to_if[(next_hop, curr)]
                                )
                        
                        # 設置到地面站的最後跳
                        fstate[(dst_sat, dst_node_id)] = (
                            dst_node_id,
                            num_isls_per_sat[dst_sat] + ground_station_satellites_in_range[dst_gid].index(True),
                            gid_to_sat_gsl_if_idx[dst_gid]
                        )
                    except nx.NetworkXNoPath:
                        continue  # 如果連備用路徑也找不到，則跳過
    
    return fstate

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
