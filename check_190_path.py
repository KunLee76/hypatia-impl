#!/usr/bin/env python3
"""
檢查189→190路徑是否更優
"""

import os

def check_189_via_190_path():
    # 設置路徑
    data_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast"
    
    # 檢查190的連接
    isls_file = f"{data_dir}/isls.txt"
    
    print("檢查190的ISL連接:")
    connections_190 = []
    
    if os.path.exists(isls_file):
        with open(isls_file, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 2:
                    sat1, sat2 = int(parts[0]), int(parts[1])
                    
                    if sat1 == 190:
                        connections_190.append(sat2)
                    elif sat2 == 190:
                        connections_190.append(sat1)
    
    print(f"190的直接ISL連接: {sorted(connections_190)}")
    
    # 檢查190是否能直接連接到能夠下行627的衛星[139, 164, 357, 382]
    can_reach_627_sats = [139, 164, 357, 382]
    direct_to_627_sats = []
    
    for sat in can_reach_627_sats:
        if sat in connections_190:
            direct_to_627_sats.append(sat)
    
    print(f"190可以直接連接到的能下行627的衛星: {direct_to_627_sats}")
    
    if direct_to_627_sats:
        print(f"✓ 可能的優化路徑: 625→189→190→{direct_to_627_sats[0]}→627 (4跳)")
        print(f"vs 當前路徑: 625→189→163→164→627 (4跳)")
        print("跳數相同，但可能距離更短")
    else:
        print("❌ 190無法直接連接到任何能下行627的衛星")
    
    # 檢查190在路由表中的行為
    fstate_file = f"{data_dir}/dynamic_state_100ms_for_10s/fstate_0.txt"
    
    print(f"\n檢查190的路由表:")
    if os.path.exists(fstate_file):
        with open(fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    if src == 190 and dst == 627:
                        print(f"190 -> GS627 下一跳: {next_hop}")
                        if next_hop in direct_to_627_sats:
                            print(f"✓ 190選擇了直接路徑到{next_hop}")
                        break
            else:
                print("❌ 190沒有到GS627的路由")
    
    # 檢查為什麼189沒有選擇190
    print(f"\n分析189的選擇:")
    print("189的選項:")
    print("1. 189→163→164→627")
    print("2. 189→190→?→627")
    
    # 如果190可以直接連164
    if 164 in connections_190:
        print("發現：190可以直接連164！")
        print("更優路徑可能是: 625→189→190→164→627 (4跳)")
    
    # 檢查動態GSL選擇是否考慮了所有可能性
    print(f"\n問題可能在於:")
    print("1. 動態GSL選擇算法可能沒有完全遍歷所有可能的路徑")
    print("2. 算法可能優先選擇了163而沒有充分評估190的路徑")
    print("3. 需要檢查find_optimal_gsl_satellite函數的邏輯")

if __name__ == "__main__":
    check_189_via_190_path()