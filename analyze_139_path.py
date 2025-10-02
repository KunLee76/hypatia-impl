#!/usr/bin/env python3
"""
分析為什麼不選擇139作為下行衛星
"""

import os

def analyze_139_path():
    print("分析為什麼不選擇139作為627的下行衛星:")
    
    # 檢查189到139的連接
    data_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast"
    isls_file = f"{data_dir}/isls.txt"
    
    connections_189 = []
    connections_139 = []
    direct_189_139 = False
    
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
                    
                    if sat1 == 139:
                        connections_139.append(sat2)
                    elif sat2 == 139:
                        connections_139.append(sat1)
                    
                    if (sat1 == 189 and sat2 == 139) or (sat1 == 139 and sat2 == 189):
                        direct_189_139 = True
    
    print(f"189的ISL連接: {sorted(set(connections_189))}")
    print(f"139的ISL連接: {sorted(set(connections_139))}")
    print(f"189和139是否直接連接: {direct_189_139}")
    
    # 檢查163和139的連接
    direct_163_139 = 139 in connections_189  # 應該檢查163的連接
    connections_163 = []
    
    if os.path.exists(isls_file):
        with open(isls_file, 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.strip().split()
                if len(parts) >= 2:
                    sat1, sat2 = int(parts[0]), int(parts[1])
                    
                    if sat1 == 163:
                        connections_163.append(sat2)
                    elif sat2 == 163:
                        connections_163.append(sat1)
    
    print(f"163的ISL連接: {sorted(set(connections_163))}")
    print(f"163和139是否直接連接: {139 in connections_163}")
    
    # 分析可能的路徑
    print(f"\n可能的路徑分析:")
    print("當前路徑: 625→189→163→164→627 (4跳)")
    
    if direct_189_139:
        print("可能路徑1: 625→189→139→627 (3跳) ✓")
    else:
        print("可能路徑1: 625→189→139→627 (189和139不直接連接)")
    
    if 139 in connections_163:
        print("可能路徑2: 625→189→163→139→627 (4跳)")
    else:
        print("可能路徑2: 625→189→163→139→627 (163和139不直接連接)")
    
    # 檢查Free One的路徑選擇
    free_one_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_free_one_only_over_isls_fast/dynamic_state_100ms_for_10s"
    free_fstate_file = f"{free_one_dir}/fstate_0.txt"
    
    print(f"\nFree One算法的路徑選擇:")
    if os.path.exists(free_fstate_file):
        with open(free_fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    if src == 383 and dst == 627:
                        print(f"Free One: 383 -> GS627 下一跳: {next_hop}")
                    if src == 382 and dst == 627:
                        print(f"Free One: 382 -> GS627 下一跳: {next_hop}")
                    if src == 139 and dst == 627:
                        print(f"Free One: 139 -> GS627 下一跳: {next_hop}")
    
    print(f"\n結論:")
    if direct_189_139:
        print("❓ 189可以直接連接到139，而139可以直接下行到627")
        print("這意味著最優路徑應該是: 625→189→139→627 (3跳)")
        print("需要檢查為什麼動態GSL選擇沒有選擇139作為目標衛星")
    else:
        print("189無法直接連接到139，所以需要經過其他中轉")
        print("當前的4跳路徑可能已經是最優的")

if __name__ == "__main__":
    analyze_139_path()