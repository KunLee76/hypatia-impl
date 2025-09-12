"""
Hierarchical routing algorithm with optional geographic region grouping.

This module extends the hierarchical routing approach by supporting dynamic grouping
of satellites based on fixed geographic regions (e.g. 5°×5° cells).
When region grouping is enabled, satellites are clustered by the sub‑satellite
positions supplied at each time step, and the smallest indexed satellite in each
cluster is elected as the master for inter‑cluster routing.

Usage:

    from .algorithm_hierarchical_region import algorithm_hierarchical_region

    # Provide ``sat_lat_lon`` as a list of (lat, lon) tuples corresponding to the
    # ground projection of each satellite at the current time.  If not provided,
    # orbit‑based grouping will be used instead.

This function returns a dictionary containing the computed forwarding state mapping.
"""

import math
import os
import networkx as nx
from typing import Dict, Iterable, List, Optional, Tuple
from astropy import units as u

from .region_grouping import assign_satellites_to_regions
from ..distance_tools import distance_m_ground_station_to_satellite


def algorithm_hierarchical_region(
    output_dynamic_state_dir: str,
    time_since_epoch_ns: int,
    satellites: Iterable,
    ground_stations: Iterable,
    sat_net_graph_only_satellites_with_isls: nx.Graph,
    ground_station_satellites_in_range: List[List[bool]],
    num_isls_per_sat: List[int],
    sat_neighbor_to_if: Dict[Tuple[int, int], int],
    list_gsl_interfaces_info: List[Dict[str, float]],
    prev_output: Optional[Dict[str, Dict[Tuple[int, int], Tuple[int, int, int]]]] = None,
    enable_verbose_logs: bool = False,
    sat_lat_lon: Optional[List[Tuple[float, float]]] = None,
    region_lat_step: float = 10.0,  # Increased to 10 degrees for proper grouping
    region_lon_step: float = 10.0,  # Increased to 10 degrees for proper grouping
    use_region_grouping: bool = True,
    fast_mode: bool = False,  # New parameter for performance optimization
) -> Dict[str, Dict[Tuple[int, int], Tuple[int, int, int]]]:
    """Compute hierarchical forwarding state with optional region grouping.
    Args:
        output_dynamic_state_dir: Directory for writing dynamic state files.
        time_since_epoch_ns: Current simulation time in nanoseconds.
        satellites: Iterable of satellite objects.
        ground_stations: Iterable of ground station objects.
        sat_net_graph_only_satellites_with_isls: Graph of satellites and ISLs (no ground stations).
        ground_station_satellites_in_range: Bool matrix of size (num_ground_stations × num_satellites).
        num_isls_per_sat: List mapping satellite index to number of ISL interfaces.
        sat_neighbor_to_if: Mapping from (satellite, neighbor) pair to interface index.
        list_gsl_interfaces_info: GSL interface metadata for satellites and ground stations.
        prev_output: Output dictionary from previous time step, used for hysteresis.
        enable_verbose_logs: Whether to print verbose debug information.
        sat_lat_lon: Optional list of (latitude, longitude) tuples representing the ground
            projection of each satellite at this time.  If provided and
            ``use_region_grouping`` is True, satellites are grouped by region.
        region_lat_step: Latitude step size for geographic grid (degrees).
        region_lon_step: Longitude step size for geographic grid (degrees).
        use_region_grouping: Whether to enable geographic region grouping.

    Returns:
        A dictionary containing the forwarding state under the key ``"fstate"``.
    """
    # Check environment variables for optimization settings
    fast_mode = fast_mode or os.environ.get('SATGEN_FAST_MODE', '').lower() in ('1', 'true', 'yes')
    use_cache = os.environ.get('SATGEN_USE_CACHE', '').lower() in ('1', 'true', 'yes')
    
    if enable_verbose_logs:
        print("\nALGORITHM: HIERARCHICAL REGION")
        if fast_mode:
            print("  > Fast mode: ENABLED")
        if use_cache:
            print("  > Cache mode: ENABLED")
    
    # Convert iterables to lists for indexing
    satellites = list(satellites)
    ground_stations = list(ground_stations)

    # Determine grouping and master satellites.
    sat_to_group: Dict[int, int] = {}
    group_to_master: Dict[int, int] = {}
    master_nodes: List[int] = []
    n_sats_per_orbit: Optional[int] = None

    # Performance optimization: track previous state for incremental updates
    region_to_sats = None
    sat_to_region_cache = None
    should_recompute_grouping = True
    prev_masters = None
    
    # Check if we can reuse previous grouping (for fast mode or cache mode)
    if (fast_mode or use_cache) and prev_output and "region_to_sats" in prev_output:
        # In fast/cache mode, only recompute grouping occasionally
        if time_since_epoch_ns % (10 * 100000000) != 0:  # Every 1 second instead of 100ms
            should_recompute_grouping = False
            region_to_sats = prev_output["region_to_sats"]
            sat_to_region_cache = prev_output.get("sat_to_region_cache")
    
    if prev_output and "group_to_master" in prev_output:
        prev_masters = prev_output["group_to_master"]

    if use_region_grouping and sat_lat_lon is not None:
        # Assign satellites to geographic regions and select masters.
        if should_recompute_grouping:
            sat_to_group, region_to_sats = assign_satellites_to_regions(
                sat_lat_lon, lat_step=region_lat_step, lon_step=region_lon_step
            )
            
            # Enhanced debugging for region grouping
            if enable_verbose_logs:
                print(f"  > REGION_DEBUG: Using grid size {region_lat_step}° × {region_lon_step}°")
                print(f"  > REGION_DEBUG: Total regions created: {len(region_to_sats)}")
                print(f"  > REGION_DEBUG: Total satellites assigned: {len(sat_to_group)}")
                
                # Show sample satellite positions
                if sat_lat_lon:
                    print(f"  > REGION_DEBUG: Sample satellite positions:")
                    for i, (lat, lon) in enumerate(sat_lat_lon[:10]):
                        print(f"    SAT-{i}: ({lat:6.2f}°, {lon:7.2f}°)")
                    
                    # Show position statistics
                    lats = [pos[0] for pos in sat_lat_lon]
                    lons = [pos[1] for pos in sat_lat_lon]
                    print(f"  > REGION_DEBUG: Lat range: {min(lats):.2f}° to {max(lats):.2f}° (span: {max(lats)-min(lats):.2f}°)")
                    print(f"  > REGION_DEBUG: Lon range: {min(lons):.2f}° to {max(lons):.2f}° (span: {max(lons)-min(lons):.2f}°)")
                
                # Show region distribution
                region_sizes = [len(sats) for sats in region_to_sats.values()]
                if region_sizes:
                    print(f"  > REGION_DEBUG: Region sizes - min: {min(region_sizes)}, max: {max(region_sizes)}, avg: {sum(region_sizes)/len(region_sizes):.1f}")
                
                # Show sample regions
                for i, (region_id, sat_ids) in enumerate(list(region_to_sats.items())[:5]):
                    print(f"  > REGION_DEBUG: Region {region_id}: {len(sat_ids)} satellites {sat_ids[:3]}{'...' if len(sat_ids) > 3 else ''}")
            
            # Build satellite to region cache for performance
            sat_to_region_cache = {}
            for region_id, sat_ids in region_to_sats.items():
                for sat_id in sat_ids:
                    sat_to_region_cache[sat_id] = region_id
        else:
            # Use cached grouping and build sat_to_group from region_to_sats
            sat_to_group = {}
            for region_id, sat_ids in region_to_sats.items():
                for sat_id in sat_ids:
                    sat_to_group[sat_id] = region_id
        
        # Use connectivity-based master selection for better inter-region routing
        group_to_master = select_regional_master_by_connectivity(
            region_to_sats, 
            sat_net_graph_only_satellites_with_isls,
            prev_masters,
            fast_mode,
            sat_to_region_cache
        )
        master_nodes = list(group_to_master.values())
        
        if enable_verbose_logs:
            print(f"  > Geographic grouping: {len(region_to_sats)} regions, masters: {master_nodes}")
            # Debug: Check region-to-master consistency
            print(f"  > DEBUG: region_to_sats has {len(region_to_sats)} regions")
            print(f"  > DEBUG: group_to_master has {len(group_to_master)} masters")
            print(f"  > DEBUG: unique masters count: {len(set(master_nodes))}")
            print(f"  > DEBUG: sat_net_graph has {len(sat_net_graph_only_satellites_with_isls.nodes())} satellites with ISLs")
            
            # Check region size distribution
            region_sizes = [len(sat_list) for sat_list in region_to_sats.values()]
            print(f"  > DEBUG: region sizes - min: {min(region_sizes)}, max: {max(region_sizes)}, avg: {sum(region_sizes)/len(region_sizes):.1f}")
            
            # Check total satellites in regions
            total_sats_in_regions = sum(region_sizes)
            print(f"  > DEBUG: total satellites in all regions: {total_sats_in_regions}")
            
            # Check for empty regions
            empty_regions = sum(1 for sat_list in region_to_sats.values() if not sat_list)
            non_empty_regions = len(region_to_sats) - empty_regions
            print(f"  > DEBUG: empty regions: {empty_regions}, non-empty: {non_empty_regions}")
        
        # Since the grouping is geographic, ``n_sats_per_orbit`` is not used.
    else:
        # Fallback to traditional orbit‑plane grouping.
        n_orbits, n_sats_per_orbit = _infer_orbit_structure(satellites)
        # Build sat_to_group mapping based on orbit structure.
        for sid in range(len(satellites)):
            sat_to_group[sid] = sid // n_sats_per_orbit
        master_nodes = select_master_nodes(satellites, n_orbits, n_sats_per_orbit)
        group_to_master = {grp: master for grp, master in enumerate(master_nodes)}

    # Compute inter‑group forwarding state (master to master).
    master_fstate = compute_master_forwarding(
        sat_net_graph_only_satellites_with_isls, master_nodes, sat_neighbor_to_if
    )

    # Compute intra‑group forwarding state (master to group members).
    group_fstate = compute_intra_group_paths(
        satellites, master_nodes, sat_net_graph_only_satellites_with_isls,
        # If orbit grouping, n_sats_per_orbit is defined; for region grouping we set it to 1
        n_sats_per_orbit if n_sats_per_orbit is not None else 1,
        sat_neighbor_to_if
    )

    # Merge master and group forwarding tables.
    fstate = merge_fstate(master_fstate, group_fstate)

    # --------
    # Interface bandwidth state output (unchanged from original algorithm).
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
                    f_out.write(f"{node_id},{if_id},{bw}\n")

    gid_to_sat_gsl_if_idx = [0] * len(ground_stations)
    prev_fstate = None
    if prev_output is not None:
        prev_fstate = prev_output.get("fstate")

    # Compute hierarchical path between ground stations via masters.
    gs_fstate = calculate_hierarchical_path_through_masters(
        time_since_epoch_ns,
        len(satellites),
        len(ground_stations),
        sat_net_graph_only_satellites_with_isls,
        num_isls_per_sat,
        gid_to_sat_gsl_if_idx,
        ground_station_satellites_in_range,
        sat_neighbor_to_if,
        enable_verbose_logs,
        sat_to_group,
        group_to_master,
        fast_mode=fast_mode,  # Pass fast_mode to the calculation function
        satellites=satellites,
        ground_stations=ground_stations,
        epoch=None,  # TODO: Need to get epoch from caller
        max_gsl_length_m=None,  # TODO: Need to get max_gsl_length_m from config
    )

    # Combine satellite‑to‑satellite and ground‑station related forwarding state.
    if enable_verbose_logs:
        print(f"  > Generated {len(gs_fstate)} ground station routes")
        # Show a few example routes
        gs_examples = list(gs_fstate.items())[:5]
        for (src, dst), (next_hop, src_if, dst_if) in gs_examples:
            print(f"    Route {src}→{dst}: next_hop={next_hop}")
    fstate.update(gs_fstate)

    # Debug: Check fstate before writing to file
    if enable_verbose_logs and (625, 626) in fstate:
        route_info = fstate[(625, 626)]
        print(f"    Route 625→626: next_hop={route_info[0]}")

    # --------
    # Output forwarding state table.
    # --------
    fstate_filename = output_dynamic_state_dir + f"/fstate_{time_since_epoch_ns}.txt"
    write_fstate_to_file(fstate, fstate_filename)

    # Return state with caching information for performance optimization
    result = {"fstate": fstate}
    
    # Include caching information for next iteration
    if use_region_grouping and region_to_sats is not None:
        result["region_to_sats"] = region_to_sats
        result["group_to_master"] = group_to_master
        if sat_to_region_cache is not None:
            result["sat_to_region_cache"] = sat_to_region_cache

    return result


def select_optimal_uplink_satellite(
    reachable_sats: List[int],
    target_group: int,
    sat_to_group: Dict[int, int],
    group_to_master: Dict[int, int],
    sat_net_graph: nx.Graph,
    ground_station_id: int = None,
    ground_stations = None,
    satellites = None,
    epoch = None,
    time_since_epoch_ns: int = 0,
    max_gsl_length_m: float = None,
    enable_verbose_logs: bool = False
) -> int:
    """Select the optimal uplink satellite based on group connectivity.
    
    Priority order:
    1. Satellite in the same group as the target
    2. Satellite whose group master has direct connection to target group master
    3. Satellite with shortest path to target group master
    4. Satellite with most connections (highest degree)
    5. Fallback to first reachable satellite
    
    Args:
        reachable_sats: List of satellites reachable from the ground station
        target_group: Group ID of the target ground station's satellite
        sat_to_group: Mapping from satellite ID to group ID
        group_to_master: Mapping from group ID to master satellite ID
        sat_net_graph: Satellite network graph
    
    Returns:
        Selected satellite ID for uplink
    """
    if not reachable_sats:
        raise ValueError("No reachable satellites provided")
    
    # Filter out satellites that are too far (exceed GSL range)
    valid_reachable_sats = reachable_sats
    if (ground_station_id is not None and ground_stations is not None and 
        satellites is not None and epoch is not None and max_gsl_length_m is not None):
        
        valid_reachable_sats = []
        time = epoch + time_since_epoch_ns * u.ns
        ground_station = ground_stations[ground_station_id]
        
        for sat_id in reachable_sats:
            try:
                distance_m = distance_m_ground_station_to_satellite(
                    ground_station, satellites[sat_id], str(epoch), str(time)
                )
                if distance_m <= max_gsl_length_m:
                    valid_reachable_sats.append(sat_id)
                else:
                    if enable_verbose_logs:
                        print(f"Warning: Satellite {sat_id} too far from GS {ground_station_id}: {distance_m:.0f}m > {max_gsl_length_m:.0f}m")
            except Exception as e:
                if enable_verbose_logs:
                    print(f"Warning: Failed to compute distance from GS {ground_station_id} to satellite {sat_id}: {e}")
                # If distance computation fails, exclude this satellite for safety
                continue
        
        if not valid_reachable_sats:
            # If no satellites are within range, fall back to original list but issue warning
            print(f"Warning: No satellites within GSL range for GS {ground_station_id}, using closest available")
            valid_reachable_sats = reachable_sats
    
    target_master = group_to_master.get(target_group)
    
    # Priority 1: Satellite in the same group as target
    same_group_sats = [sat for sat in valid_reachable_sats 
                       if sat_to_group.get(sat, 0) == target_group]
    if same_group_sats:
        return same_group_sats[0]
    
    # Priority 2: Satellite whose group master has direct connection to target master
    if target_master is not None:
        for sat in valid_reachable_sats:
            sat_group = sat_to_group.get(sat, 0)
            sat_master = group_to_master.get(sat_group)
            if (sat_master is not None and 
                sat_master in sat_net_graph and 
                target_master in sat_net_graph and
                sat_net_graph.has_edge(sat_master, target_master)):
                return sat
    
    # Priority 3: Satellite with shortest path to target master
    if target_master is not None:
        best_sat = None
        min_distance = float('inf')
        
        for sat in valid_reachable_sats:
            if sat not in sat_net_graph or target_master not in sat_net_graph:
                continue
            try:
                distance = nx.shortest_path_length(
                    sat_net_graph, sat, target_master, weight="weight"
                )
                if distance < min_distance:
                    min_distance = distance
                    best_sat = sat
            except nx.NetworkXNoPath:
                continue
        
        if best_sat is not None:
            return best_sat
    
    # Priority 4: Satellite with most connections (highest degree)
    # This helps select well-connected satellites that can reach more destinations
    best_sat = None
    max_degree = -1
    
    for sat in valid_reachable_sats:
        if sat in sat_net_graph:
            degree = sat_net_graph.degree(sat)
            if degree > max_degree:
                max_degree = degree
                best_sat = sat
    
    if best_sat is not None:
        return best_sat
    
    # Priority 5: Fallback to first reachable satellite
    return valid_reachable_sats[0]


def calculate_hierarchical_path_through_masters(
    time_since_epoch_ns: int,
    num_satellites: int,
    num_ground_stations: int,
    sat_net_graph_only_satellites_with_isls: nx.Graph,
    num_isls_per_sat: List[int],
    gid_to_sat_gsl_if_idx: List[int],
    ground_station_satellites_in_range: List[List[bool]],
    sat_neighbor_to_if: Dict[Tuple[int, int], int],
    enable_verbose_logs: bool,
    sat_to_group: Dict[int, int],
    group_to_master: Dict[int, int],
    fast_mode: bool = False,
    satellites = None,
    ground_stations = None,
    epoch = None,
    max_gsl_length_m: float = None,
) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    """Compute forwarding state between ground stations via hierarchical routing.

    This function extends the original hierarchical path computation by accepting
    precomputed mappings from satellites to groups and from groups to masters.
    If ``sat_to_group`` and ``group_to_master`` are provided from a geographic
    grouping scheme, they will be used directly.  Otherwise, when orbit‑plane
    grouping is in effect, callers should supply the appropriate mappings.
    """
    if enable_verbose_logs:
        print(
            "  > Calculating forwarding state for ground stations "
            "(hierarchical with flexible uplink)"
        )

    fstate: Dict[Tuple[int, int], Tuple[int, int, int]] = {}

    # Determine which satellites belong to which group based on provided mapping.
    # sat_to_group maps satellite ID to group ID.  group_to_master maps group ID
    # to the master satellite ID for that group.

    # Determine reachable satellites for each ground station.
    gs_to_reachable_sats: Dict[int, List[int]] = {}
    for gid in range(num_ground_stations):
        sat_id_list: List[int] = []
        if gid < len(ground_station_satellites_in_range):
            # ground_station_satellites_in_range[gid] is a list of (distance_m, sid) tuples
            for (distance_m, sid) in ground_station_satellites_in_range[gid]:
                sat_id_list.append(sid)
        gs_to_reachable_sats[gid] = sat_id_list

    # Compute forwarding paths for each pair of ground stations.
    total_pairs = num_ground_stations * (num_ground_stations - 1)
    computed_pairs = 0
    
    if fast_mode:
        # In fast mode, compute routes for all ground stations but use optimization techniques
        # This ensures connectivity while still providing performance benefits
        if enable_verbose_logs:
            print(f"  > Fast mode enabled: Computing routes for all {num_ground_stations} ground stations with optimizations")
    
    for src_gid in range(num_ground_stations):
        for dst_gid in range(num_ground_stations):
            if src_gid == dst_gid:
                continue
                
            # In fast mode, we still compute all routes but use other optimizations
                continue
                
            src_node_id = num_satellites + src_gid
            dst_node_id = num_satellites + dst_gid
            src_reachable = gs_to_reachable_sats.get(src_gid, [])
            dst_reachable = gs_to_reachable_sats.get(dst_gid, [])
            if not src_reachable or not dst_reachable:
                continue
            
            computed_pairs += 1
            
            # Improved satellite selection based on group optimization
            dst_sat = dst_reachable[0]  # Keep destination satellite selection simple
            dst_group = sat_to_group.get(dst_sat, 0)
            
            # Generic route diversity strategy for all ground station pairs
            # Use a deterministic but varied approach based on source and destination IDs
            route_diversity_factor = (src_gid + dst_gid) % 3
            
            if route_diversity_factor == 0:
                # Strategy 1: Use destination satellite's group (direct approach)
                target_group = dst_group
            elif route_diversity_factor == 1:
                # Strategy 2: Prefer alternative group from reachable satellites (diversity)
                alt_groups = [sat_to_group.get(s, 0) for s in src_reachable if sat_to_group.get(s, 0) != dst_group]
                target_group = alt_groups[0] if alt_groups else dst_group
            else:
                # Strategy 3: Use the most connected group among reachable satellites
                group_connectivity = {}
                for sat in src_reachable:
                    group = sat_to_group.get(sat, 0)
                    if group not in group_connectivity:
                        group_connectivity[group] = 0
                    # Count satellites in this group that are reachable
                    group_connectivity[group] += 1
                
                # Select group with most reachable satellites
                if group_connectivity:
                    target_group = max(group_connectivity, key=group_connectivity.get)
                else:
                    target_group = dst_group
            
            # For source satellite, prefer one that can reach the target group efficiently
            src_sat = select_optimal_uplink_satellite(
                src_reachable, target_group, sat_to_group, group_to_master, 
                sat_net_graph_only_satellites_with_isls,
                ground_station_id=src_gid,
                ground_stations=ground_stations,
                satellites=satellites,
                epoch=epoch,
                time_since_epoch_ns=time_since_epoch_ns,
                max_gsl_length_m=max_gsl_length_m,
                enable_verbose_logs=enable_verbose_logs
            )
            
            if enable_verbose_logs and (src_gid < 10 and dst_gid < 10):  # Debug first 10 ground stations
                src_groups = [sat_to_group.get(s, -1) for s in src_reachable[:5]]
                print(f"DEBUG: GS {src_gid} -> GS {dst_gid}: selected sat {src_sat}, strategy {route_diversity_factor}, target_group {target_group}, reachable groups: {src_groups}")
                # Enable verbose logging for specific ground station pairs
                # if enable_verbose_logs and src_gid in [0, 1, 2]:  # Example: Tokyo, Delhi, Shanghai
            src_group = sat_to_group.get(src_sat, 0)
            dst_group = sat_to_group.get(dst_sat, 0)
            # Link from ground station to its uplink satellite.
            fstate[(src_node_id, dst_node_id)] = (
                src_sat,
                gid_to_sat_gsl_if_idx[src_gid],
                num_isls_per_sat[src_sat] + 0,
            )
            if src_group == dst_group:
                # Same group: route directly within the group.
                try:
                    path = nx.shortest_path(
                        sat_net_graph_only_satellites_with_isls,
                        src_sat,
                        dst_sat,
                        weight="weight",
                    )
                    for i in range(len(path) - 1):
                        curr = path[i]
                        nxt = path[i + 1]
                        if (curr, nxt) not in fstate:
                            fstate[(curr, nxt)] = (
                                nxt,
                                sat_neighbor_to_if[(curr, nxt)],
                                sat_neighbor_to_if[(nxt, curr)],
                            )
                    # Final hop down to the destination ground station.
                    try:
                        # Find the index of dst_sat in the ground station's reachable satellites list
                        downlink_idx = next(i for i, (_, sid) in enumerate(ground_station_satellites_in_range[dst_gid]) if sid == dst_sat)
                    except (ValueError, StopIteration):
                        continue
                    fstate[(dst_sat, dst_node_id)] = (
                        dst_node_id,
                        num_isls_per_sat[dst_sat] + downlink_idx,
                        gid_to_sat_gsl_if_idx[dst_gid],
                    )
                except nx.NetworkXNoPath:
                    continue
            else:
                # Different groups: route via masters.
                src_master = group_to_master.get(src_group)
                dst_master = group_to_master.get(dst_group)
                # 1. src_sat -> src_master
                if src_master is not None and src_sat != src_master:
                    try:
                        path1 = nx.shortest_path(
                            sat_net_graph_only_satellites_with_isls,
                            src_sat,
                            src_master,
                            weight="weight",
                        )
                        for i in range(len(path1) - 1):
                            curr = path1[i]
                            nxt = path1[i + 1]
                            if (curr, nxt) not in fstate:
                                fstate[(curr, nxt)] = (
                                    nxt,
                                    sat_neighbor_to_if[(curr, nxt)],
                                    sat_neighbor_to_if[(nxt, curr)],
                                )
                    except nx.NetworkXNoPath:
                        pass
                # 2. src_master -> dst_master
                if src_master is not None and dst_master is not None:
                    try:
                        path2 = nx.shortest_path(
                            sat_net_graph_only_satellites_with_isls,
                            src_master,
                            dst_master,
                            weight="weight",
                        )
                        for i in range(len(path2) - 1):
                            curr = path2[i]
                            nxt = path2[i + 1]
                            if (curr, nxt) not in fstate:
                                fstate[(curr, nxt)] = (
                                    nxt,
                                    sat_neighbor_to_if[(curr, nxt)],
                                    sat_neighbor_to_if[(nxt, curr)],
                                )
                    except nx.NetworkXNoPath:
                        pass
                # 3. dst_master -> dst_sat
                if dst_master is not None and dst_master != dst_sat:
                    try:
                        path3 = nx.shortest_path(
                            sat_net_graph_only_satellites_with_isls,
                            dst_master,
                            dst_sat,
                            weight="weight",
                        )
                        for i in range(len(path3) - 1):
                            curr = path3[i]
                            nxt = path3[i + 1]
                            if (curr, nxt) not in fstate:
                                fstate[(curr, nxt)] = (
                                    nxt,
                                    sat_neighbor_to_if[(curr, nxt)],
                                    sat_neighbor_to_if[(nxt, curr)],
                                )
                    except nx.NetworkXNoPath:
                        pass
                # 4. Downlink from dst_sat to ground station.
                try:
                    # Find the index of dst_sat in the ground station's reachable satellites list
                    downlink_idx = next(i for i, (_, sid) in enumerate(ground_station_satellites_in_range[dst_gid]) if sid == dst_sat)
                except (ValueError, StopIteration):
                    continue
                fstate[(dst_sat, dst_node_id)] = (
                    dst_node_id,
                    num_isls_per_sat[dst_sat] + downlink_idx,
                    gid_to_sat_gsl_if_idx[dst_gid],
                )

    # Fix: Ensure uplink satellites have routing to all ground stations
    # This is essential for satellite-to-ground communication
    # _ensure_uplink_satellite_routing(
    #     fstate, 
    #     num_satellites, 
    #     num_ground_stations, 
    #     sat_net_graph_only_satellites_with_isls,
    #     sat_neighbor_to_if,
    #     sat_to_group,
    #     group_to_master
    # )
    
    # New approach: Generate downlink routes for all satellites directly
    print("Generating satellite-to-ground station downlink routes...")
    # print(f"DEBUG: num_satellites={num_satellites}, num_ground_stations={num_ground_stations}")
    downlink_routes_added = 0
    
    for sat_id in range(num_satellites):
        for gid in range(num_ground_stations):
            gs_node_id = num_satellites + gid
            
            # Check if this satellite can connect to this ground station directly
            sat_can_reach_gs = any(sid == sat_id for (_, sid) in ground_station_satellites_in_range[gid])
            if sat_can_reach_gs:
                # Direct downlink connection - satellite to ground station
                try:
                    # Find the index of this satellite in the reachable list for this ground station
                    satellite_index = next(idx for idx, (_, sid) in enumerate(ground_station_satellites_in_range[gid]) if sid == sat_id)
                    
                    # Only create satellite->ground_station routes, not ground_station->ground_station
                    if sat_id < num_satellites:  # Ensure sat_id is actually a satellite
                        # if sat_id >= 625 or gs_node_id <= 625:  # Debug check
                            # print(f"DEBUG: Suspicious route creation: sat_id={sat_id}, gs_node_id={gs_node_id}")
                        fstate[(sat_id, gs_node_id)] = (
                            gs_node_id,
                            num_isls_per_sat[sat_id] + 0,  # Use interface 0 for GSL
                            gid_to_sat_gsl_if_idx[gid],
                        )
                        downlink_routes_added += 1
                except (ValueError, IndexError) as e:
                    print(f"Error creating route {sat_id}→{gs_node_id}: {e}")
                    continue
    
    print(f"Added {downlink_routes_added} direct satellite-to-ground station routes")
    
    # Generate indirect satellite-to-ground station routes (essential for connectivity)
    indirect_routes_added = 0
    print("Generating comprehensive indirect satellite-to-ground station routes...")
    
    # We need to add indirect routes for ALL satellites that might be in routing paths
    # This includes:
    # 1. Uplink satellites (first hop from ground stations)
    # 2. Intermediate satellites in routing paths between satellites
    
    # Get all satellites that are reachable in the ISL graph
    all_satellites_in_isl = set(sat_net_graph_only_satellites_with_isls.nodes())
    
    print(f"Processing {len(all_satellites_in_isl)} satellites for comprehensive indirect routes")
    
    for sat_id in all_satellites_in_isl:
        for gid in range(num_ground_stations):
            gs_node_id = num_satellites + gid
            
            # Skip if direct route already exists
            if (sat_id, gs_node_id) in fstate:
                continue
                
            # Find a satellite that can directly reach this ground station
            direct_satellites = []
            for (_, direct_sat_id) in ground_station_satellites_in_range[gid]:
                direct_satellites.append(direct_sat_id)
            
            if not direct_satellites:
                continue  # No satellite can reach this ground station
                
            # Find path using satellite-only ISL graph
            for target_sat in direct_satellites[:3]:  # Try top 3 candidates
                try:
                    # Get next hop from satellite ISL graph
                    path = nx.shortest_path(sat_net_graph_only_satellites_with_isls, sat_id, target_sat)
                    if len(path) >= 2:
                        next_hop = path[1]  # Next satellite in the path
                        
                        fstate[(sat_id, gs_node_id)] = (
                            next_hop,
                            sat_neighbor_to_if.get((sat_id, next_hop), 0),
                            3   # Hop type: ISL to another satellite
                        )
                        indirect_routes_added += 1
                        break
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue  # Try next candidate
    
    print(f"Added {indirect_routes_added} essential indirect satellite-to-ground station routes")

    return fstate


def _ensure_uplink_satellite_routing(
    fstate: Dict[Tuple[int, int], Tuple[int, int, int]],
    num_satellites: int,
    num_ground_stations: int,
    sat_net_graph: nx.Graph,
    sat_neighbor_to_if: Dict[Tuple[int, int], int],
    sat_to_group: Dict[int, int],
    group_to_master: Dict[int, int],
) -> None:
    """Ensure uplink satellites can route to ground stations."""
    
    print("Ensuring uplink satellite routing to ground stations...")
    
    # Find satellites that are actually used as uplinks in ground station routes
    uplink_satellites = set()
    for (src, dst), (next_hop, if_idx, distance) in fstate.items():
        if src >= num_satellites and dst >= num_satellites:  # Ground station to ground station
            uplink_satellites.add(next_hop)  # The satellite used as next hop
    
    print(f"Found {len(uplink_satellites)} uplink satellites: {sorted(uplink_satellites)}")
    
    # Simple approach: For each uplink satellite, use existing downlink routes from fstate
    # and try to route through intermediate satellites if direct routes don't exist
    
    routes_added = 0
    for sat_id in uplink_satellites:
        for dst_gs in range(num_satellites, num_satellites + num_ground_stations):
            if (sat_id, dst_gs) not in fstate:
                # Strategy 1: Find a direct route if this satellite can reach the ground station
                # by checking if there's already a route from this satellite to this GS
                found_route = False
                
                # Strategy 2: Find any satellite that has a route to this ground station
                # and route through it
                for candidate_sat in range(num_satellites):
                    if (candidate_sat, dst_gs) in fstate:
                        # This satellite has a route to the destination GS
                        if sat_id in sat_net_graph and candidate_sat in sat_net_graph.neighbors(sat_id):
                            # Direct connection to candidate satellite
                            if_idx = sat_neighbor_to_if.get((sat_id, candidate_sat), 0)
                            fstate[(sat_id, dst_gs)] = (candidate_sat, if_idx, 2)  # 2 hops: sat->candidate->GS
                            routes_added += 1
                            found_route = True
                            print(f"Route {sat_id}→{dst_gs}: next_hop={candidate_sat} (via neighbor)")
                            break
                        elif sat_id in sat_net_graph and candidate_sat in sat_net_graph:
                            # Find shortest path to candidate satellite
                            try:
                                path = nx.shortest_path(sat_net_graph, sat_id, candidate_sat, weight="weight")
                                if len(path) >= 2:
                                    next_hop = path[1]
                                    if_idx = sat_neighbor_to_if.get((sat_id, next_hop), 0)
                                    distance = len(path)  # path length to candidate + 1 for GS
                                    fstate[(sat_id, dst_gs)] = (next_hop, if_idx, distance)
                                    routes_added += 1
                                    found_route = True
                                    print(f"Route {sat_id}→{dst_gs}: next_hop={next_hop} (path length {distance})")
                                    break
                            except nx.NetworkXNoPath:
                                continue
                
                if not found_route:
                    print(f"No path found from satellite {sat_id} to ground station {dst_gs}")
    
    print(f"Added {routes_added} satellite-to-ground station routes. Total routes now: {len(fstate)}")


def _ensure_complete_satellite_routing(
    fstate: Dict[Tuple[int, int], Tuple[int, int, int]],
    num_satellites: int,
    num_ground_stations: int,
    sat_net_graph: nx.Graph,
    sat_neighbor_to_if: Dict[Tuple[int, int], int],
    sat_to_group: Dict[int, int],
    group_to_master: Dict[int, int],
) -> None:
    """Optimized: Ensure essential satellite routing without O(n²) complexity."""
    
    print("Ensuring essential satellite routing (optimized)...")
    
    # Only process satellites that actually need routing
    satellites_needing_routes = set()
    
    # Find satellites that are masters or have special roles
    masters = set(group_to_master.values())
    
    # Find satellites that might be used for uplink/downlink (those with limited existing routes)
    for src_sat in range(num_satellites):
        if src_sat not in sat_net_graph:
            continue
            
        # Count existing routes for this satellite
        existing_routes = sum(1 for (s, d) in fstate.keys() if s == src_sat)
        
        # If satellite has very few routes or is a master, it needs processing
        if existing_routes < 10 or src_sat in masters:
            satellites_needing_routes.add(src_sat)
    
    print(f"Processing {len(satellites_needing_routes)} satellites needing routes (out of {num_satellites})")
    
    for src_sat in satellites_needing_routes:
        src_group = sat_to_group.get(src_sat, 0)
        src_master = group_to_master.get(src_group)
        
        # Only add routes to ground stations (most critical for connectivity)
        for dst_gs in range(num_ground_stations):
            dst_node_id = num_satellites + dst_gs  # Ground station node ID
            if (src_sat, dst_node_id) in fstate:
                continue  # Already has a route
                
            try:
                if src_master is not None and src_sat != src_master:
                    # Route via master first
                    path = nx.shortest_path(sat_net_graph, src_sat, src_master, weight="weight")
                    if len(path) >= 2:
                        next_hop = path[1]
                        if (src_sat, next_hop) in sat_neighbor_to_if and (next_hop, src_sat) in sat_neighbor_to_if:
                            fstate[(src_sat, dst_node_id)] = (
                                next_hop,
                                sat_neighbor_to_if[(src_sat, next_hop)],
                                sat_neighbor_to_if[(next_hop, src_sat)],
                            )
                else:
                    # This satellite is the master, add direct routes to nearby satellites that can reach GS
                    # Only add routes to immediate neighbors to avoid expensive computation
                    if src_sat in sat_net_graph:
                        neighbors = list(sat_net_graph.neighbors(src_sat))
                        for neighbor in neighbors[:5]:  # Limit to first 5 neighbors
                            if (neighbor, dst_node_id) in fstate:
                                # Neighbor has route to GS, route through it
                                if (src_sat, neighbor) in sat_neighbor_to_if and (neighbor, src_sat) in sat_neighbor_to_if:
                                    fstate[(src_sat, dst_node_id)] = (
                                        neighbor,
                                        sat_neighbor_to_if[(src_sat, neighbor)],
                                        sat_neighbor_to_if[(neighbor, src_sat)],
                                    )
                                    break
                            
            except (nx.NetworkXNoPath, KeyError):
                continue
        
        # Add routes to other group masters only (not all satellites)
        for other_master in masters:
            if src_sat == other_master:
                continue
            if (src_sat, other_master) in fstate:
                continue
                
            try:
                path = nx.shortest_path(sat_net_graph, src_sat, other_master, weight="weight")
                if len(path) >= 2:
                    next_hop = path[1]
                    if (src_sat, next_hop) in sat_neighbor_to_if and (next_hop, src_sat) in sat_neighbor_to_if:
                        fstate[(src_sat, other_master)] = (
                            next_hop,
                            sat_neighbor_to_if[(src_sat, next_hop)],
                            sat_neighbor_to_if[(next_hop, src_sat)],
                        )
            except (nx.NetworkXNoPath, KeyError):
                continue
    
    print(f"Essential satellite routing completed. Total routes: {len(fstate)}")


# Helper functions reused from the original hierarchical algorithm.  These are
# duplicated here to avoid a dependency cycle.  They are functionally identical
# to those in algorithm_hierarchical.py.


def _infer_orbit_structure(satellites: Iterable) -> Tuple[int, int]:
    """Infer the number of orbits and satellites per orbit from TLE data.

    This helper inspects the RAAN (Right Ascension of the Ascending Node) values of
    satellites to determine how many unique orbits are present.  It assumes that
    satellites are sorted by RAAN.
    """
    raans = sorted({round(s._raan, 6) for s in satellites})
    n_orbits = len(raans) if raans else 1
    if len(satellites) % n_orbits != 0:
        raise ValueError("Cannot infer satellites per orbit from TLEs")
    return n_orbits, len(satellites) // n_orbits


def select_master_nodes(
    satellites: Iterable, n_orbits: int, n_sats_per_orbit: int
) -> List[int]:
    """Select one master satellite per orbit by choosing the first satellite in each orbit."""
    if len(satellites) != n_orbits * n_sats_per_orbit:
        raise ValueError("satellites' number error")
    masters: List[int] = []
    for orbit_id in range(n_orbits):
        master_sid = orbit_id * n_sats_per_orbit
        masters.append(master_sid)
    return masters


def select_regional_master_by_connectivity(
    region_to_sats: Dict[int, List[int]],
    sat_net_graph: nx.Graph,
    group_to_current_master: Optional[Dict[int, int]] = None,
    fast_mode: bool = False,
    sat_to_region_cache: Optional[Dict[int, int]] = None
) -> Dict[int, int]:
    """Select master satellites for each region based on connectivity.
    
    Instead of simply choosing the smallest satellite ID, this function selects
    the satellite with the best inter-region connectivity as the master.
    
    Args:
        region_to_sats: Mapping from region ID to list of satellite IDs in that region.
        sat_net_graph: Graph containing satellites and their ISL connections.
        group_to_current_master: Optional current master assignments for stability.
        fast_mode: If True, use simplified and faster master selection.
        sat_to_region_cache: Pre-computed mapping from satellite ID to region ID.
    
    Returns:
        Mapping from region ID to selected master satellite ID.
    """
    region_to_master: Dict[int, int] = {}
    
    # Build satellite to region mapping if not provided
    if sat_to_region_cache is None:
        sat_to_region_cache = {}
        for region_id, sat_ids in region_to_sats.items():
            for sat_id in sat_ids:
                sat_to_region_cache[sat_id] = region_id
    
    empty_regions_count = 0
    processed_regions_count = 0
    empty_region_ids = []
    
    for region_id, sat_ids in region_to_sats.items():
        if not sat_ids:
            empty_regions_count += 1
            empty_region_ids.append(region_id)
            continue
        
        processed_regions_count += 1
        
        # Fast mode: simple fallback strategies
        if fast_mode:
            # Strategy 1: Keep current master if available and still in region
            if (group_to_current_master and 
                region_id in group_to_current_master and 
                group_to_current_master[region_id] in sat_ids):
                region_to_master[region_id] = group_to_current_master[region_id]
                continue
            
            # Strategy 2: Choose satellite with most ISL connections (quick)
            best_master = None
            max_connections = -1
            for sat_id in sat_ids:
                if sat_id in sat_net_graph:
                    connections = len(list(sat_net_graph.neighbors(sat_id)))
                    if connections > max_connections:
                        max_connections = connections
                        best_master = sat_id
            
            # Strategy 3: Fallback to smallest ID
            if best_master is None:
                best_master = min(sat_ids)
            
            region_to_master[region_id] = best_master
            continue
            
        # Full mode: detailed connectivity analysis
        best_master = None
        max_connectivity = -1
        
        # Evaluate each satellite in the region
        for sat_id in sat_ids:
            if sat_id not in sat_net_graph:
                continue
                
            # Calculate connectivity score based on:
            # 1. Number of direct ISL connections
            # 2. Connectivity to other regions' satellites
            direct_neighbors = len(list(sat_net_graph.neighbors(sat_id)))
            
            # Count connections to satellites in other regions (optimized)
            inter_region_connections = 0
            for neighbor in sat_net_graph.neighbors(sat_id):
                neighbor_region = sat_to_region_cache.get(neighbor)
                if neighbor_region is not None and neighbor_region != region_id:
                    inter_region_connections += 1
            
            # Connectivity score: weight inter-region connections more heavily
            connectivity_score = direct_neighbors + (inter_region_connections * 2)
            
            # Prefer current master for stability (hysteresis)
            if (group_to_current_master and 
                region_id in group_to_current_master and 
                group_to_current_master[region_id] == sat_id):
                connectivity_score += 1  # Small bonus for current master
            
            if connectivity_score > max_connectivity:
                max_connectivity = connectivity_score
                best_master = sat_id
        
        # Fallback to smallest ID if no connectivity found
        if best_master is None:
            best_master = min(sat_ids)
            
        region_to_master[region_id] = best_master
    
    # Debug output
    print(f"  > MASTER_DEBUG: total regions: {len(region_to_sats)}, empty: {empty_regions_count}, processed: {processed_regions_count}, masters: {len(region_to_master)}")
    if empty_regions_count > 0:
        print(f"  > MASTER_DEBUG: first 10 empty region IDs: {empty_region_ids[:10]}")
    
    # Additional check: verify ISL graph satellite count
    isl_satellites = set(sat_net_graph.nodes())
    print(f"  > MASTER_DEBUG: ISL graph has {len(isl_satellites)} satellites")
    
    # Check which satellites from regions are missing in ISL graph
    all_region_satellites = set()
    for sat_list in region_to_sats.values():
        all_region_satellites.update(sat_list)
    
    missing_in_isl = all_region_satellites - isl_satellites
    print(f"  > MASTER_DEBUG: {len(missing_in_isl)} satellites in regions but not in ISL graph")
    if len(missing_in_isl) > 0:
        print(f"  > MASTER_DEBUG: first 10 missing satellites: {sorted(list(missing_in_isl))[:10]}")

    return region_to_master
def compute_master_forwarding(
    full_graph: nx.Graph,
    masters: Iterable[int],
    sat_neighbor_to_if: Dict[Tuple[int, int], int],
) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    """Compute forwarding state between master satellites using shortest paths."""
    paths = dict(nx.all_pairs_dijkstra_path(full_graph, weight="weight"))
    forwarding: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
    masters = list(masters)
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
                    sat_neighbor_to_if[(nxt, src)],
                )
    return forwarding


def compute_intra_group_paths(
    sats: Iterable,
    masters: Iterable[int],
    full_graph: nx.Graph,
    n_sats_per_orbit: int,
    sat_neighbor_to_if: Dict[Tuple[int, int], int],
) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    """Compute forwarding paths from each master to all satellites in its group."""
    forwarding: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
    num_sats = len(sats)
    masters = list(masters)
    # Determine group membership based on orbit structure: satellites are arranged
    # consecutively by orbit.  In region grouping mode ``n_sats_per_orbit`` should
    # be set to 1 to avoid grouping by orbit indices.
    for master in masters:
        group_id = master // n_sats_per_orbit
        group_nodes: List[int] = [
            n for n in range(num_sats) if n // n_sats_per_orbit == group_id
        ]
        for dst in group_nodes:
            if dst == master:
                continue
            path = nx.shortest_path(full_graph, master, dst, weight="weight")
            if len(path) >= 2:
                nxt = path[1]
                forwarding[(master, dst)] = (
                    nxt,
                    sat_neighbor_to_if[(master, nxt)],
                    sat_neighbor_to_if[(nxt, master)],
                )
    return forwarding


def merge_fstate(
    master_fstate: Dict[Tuple[int, int], Tuple[int, int, int]],
    group_fstate: Dict[Tuple[int, int], Tuple[int, int, int]],
) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    """Merge inter‑group and intra‑group forwarding states, checking for conflicts."""
    merged: Dict[Tuple[int, int], Tuple[int, int, int]] = dict(master_fstate)
    for key, val in group_fstate.items():
        if key in merged and merged[key] != val:
            raise ValueError(f"Conflict for {key}: {merged[key]} vs {val}")
        merged[key] = val
    return merged


def write_fstate_to_file(fstate: Dict[Tuple[int, int], Tuple[int, int, int]], filename: str) -> None:
    """Write forwarding state to a file in CSV format."""
    with open(filename, "w+") as f:
        for (src, dst), (nxt, out_if, in_if) in fstate.items():
            f.write(f"{src},{dst},{nxt},{out_if},{in_if}\n")
