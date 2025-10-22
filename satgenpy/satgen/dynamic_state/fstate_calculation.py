import math
import networkx as nx


def calculate_fstate_shortest_path_without_gs_relaying(
        output_dynamic_state_dir,
        time_since_epoch_ns,
        num_satellites,
        num_ground_stations,
        sat_net_graph_only_satellites_with_isls,
        num_isls_per_sat,
        gid_to_sat_gsl_if_idx,
        ground_station_satellites_in_range_candidates,
        sat_neighbor_to_if,
        prev_fstate,
        enable_verbose_logs
):

    # Calculate shortest path distances
    if enable_verbose_logs:
        print("  > Calculating Floyd-Warshall for graph without ground-station relays")
    # (Note: Numpy has a deprecation warning here because of how networkx uses matrices)
    dist_sat_net_without_gs = nx.floyd_warshall_numpy(sat_net_graph_only_satellites_with_isls)

    # Forwarding state
    fstate = {}

    # Now write state to file for complete graph
    output_filename = output_dynamic_state_dir + "/fstate_" + str(time_since_epoch_ns) + ".txt"
    if enable_verbose_logs:
        print("  > Writing forwarding state to: " + output_filename)
    with open(output_filename, "w+") as f_out:

        # Satellites to ground stations
        # From the satellites attached to the destination ground station,
        # select the one which promises the shortest path to the destination ground station (getting there + last hop)
        dist_satellite_to_ground_station = {}
        for curr in range(num_satellites):
            for dst_gid in range(num_ground_stations):
                dst_gs_node_id = num_satellites + dst_gid

                # Among the satellites in range of the destination ground station,
                # find the one which promises the shortest distance
                possible_dst_sats = ground_station_satellites_in_range_candidates[dst_gid]
                possibilities = []
                for b in possible_dst_sats:
                    if not math.isinf(dist_sat_net_without_gs[(curr, b[1])]):  # Must be reachable
                        possibilities.append(
                            (
                                dist_sat_net_without_gs[(curr, b[1])] + b[0],
                                b[1]
                            )
                        )
                possibilities = list(sorted(possibilities))

                # By default, if there is no satellite in range for the
                # destination ground station, it will be dropped (indicated by -1)
                next_hop_decision = (-1, -1, -1)
                distance_to_ground_station_m = float("inf")
                if len(possibilities) > 0:
                    dst_sat = possibilities[0][1]
                    distance_to_ground_station_m = possibilities[0][0]

                    # If the current node is not that satellite, determine how to get to the satellite
                    if curr != dst_sat:

                        # Among its neighbors, find the one which promises the
                        # lowest distance to reach the destination satellite
                        best_distance_m = 1000000000000000
                        for neighbor_id in sat_net_graph_only_satellites_with_isls.neighbors(curr):
                            distance_m = (
                                    sat_net_graph_only_satellites_with_isls.edges[(curr, neighbor_id)]["weight"]
                                    +
                                    dist_sat_net_without_gs[(neighbor_id, dst_sat)]
                            )
                            if distance_m < best_distance_m:
                                next_hop_decision = (
                                    neighbor_id,
                                    sat_neighbor_to_if[(curr, neighbor_id)],
                                    sat_neighbor_to_if[(neighbor_id, curr)]
                                )
                                best_distance_m = distance_m

                    else:
                        # This is the destination satellite, as such the next hop is the ground station itself
                        next_hop_decision = (
                            dst_gs_node_id,
                            num_isls_per_sat[dst_sat] + gid_to_sat_gsl_if_idx[dst_gid],
                            0
                        )

                # In any case, save the distance of the satellite to the ground station to re-use
                # when we calculate ground station to ground station forwarding
                dist_satellite_to_ground_station[(curr, dst_gs_node_id)] = distance_to_ground_station_m

                # Write to forwarding state
                if not prev_fstate or prev_fstate[(curr, dst_gs_node_id)] != next_hop_decision:
                    f_out.write("%d,%d,%d,%d,%d\n" % (
                        curr,
                        dst_gs_node_id,
                        next_hop_decision[0],
                        next_hop_decision[1],
                        next_hop_decision[2]
                    ))
                fstate[(curr, dst_gs_node_id)] = next_hop_decision

        # Ground stations to ground stations
        # Choose the source satellite which promises the shortest path
        for src_gid in range(num_ground_stations):
            for dst_gid in range(num_ground_stations):
                if src_gid != dst_gid:
                    src_gs_node_id = num_satellites + src_gid
                    dst_gs_node_id = num_satellites + dst_gid

                    # Among the satellites in range of the source ground station,
                    # find the one which promises the shortest distance
                    possible_src_sats = ground_station_satellites_in_range_candidates[src_gid]
                    possibilities = []
                    for a in possible_src_sats:
                        best_distance_offered_m = dist_satellite_to_ground_station[(a[1], dst_gs_node_id)]
                        if not math.isinf(best_distance_offered_m):
                            possibilities.append(
                                (
                                    a[0] + best_distance_offered_m,
                                    a[1]
                                )
                            )
                    possibilities = sorted(possibilities)

                    # By default, if there is no satellite in range for one of the
                    # ground stations, it will be dropped (indicated by -1)
                    next_hop_decision = (-1, -1, -1)
                    if len(possibilities) > 0:
                        src_sat_id = possibilities[0][1]
                        next_hop_decision = (
                            src_sat_id,
                            0,
                            num_isls_per_sat[src_sat_id] + gid_to_sat_gsl_if_idx[src_gid]
                        )

                    # Update forwarding state
                    if not prev_fstate or prev_fstate[(src_gs_node_id, dst_gs_node_id)] != next_hop_decision:
                        f_out.write("%d,%d,%d,%d,%d\n" % (
                            src_gs_node_id,
                            dst_gs_node_id,
                            next_hop_decision[0],
                            next_hop_decision[1],
                            next_hop_decision[2]
                        ))
                    fstate[(src_gs_node_id, dst_gs_node_id)] = next_hop_decision

    # Finally return result
    return fstate


def calculate_fstate_shortest_path_with_gs_relaying(
        output_dynamic_state_dir,
        time_since_epoch_ns,
        num_satellites,
        num_ground_stations,
        sat_net_graph,
        num_isls_per_sat,
        gid_to_sat_gsl_if_idx,
        sat_neighbor_to_if,
        prev_fstate,
        enable_verbose_logs
):

    # Calculate shortest paths
    if enable_verbose_logs:
        print("  > Calculating Floyd-Warshall for graph including ground-station relays")
    # (Note: Numpy has a deprecation warning here because of how networkx uses matrices)
    dist_sat_net = nx.floyd_warshall_numpy(sat_net_graph)

    # Forwarding state
    fstate = {}

    # Now write state to file for complete graph
    output_filename = output_dynamic_state_dir + "/fstate_" + str(time_since_epoch_ns) + ".txt"
    if enable_verbose_logs:
        print("  > Writing forwarding state to: " + output_filename)
    with open(output_filename, "w+") as f_out:

        # Satellites and ground stations to ground stations
        for current_node_id in range(num_satellites + num_ground_stations):
            for dst_gid in range(num_ground_stations):
                dst_gs_node_id = num_satellites + dst_gid

                # Cannot forward to itself
                if current_node_id != dst_gs_node_id:

                    # Among its neighbors, find the one which promises the
                    # lowest distance to reach the destination satellite
                    next_hop_decision = (-1, -1, -1)
                    best_distance_m = 1000000000000000
                    for neighbor_id in sat_net_graph.neighbors(current_node_id):

                        # Any neighbor must be reachable
                        if math.isinf(dist_sat_net[(current_node_id, neighbor_id)]):
                            raise ValueError("Neighbor cannot be unreachable")

                        # Calculate distance = next-hop + distance the next hop node promises
                        distance_m = (
                            sat_net_graph.edges[(current_node_id, neighbor_id)]["weight"]
                            +
                            dist_sat_net[(neighbor_id, dst_gs_node_id)]
                        )
                        if (
                                not math.isinf(dist_sat_net[(neighbor_id, dst_gs_node_id)])
                                and
                                distance_m < best_distance_m
                        ):

                            # Check node identifiers to determine what are the
                            # correct interface identifiers
                            if current_node_id >= num_satellites and neighbor_id < num_satellites:  # GS to sat.
                                my_if = 0
                                next_hop_if = (
                                    num_isls_per_sat[neighbor_id]
                                    +
                                    gid_to_sat_gsl_if_idx[current_node_id - num_satellites]
                                )

                            elif current_node_id < num_satellites and neighbor_id >= num_satellites:  # Sat. to GS
                                my_if = (
                                    num_isls_per_sat[current_node_id]
                                    +
                                    gid_to_sat_gsl_if_idx[neighbor_id - num_satellites]
                                )
                                next_hop_if = 0

                            elif current_node_id < num_satellites and neighbor_id < num_satellites:  # Sat. to sat.
                                my_if = sat_neighbor_to_if[(current_node_id, neighbor_id)]
                                next_hop_if = sat_neighbor_to_if[(neighbor_id, current_node_id)]

                            else:  # GS to GS
                                raise ValueError("GS-to-GS link cannot exist")

                            # Write the next-hop decision
                            next_hop_decision = (
                                neighbor_id,  # Next-hop node identifier
                                my_if,        # My outgoing interface id
                                next_hop_if   # Next-hop incoming interface id
                            )

                            # Update best distance found
                            best_distance_m = distance_m

                    # Write to forwarding state
                    if not prev_fstate or prev_fstate[(current_node_id, dst_gs_node_id)] != next_hop_decision:
                        f_out.write("%d,%d,%d,%d,%d\n" % (
                            current_node_id,
                            dst_gs_node_id,
                            next_hop_decision[0],
                            next_hop_decision[1],
                            next_hop_decision[2]
                        ))
                    fstate[(current_node_id, dst_gs_node_id)] = next_hop_decision

    # Finally return result
    return fstate


def calculate_fstate_dijkstra_based(
        output_dynamic_state_dir,
        time_since_epoch_ns,
        num_satellites,
        num_ground_stations,
        sat_net_graph_only_satellites_with_isls,
        num_isls_per_sat,
        gid_to_sat_gsl_if_idx,
        ground_station_satellites_in_range_candidates,
        sat_neighbor_to_if,
        prev_fstate,
        enable_verbose_logs
):
    """
    使用 Dijkstra 算法計算 fstate - 針對分層路由優化
    
    相比 Floyd-Warshall 的優勢：
    - 時間複雜度：O(G × (V+E)logV) vs O(V³)
    - 只計算需要的路徑（衛星到地面站）
    - 充分利用受限圖的稀疏性
    
    其中 G ≈ 100 (地面站數), V ≈ 1584 (衛星數), E 取決於受限圖的邊數
    """
    
    if enable_verbose_logs:
        print("  > Calculating Dijkstra-based shortest paths (optimized for hierarchical routing)")
    
    # Forwarding state
    fstate = {}
    
    # Cache for storing distances from destination satellites
    # This avoids recalculating paths from the same destination satellite
    dst_sat_distances = {}
    
    # Now write state to file
    output_filename = output_dynamic_state_dir + "/fstate_" + str(time_since_epoch_ns) + ".txt"
    if enable_verbose_logs:
        print("  > Writing forwarding state to: " + output_filename)
    
    with open(output_filename, "w+") as f_out:
        
        # Satellites to ground stations
        dist_satellite_to_ground_station = {}
        
        # 對每個目標地面站處理
        for dst_gid in range(num_ground_stations):
            dst_gs_node_id = num_satellites + dst_gid
            possible_dst_sats = ground_station_satellites_in_range_candidates[dst_gid]
            
            if not possible_dst_sats:
                # 沒有衛星在範圍內，所有源衛星都無法到達
                for curr in range(num_satellites):
                    next_hop_decision = (-1, -1, -1)
                    dist_satellite_to_ground_station[(curr, dst_gs_node_id)] = float("inf")
                    if not prev_fstate or prev_fstate.get((curr, dst_gs_node_id)) != next_hop_decision:
                        f_out.write("%d,%d,%d,%d,%d\n" % (
                            curr, dst_gs_node_id,
                            next_hop_decision[0], next_hop_decision[1], next_hop_decision[2]
                        ))
                    fstate[(curr, dst_gs_node_id)] = next_hop_decision
                continue
            
            # 找到到達該地面站的最優目標衛星（對每個源衛星）
            # 使用反向 Dijkstra：從每個可能的目標衛星計算到所有源衛星的距離
            best_dst_sat_per_src = {}  # {src_sat: (best_dst_sat, total_distance)}
            
            for (gsl_distance, dst_sat_id) in possible_dst_sats:
                # 從這個目標衛星執行一次 Dijkstra（如果還沒計算過）
                if dst_sat_id not in dst_sat_distances:
                    try:
                        # 單源最短路徑距離
                        distances = nx.single_source_dijkstra_path_length(
                            sat_net_graph_only_satellites_with_isls,
                            dst_sat_id,
                            weight='weight'
                        )
                        dst_sat_distances[dst_sat_id] = distances
                    except nx.NetworkXError:
                        dst_sat_distances[dst_sat_id] = {}
                
                distances = dst_sat_distances[dst_sat_id]
                
                # 對每個源衛星，檢查是否這是更好的路徑
                for src_sat in range(num_satellites):
                    if src_sat in distances:
                        total_dist = distances[src_sat] + gsl_distance
                        if src_sat not in best_dst_sat_per_src or total_dist < best_dst_sat_per_src[src_sat][1]:
                            best_dst_sat_per_src[src_sat] = (dst_sat_id, total_dist)
            
            # 現在為每個源衛星建立路由
            for curr in range(num_satellites):
                next_hop_decision = (-1, -1, -1)
                distance_to_ground_station_m = float("inf")
                
                if curr in best_dst_sat_per_src:
                    dst_sat, total_dist = best_dst_sat_per_src[curr]
                    distance_to_ground_station_m = total_dist
                    
                    if curr != dst_sat:
                        # 需要找到下一跳：從 curr 到 dst_sat 的第一步
                        # 在鄰居中找到最短路徑的下一跳
                        best_distance_m = float('inf')
                        
                        for neighbor_id in sat_net_graph_only_satellites_with_isls.neighbors(curr):
                            # 計算通過這個鄰居到達目標衛星的距離
                            edge_weight = sat_net_graph_only_satellites_with_isls.edges[(curr, neighbor_id)].get("weight", 1.0)
                            
                            # 鄰居到目標衛星的距離
                            if dst_sat in dst_sat_distances.get(neighbor_id, {}):
                                neighbor_to_dst = dst_sat_distances[neighbor_id][dst_sat]
                            elif neighbor_id == dst_sat:
                                neighbor_to_dst = 0
                            else:
                                # 鄰居無法到達目標衛星，跳過
                                continue
                            
                            distance_m = edge_weight + neighbor_to_dst
                            
                            if distance_m < best_distance_m:
                                next_hop_decision = (
                                    neighbor_id,
                                    sat_neighbor_to_if[(curr, neighbor_id)],
                                    sat_neighbor_to_if[(neighbor_id, curr)]
                                )
                                best_distance_m = distance_m
                    else:
                        # 當前衛星就是目標衛星，下一跳是地面站
                        next_hop_decision = (
                            dst_gs_node_id,
                            num_isls_per_sat[dst_sat] + gid_to_sat_gsl_if_idx[dst_gid],
                            0
                        )
                
                # 保存距離供地面站到地面站使用
                dist_satellite_to_ground_station[(curr, dst_gs_node_id)] = distance_to_ground_station_m
                
                # 寫入 fstate
                if not prev_fstate or prev_fstate.get((curr, dst_gs_node_id)) != next_hop_decision:
                    f_out.write("%d,%d,%d,%d,%d\n" % (
                        curr, dst_gs_node_id,
                        next_hop_decision[0], next_hop_decision[1], next_hop_decision[2]
                    ))
                fstate[(curr, dst_gs_node_id)] = next_hop_decision
        
        # Ground stations to ground stations
        for src_gid in range(num_ground_stations):
            for dst_gid in range(num_ground_stations):
                if src_gid != dst_gid:
                    src_gs_node_id = num_satellites + src_gid
                    dst_gs_node_id = num_satellites + dst_gid
                    
                    # 在源地面站範圍內的衛星中找最優路徑
                    possible_src_sats = ground_station_satellites_in_range_candidates[src_gid]
                    possibilities = []
                    
                    for (gsl_distance, src_sat_id) in possible_src_sats:
                        # 該源衛星到目標地面站的距離
                        best_distance_offered_m = dist_satellite_to_ground_station.get(
                            (src_sat_id, dst_gs_node_id),
                            float("inf")
                        )
                        
                        if not math.isinf(best_distance_offered_m):
                            possibilities.append((
                                gsl_distance + best_distance_offered_m,
                                src_sat_id
                            ))
                    
                    possibilities = sorted(possibilities)
                    
                    # 選擇最優的源衛星
                    next_hop_decision = (-1, -1, -1)
                    if len(possibilities) > 0:
                        src_sat_id = possibilities[0][1]
                        next_hop_decision = (
                            src_sat_id,
                            0,
                            num_isls_per_sat[src_sat_id] + gid_to_sat_gsl_if_idx[src_gid]
                        )
                    
                    # 更新 fstate
                    if not prev_fstate or prev_fstate.get((src_gs_node_id, dst_gs_node_id)) != next_hop_decision:
                        f_out.write("%d,%d,%d,%d,%d\n" % (
                            src_gs_node_id, dst_gs_node_id,
                            next_hop_decision[0], next_hop_decision[1], next_hop_decision[2]
                        ))
                    fstate[(src_gs_node_id, dst_gs_node_id)] = next_hop_decision
    
    if enable_verbose_logs:
        total_dijkstra_runs = len(dst_sat_distances)
        print(f"  > Dijkstra runs: {total_dijkstra_runs} (vs Floyd-Warshall: 1 run with O(V³) complexity)")
    
    # Finally return result
    return fstate
