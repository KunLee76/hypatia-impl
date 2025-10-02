#!/usr/bin/env python3
"""
檢查189為什麼不直接連接到164
"""

import os

def check_189_to_164_connection():
    # 設置路徑
    data_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast"
    
    # 檢查ISL連接
    isls_file = f"{data_dir}/isls.txt"
    
    print("檢查189的ISL連接:")
    connections_189 = []
    
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
    
    print(f"189的直接ISL連接: {sorted(connections_189)}")
    
    # 檢查189是否有直接連接到164
    if 164 in connections_189:
        print("✓ 189確實有直接ISL連接到164!")
        print("❌ 問題：算法沒有選擇這條直接路徑")
    else:
        print("❌ 189沒有直接ISL連接到164")
        print("✓ 算法選擇163是正確的，因為189無法直接到達164")
    
    # 檢查163是否在189的連接中
    if 163 in connections_189:
        print("✓ 189確實有直接ISL連接到163")
    
    # 檢查189在路由表中的選擇
    fstate_file = f"{data_dir}/dynamic_state_100ms_for_10s/fstate_0.txt"
    
    print(f"\n檢查189的路由表選擇:")
    if os.path.exists(fstate_file):
        with open(fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    if src == 189 and dst == 627:
                        print(f"189 -> GS627 下一跳: {next_hop}")
                        
                        if next_hop == 164 and 164 in connections_189:
                            print("✓ 算法選擇了直接路徑189→164")
                        elif next_hop == 163 and 163 in connections_189:
                            print("❌ 算法選擇了189→163，但189可以直接連164")
                        elif next_hop == 163:
                            print("✓ 算法選擇189→163是合理的（如果189無法直接連164）")
    
    # 檢查Free One算法的選擇
    free_one_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_free_one_only_over_isls_fast/dynamic_state_100ms_for_10s"
    free_fstate_file = f"{free_one_dir}/fstate_0.txt"
    
    print(f"\n檢查Free One算法的選擇:")
    if os.path.exists(free_fstate_file):
        with open(free_fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    if src == 189 and dst == 627:
                        print(f"Free One: 189 -> GS627 下一跳: {next_hop}")
    
    # 分析可能的原因
    print(f"\n可能的原因分析:")
    if 164 in connections_189:
        print("1. 189確實可以直接連164，但算法的動態GSL選擇可能有問題")
        print("2. 檢查find_optimal_gsl_satellite函數是否正確計算了最短路徑")
        print("3. 可能PID限制影響了路由選擇")
    else:
        print("1. 189無法直接連164，所以必須通過163中轉")
        print("2. 這是物理連接的限制，不是算法問題")
    
    return 164 in connections_189

if __name__ == "__main__":
    can_direct_connect = check_189_to_164_connection()
    if can_direct_connect:
        print(f"\n🎯 關鍵發現：189可以直接連164！需要檢查算法的路由選擇邏輯")
    else:
        print(f"\n✓ 確認：189無法直接連164，當前路由是最優的")