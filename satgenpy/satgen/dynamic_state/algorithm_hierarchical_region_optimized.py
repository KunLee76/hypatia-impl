def _ensure_complete_satellite_routing_optimized(
    fstate: Dict[Tuple[int, int], Tuple[int, int, int]],
    num_satellites: int,
    num_ground_stations: int,
    sat_net_graph: nx.Graph,
    sat_neighbor_to_if: Dict[Tuple[int, int], int],
    sat_to_group: Dict[int, int],
    group_to_master: Dict[int, int],
) -> None:
    """
    Optimized version: Only add essential routing rules to avoid O(n²) complexity.
    Focus on satellites that need routing to ground stations and masters.
    """
    
    print("Ensuring essential satellite routing (optimized)...")
    
    # Find satellites that are masters
    masters = set(group_to_master.values())
    
    # Only process satellites that need routing (masters + satellites with few routes)
    satellites_needing_routes = set()
    
    for src_sat in range(num_satellites):
        if src_sat not in sat_net_graph:
            continue
            
        # Count existing routes for this satellite
        existing_routes = sum(1 for (s, d) in fstate.keys() if s == src_sat)
        
        # Add satellite if it's a master or has very few routes
        if src_sat in masters or existing_routes < 5:
            satellites_needing_routes.add(src_sat)
    
    print(f"Processing {len(satellites_needing_routes)} satellites (out of {num_satellites})")
    
    # For each selected satellite, add essential routes
    for src_sat in satellites_needing_routes:
        src_group = sat_to_group.get(src_sat, 0)
        src_master = group_to_master.get(src_group)
        
        # Add routes to ground stations (most critical)
        for dst_gs in range(num_ground_stations):
            dst_node_id = num_satellites + dst_gs
            if (src_sat, dst_node_id) in fstate:
                continue
                
            # Route via master if not a master itself
            if src_master is not None and src_sat != src_master:
                try:
                    path = nx.shortest_path(sat_net_graph, src_sat, src_master, weight="weight")
                    if len(path) >= 2:
                        next_hop = path[1]
                        if (src_sat, next_hop) in sat_neighbor_to_if:
                            fstate[(src_sat, dst_node_id)] = (
                                next_hop,
                                sat_neighbor_to_if[(src_sat, next_hop)],
                                sat_neighbor_to_if.get((next_hop, src_sat), 0),
                            )
                except (nx.NetworkXNoPath, KeyError):
                    pass
        
        # Add routes to other masters (for inter-group communication)
        if src_sat in masters:
            for other_master in masters:
                if src_sat == other_master or (src_sat, other_master) in fstate:
                    continue
                    
                try:
                    path = nx.shortest_path(sat_net_graph, src_sat, other_master, weight="weight")
                    if len(path) >= 2:
                        next_hop = path[1]
                        if (src_sat, next_hop) in sat_neighbor_to_if:
                            fstate[(src_sat, other_master)] = (
                                next_hop,
                                sat_neighbor_to_if[(src_sat, next_hop)],
                                sat_neighbor_to_if.get((next_hop, src_sat), 0),
                            )
                except (nx.NetworkXNoPath, KeyError):
                    pass
    
    print(f"Essential routing completed. Total routes: {len(fstate)}")
