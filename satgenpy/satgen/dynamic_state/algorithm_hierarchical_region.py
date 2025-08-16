"""
Hierarchical routing algorithm with optional geographic region grouping.

This module extends the hierarchical routing approach by supporting dynamic grouping
of satellites based on fixed geographic regions (e.g. 5°×5° latitude/longitude cells).
When region grouping is enabled, satellites are clustered by the sub‑satellite
positions supplied at each time step, and the smallest indexed satellite in each
cluster is elected as the master for inter‑cluster routing.  Otherwise the
traditional orbit‑plane grouping is used.

Usage:

    from .algorithm_hierarchical_region import algorithm_hierarchical_region

    # Provide ``sat_lat_lon`` as a list of (lat, lon) tuples corresponding to the
    # ground projection of each satellite at the current time.  If not provided,
    # orbit‑based grouping will be used instead.
    result = algorithm_hierarchical_region(
        output_dynamic_state_dir=..., time_since_epoch_ns=..., satellites=..., ground_stations=...,
        sat_net_graph_only_satellites_with_isls=..., ground_station_satellites_in_range=...,
        num_isls_per_sat=..., sat_neighbor_to_if=..., list_gsl_interfaces_info=...,
        prev_output=..., enable_verbose_logs=True, sat_lat_lon=current_satellite_positions,
        region_lat_step=5.0, region_lon_step=5.0, use_region_grouping=True
    )

This function returns a dictionary containing the computed forwarding state mapping.
"""

import math
import networkx as nx
from typing import Dict, Iterable, List, Optional, Tuple

from .fstate_calculation import calculate_fstate_shortest_path_without_gs_relaying  # noqa: F401
from .region_grouping import (
    assign_satellites_to_regions,
    select_master_for_regions,
)


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
    *,
    sat_lat_lon: Optional[List[Tuple[float, float]]] = None,
    region_lat_step: float = 5.0,
    region_lon_step: float = 5.0,
    use_region_grouping: bool = False,
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
    if enable_verbose_logs:
        print("\nALGORITHM: HIERARCHICAL REGION")

    # Determine grouping and master satellites.
    sat_to_group: Dict[int, int] = {}
    group_to_master: Dict[int, int] = {}
    master_nodes: List[int] = []
    n_sats_per_orbit: Optional[int] = None

    if use_region_grouping and sat_lat_lon is not None:
        # Assign satellites to geographic regions and select masters.
        sat_to_group, region_to_sats = assign_satellites_to_regions(
            sat_lat_lon, lat_step=region_lat_step, lon_step=region_lon_step
        )
        group_to_master = select_master_for_regions(region_to_sats)
        master_nodes = list(group_to_master.values())
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
        master_nodes,
        n_sats_per_orbit if n_sats_per_orbit is not None else 1,
        # Pass dynamic grouping mappings for downstream use.
        sat_to_group=sat_to_group,
        group_to_master=group_to_master,
    )

    # Combine satellite‑to‑satellite and ground‑station related forwarding state.
    fstate.update(gs_fstate)

    # --------
    # Output forwarding state table.
    # --------
    fstate_filename = output_dynamic_state_dir + f"/fstate_{time_since_epoch_ns}.txt"
    write_fstate_to_file(fstate, fstate_filename)

    return {"fstate": fstate}


def calculate_hierarchical_path_through_masters(
    output_dynamic_state_dir: str,
    time_since_epoch_ns: int,
    num_satellites: int,
    num_ground_stations: int,
    sat_net_graph_only_satellites_with_isls: nx.Graph,
    num_isls_per_sat: List[int],
    gid_to_sat_gsl_if_idx: List[int],
    ground_station_satellites_in_range: List[List[bool]],
    sat_neighbor_to_if: Dict[Tuple[int, int], int],
    prev_fstate: Optional[Dict[Tuple[int, int], Tuple[int, int, int]]],
    enable_verbose_logs: bool,
    master_nodes: List[int],
    n_sats_per_orbit: int,
    *,
    sat_to_group: Dict[int, int],
    group_to_master: Dict[int, int],
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
            for sid in range(num_satellites):
                try:
                    if ground_station_satellites_in_range[gid][sid]:
                        sat_id_list.append(sid)
                except IndexError:
                    continue
        gs_to_reachable_sats[gid] = sat_id_list

    # Compute forwarding paths for each pair of ground stations.
    for src_gid in range(num_ground_stations):
        for dst_gid in range(num_ground_stations):
            if src_gid == dst_gid:
                continue
            src_node_id = num_satellites + src_gid
            dst_node_id = num_satellites + dst_gid
            src_reachable = gs_to_reachable_sats.get(src_gid, [])
            dst_reachable = gs_to_reachable_sats.get(dst_gid, [])
            if not src_reachable or not dst_reachable:
                continue
            # Pick the first reachable satellite for each ground station as uplink/downlink.
            src_sat = src_reachable[0]
            dst_sat = dst_reachable[0]
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
                        downlink_idx = ground_station_satellites_in_range[dst_gid].index(True)
                    except ValueError:
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
                    downlink_idx = ground_station_satellites_in_range[dst_gid].index(True)
                except ValueError:
                    continue
                fstate[(dst_sat, dst_node_id)] = (
                    dst_node_id,
                    num_isls_per_sat[dst_sat] + downlink_idx,
                    gid_to_sat_gsl_if_idx[dst_gid],
                )

    return fstate


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
