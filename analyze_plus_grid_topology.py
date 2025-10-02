#!/usr/bin/env python3
"""
分析189在Plus Grid拓撲中的連接限制
"""

def analyze_189_connections():
    NUM_ORBS = 25
    NUM_SATS_PER_ORB = 25
    isl_shift = 1
    
    sat_189 = 189
    
    # 計算189的軌道和位置
    orbit_189 = sat_189 // NUM_SATS_PER_ORB  # 7
    pos_189 = sat_189 % NUM_SATS_PER_ORB     # 14
    
    print(f"衛星189位置分析:")
    print(f"  軌道: {orbit_189}")
    print(f"  軌道內位置: {pos_189}")
    
    # Plus Grid連接規則
    connections = []
    
    # 1. 同軌道連接：前一顆和後一顆
    prev_same_orbit = orbit_189 * NUM_SATS_PER_ORB + ((pos_189 - 1) % NUM_SATS_PER_ORB)
    next_same_orbit = orbit_189 * NUM_SATS_PER_ORB + ((pos_189 + 1) % NUM_SATS_PER_ORB)
    
    connections.extend([prev_same_orbit, next_same_orbit])
    
    # 2. 跨軌道連接：相鄰軌道的對應位置（考慮shift）
    # 前一個軌道
    prev_orbit = (orbit_189 - 1) % NUM_ORBS
    sat_prev_orbit = prev_orbit * NUM_SATS_PER_ORB + ((pos_189 - isl_shift) % NUM_SATS_PER_ORB)
    
    # 後一個軌道  
    next_orbit = (orbit_189 + 1) % NUM_ORBS
    sat_next_orbit = next_orbit * NUM_SATS_PER_ORB + ((pos_189 + isl_shift) % NUM_SATS_PER_ORB)
    
    connections.extend([sat_prev_orbit, sat_next_orbit])
    
    print(f"\nPlus Grid理論連接:")
    print(f"  同軌道前一顆: {prev_same_orbit}")
    print(f"  同軌道後一顆: {next_same_orbit}")
    print(f"  前軌道對應: {sat_prev_orbit}")
    print(f"  後軌道對應: {sat_next_orbit}")
    print(f"  理論連接: {sorted(connections)}")
    
    # 實際ISL檔案中的連接
    actual_connections = [163, 188, 190, 215]
    print(f"  實際連接: {sorted(actual_connections)}")
    
    # 驗證計算
    print(f"\n驗證計算:")
    print(f"  188 -> 軌道{188//25}, 位置{188%25}")  # 軌道7, 位置13
    print(f"  190 -> 軌道{190//25}, 位置{190%25}")  # 軌道7, 位置15  
    print(f"  163 -> 軌道{163//25}, 位置{163%25}")  # 軌道6, 位置13
    print(f"  215 -> 軌道{215//25}, 位置{215%25}")  # 軌道8, 位置15
    
    print(f"\n結論:")
    print(f"Plus Grid拓撲限制了每個衛星只能連接到:")
    print(f"1. 同軌道的前後兩顆衛星")
    print(f"2. 相鄰軌道的對應位置衛星（考慮shift）")
    print(f"這就是為什麼189無法連接到164、382、407等衛星的原因！")
    
    # 分析164的位置
    sat_164 = 164
    orbit_164 = sat_164 // NUM_SATS_PER_ORB  # 6
    pos_164 = sat_164 % NUM_SATS_PER_ORB     # 14
    
    print(f"\n164的位置:")
    print(f"  軌道: {orbit_164}")
    print(f"  軌道內位置: {pos_164}")
    print(f"  189在軌道{orbit_189}，164在軌道{orbit_164}")
    print(f"  相差{abs(orbit_189-orbit_164)}個軌道，Plus Grid只能連接相鄰軌道")
    print(f"  所以189無法直接連接164！")

if __name__ == "__main__":
    analyze_189_connections()