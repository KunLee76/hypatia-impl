#!/usr/bin/env python3
"""
簡單測試修復後的衛星位置數據提取
"""

import sys
import os
import networkx as nx
from typing import Dict, Tuple, Any, Optional

# 模擬修復後的 _best_effort_sat_latlon 函數
def _best_effort_sat_latlon(
    sat_lat_lon,
    satellites,
    G_sat_isls: nx.Graph
) -> Dict[int, Tuple[float, float]]:
    """
    優先使用呼叫者提供的 sat_lat_lon；
    否則嘗試從圖節點屬性或 satellites 物件上擷取 (lat, lon)。
    回傳 {sat_id: (lat, lon)}；擷取不到則回 {}。
    """
    print(f"[DEBUG] Testing sat_lat_lon extraction...")
    print(f"  - Input sat_lat_lon type: {type(sat_lat_lon)}")
    if sat_lat_lon:
        print(f"  - Input sat_lat_lon sample: {dict(list(sat_lat_lon.items())[:3]) if isinstance(sat_lat_lon, dict) else str(sat_lat_lon)[:100]}")
    
    # 1) 呼叫者已提供
    if isinstance(sat_lat_lon, dict) and len(sat_lat_lon) > 0:
        print(f"[DEBUG] Using provided sat_lat_lon with {len(sat_lat_lon)} entries")
        return sat_lat_lon

    # 2) 從圖節點屬性撈
    cand_keys = [
        ("lat", "lon"),
        ("nadir_lat", "nadir_lon"),
        ("lat_deg", "lon_deg"),
        ("latitude", "longitude"),
    ]
    out: Dict[int, Tuple[float,float]] = {}
    try:
        print(f"[DEBUG] Trying to extract from graph nodes ({len(G_sat_isls.nodes())} nodes)")
        for nid, data in G_sat_isls.nodes(data=True):
            if not isinstance(nid, int):
                continue
            for klat, klon in cand_keys:
                if klat in data and klon in data:
                    out[nid] = (float(data[klat]), float(data[klon]))
                    print(f"[DEBUG] Found position for node {nid}: {out[nid]}")
                    break
        if out:
            print(f"[DEBUG] Extracted {len(out)} positions from graph")
            return out
    except Exception as e:
        print(f"[DEBUG] Graph extraction failed: {e}")

    # 3) 從 satellites 物件撈
    try:
        print(f"[DEBUG] Trying to extract from satellites ({len(satellites) if hasattr(satellites, '__len__') else 'unknown'} sats)")
        for sid, sat in enumerate(satellites):
            for klat, klon in cand_keys + [("nadir_lat_deg","nadir_lon_deg")]:
                lat = getattr(sat, klat, None)
                lon = getattr(sat, klon, None)
                if lat is not None and lon is not None:
                    out[sid] = (float(lat), float(lon))
                    print(f"[DEBUG] Found position for sat {sid}: {out[sid]}")
                    break
        if out:
            print(f"[DEBUG] Extracted {len(out)} positions from satellites")
            return out
    except Exception as e:
        print(f"[DEBUG] Satellites extraction failed: {e}")

    # 4) 仍失敗 → 回 {}
    print(f"[DEBUG] No position data found, returning empty dict")
    return {}

def test_scenarios():
    """測試不同的輸入場景"""
    
    print("=== Test 1: Valid dict input ===")
    test_dict = {0: (45.0, -90.0), 1: (50.0, 0.0)}
    result = _best_effort_sat_latlon(test_dict, [], nx.Graph())
    print(f"Result: {result}")
    
    print("\n=== Test 2: None input ===")
    result = _best_effort_sat_latlon(None, [], nx.Graph())
    print(f"Result: {result}")
    
    print("\n=== Test 3: Empty dict input ===")
    result = _best_effort_sat_latlon({}, [], nx.Graph())
    print(f"Result: {result}")
    
    print("\n=== Test 4: Graph with node attributes ===")
    G = nx.Graph()
    G.add_node(0, lat=30.0, lon=120.0)
    G.add_node(1, nadir_lat=35.0, nadir_lon=125.0)
    result = _best_effort_sat_latlon(None, [], G)
    print(f"Result: {result}")
    
    print("\n=== Test 5: Mock satellite objects ===")
    class MockSat:
        def __init__(self, lat, lon):
            self.nadir_lat_deg = lat
            self.nadir_lon_deg = lon
    
    mock_sats = [MockSat(40.0, -75.0), MockSat(41.0, -74.0)]
    result = _best_effort_sat_latlon(None, mock_sats, nx.Graph())
    print(f"Result: {result}")

if __name__ == "__main__":
    test_scenarios()