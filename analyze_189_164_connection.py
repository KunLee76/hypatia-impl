#!/usr/bin/env python3
"""
分析為什麼189無法直連164的問題
"""

import os

def analyze_189_164_connection():
    # 設置路徑
    data_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast"
    fstate_dir = f"{data_dir}/dynamic_state_100ms_for_10s"
    
    # 分析路由表
    fstate_file = f"{fstate_dir}/fstate_0.txt"
    print(f"分析路由表文件: {fstate_file}")
    
    routes_189_to_627 = []
    routes_164_related = []
    
    if os.path.exists(fstate_file):
        with open(fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    # 尋找189到地面站627的路由
                    if src == 189 and dst == 627:
                        routes_189_to_627.append((src, dst, next_hop))
                        print(f"路由表: 189 -> 627 的下一跳是 {next_hop}")
                    
                    # 尋找所有涉及164的路由
                    if src == 164 or dst == 164 or next_hop == 164:
                        routes_164_related.append((src, dst, next_hop))
                    
                    # 尋找189的所有出站路由
                    if src == 189:
                        if dst >= 625:  # 地面站
                            print(f"189 -> GS{dst} 下一跳: {next_hop}")
    
    print(f"\n找到 {len(routes_164_related)} 條涉及164的路由:")
    for route in routes_164_related[:10]:  # 只顯示前10條
        src, dst, next_hop = route
        if dst >= 625:
            print(f"  {src} -> GS{dst} 下一跳: {next_hop}")
        elif src >= 625:
            print(f"  GS{src} -> {dst} 下一跳: {next_hop}")
        else:
            print(f"  {src} -> {dst} 下一跳: {next_hop}")
    
    # 檢查ISL文件來分析物理連接
    isls_file = f"{data_dir}/isls.txt"
    print(f"\n檢查ISL連接文件: {isls_file}")
    
    connections_189 = []
    connections_164 = []
    direct_189_164 = False
    
    if os.path.exists(isls_file):
        with open(isls_file, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 2:
                    sat1, sat2 = int(parts[0]), int(parts[1])
                    
                    if sat1 == 189:
                        connections_189.append(sat2)
                    elif sat2 == 189:
                        connections_189.append(sat1)
                    
                    if sat1 == 164:
                        connections_164.append(sat2)
                    elif sat2 == 164:
                        connections_164.append(sat1)
                    
                    if (sat1 == 189 and sat2 == 164) or (sat1 == 164 and sat2 == 189):
                        direct_189_164 = True
    
    print(f"189的ISL連接: {sorted(set(connections_189))}")
    print(f"164的ISL連接: {sorted(set(connections_164))}")
    print(f"189和164是否有直接ISL連接: {direct_189_164}")
    
    # 檢查163是否在189的連接中
    if 163 in connections_189:
        print("✓ 189確實直接連接到163")
    else:
        print("✗ 189沒有直接連接到163")
    
    if 164 in connections_189:
        print("✓ 189確實直接連接到164") 
    else:
        print("✗ 189沒有直接連接到164")
    
    # 分析共同鄰居
    common_neighbors = set(connections_189) & set(connections_164)
    print(f"189和164的共同鄰居: {sorted(common_neighbors)}")
    
    return {
        'routes_189_to_627': routes_189_to_627,
        'connections_189': connections_189,
        'connections_164': connections_164,
        'direct_189_164': direct_189_164,
        'common_neighbors': list(common_neighbors)
    }


if __name__ == "__main__":
    analyze_189_164_connection()