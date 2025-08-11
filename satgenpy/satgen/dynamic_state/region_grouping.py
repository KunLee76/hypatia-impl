"""
Utilities for assigning satellites to geographic regions and selecting a master satellite for
each region.  In a hierarchical routing design, grouping satellites by geographic area can
reduce the scope of link‑state advertisements and improve locality for content delivery.

This module exposes a few simple helpers to map ground projection coordinates to a
discrete region identifier and to choose a representative ("master") satellite for each
region.  The region identifiers are derived from a fixed latitude/longitude grid.

The grid cell size defaults to 5°×5°, but any positive step size can be provided.

Example usage:

    from .region_grouping import assign_satellites_to_regions, select_master_for_regions

    # List of (latitude, longitude) tuples for each satellite's sub‑satellite point.
    sat_lat_lon = [(lat0, lon0), (lat1, lon1), ...]
    sat_to_region, region_to_sats = assign_satellites_to_regions(sat_lat_lon, lat_step=5, lon_step=5)
    region_to_master = select_master_for_regions(region_to_sats)

The resulting ``sat_to_region`` mapping indicates which grid cell each satellite belongs
to, and ``region_to_master`` maps each region identifier to the smallest satellite index
found in that region.  You may use different selection logic if a different notion of
``master`` is required (e.g. the satellite closest to the region centroid).
"""

from typing import Dict, Iterable, List, Tuple


def get_region_id(lat: float, lon: float, lat_step: float = 5.0, lon_step: float = 5.0) -> int:
    """Return an integer region identifier for a sub‑satellite point.

    The Earth is divided into a grid of equally sized latitude × longitude cells.  Latitudes
    are in the range [‑90, 90] and longitudes in [‑180, 180].  A region identifier is
    computed by mapping latitudes and longitudes to discrete indices and then flattening the
    2D grid into a 1D index.

    Args:
        lat:  Sub‑satellite latitude in degrees.
        lon:  Sub‑satellite longitude in degrees.
        lat_step:  Size of each grid cell in the latitude direction (degrees).
        lon_step:  Size of each grid cell in the longitude direction (degrees).

    Returns:
        An integer region identifier unique within the grid.

    Notes:
        The region ID is computed as ``lat_index * num_lon_cells + lon_index`` where
        ``lat_index`` = floor((lat + 90) / lat_step) and ``lon_index`` = floor((lon + 180) / lon_step).
    """
    # Clamp values within expected ranges.
    if lat < -90.0:
        lat = -90.0
    elif lat > 90.0:
        lat = 90.0
    # Normalize longitude to [‑180, 180]
    lon = ((lon + 180) % 360) - 180

    lat_index = int((lat + 90.0) // lat_step)
    lon_index = int((lon + 180.0) // lon_step)
    num_lon_cells = int(360.0 // lon_step)
    return lat_index * num_lon_cells + lon_index


def assign_satellites_to_regions(
    sat_lat_lon: Iterable[Tuple[float, float]],
    lat_step: float = 5.0,
    lon_step: float = 5.0,
) -> Tuple[Dict[int, int], Dict[int, List[int]]]:
    """Assign satellites to geographic regions.

    Given a list of sub‑satellite latitude/longitude pairs, compute a mapping from satellite
    indices (based on enumeration order) to region identifiers, along with a reverse mapping
    from region identifiers to lists of satellite indices belonging to that region.

    Args:
        sat_lat_lon:  An iterable of ``(latitude, longitude)`` tuples.  Each entry
            corresponds to one satellite's ground projection.
        lat_step:  Grid step size in latitude direction (degrees).
        lon_step:  Grid step size in longitude direction (degrees).

    Returns:
        A tuple ``(sat_to_region, region_to_sats)`` where ``sat_to_region`` maps each
        satellite index to its region identifier, and ``region_to_sats`` maps each region
        identifier to a list of satellite indices assigned to it.
    """
    sat_to_region: Dict[int, int] = {}
    region_to_sats: Dict[int, List[int]] = {}
    for sid, (lat, lon) in enumerate(sat_lat_lon):
        region_id = get_region_id(lat, lon, lat_step, lon_step)
        sat_to_region[sid] = region_id
        region_to_sats.setdefault(region_id, []).append(sid)
    return sat_to_region, region_to_sats


def select_master_for_regions(region_to_sats: Dict[int, Iterable[int]]) -> Dict[int, int]:
    """Select a master satellite for each region.

    The default strategy is to choose the satellite with the smallest index within each
    region as the master.  This simple approach provides a deterministic choice and can
    easily be replaced with alternative logic (e.g. choosing the satellite closest to the
    region's centroid or with the longest remaining dwell time).

    Args:
        region_to_sats:  Mapping from region identifiers to iterables of satellite
            indices belonging to each region.

    Returns:
        A mapping from region identifiers to the selected master satellite index for
        that region.
    """
    region_to_master: Dict[int, int] = {}
    for region_id, sat_ids in region_to_sats.items():
        # Convert to list in case the iterable is not indexable.
        sat_list = list(sat_ids)
        if not sat_list:
            continue
        master = min(sat_list)
        region_to_master[region_id] = master
    return region_to_master
