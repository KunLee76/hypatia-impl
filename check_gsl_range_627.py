#!/usr/bin/env python3
"""
檢查627地面站的GSL連接範圍
"""

import os

def check_gsl_range_for_gs627():
    # 設置路徑
    data_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast"
    
    # 讀取GSL接口信息
    gsl_file = f"{data_dir}/gsl_interfaces_info.txt"
    
    print("檢查627地面站的GSL連接範圍:")
    
    if os.path.exists(gsl_file):
        with open(gsl_file, 'r') as f:
            lines = f.readlines()
            
        # 找到627地面站（通常是第627-625=2行，因為從625開始）
        gs_627_line_idx = 627 - 625 + 625  # 調整索引
        
        if gs_627_line_idx < len(lines):
            line = lines[gs_627_line_idx].strip()
            print(f"GS627的GSL信息: {line}")
            
        # 或者搜索包含627的行
        for i, line in enumerate(lines):
            if '627' in line:
                print(f"找到627相關行 (line {i}): {line.strip()}")
    
    # 更好的方法：檢查哪些衛星在627的範圍內
    print("\n通過檢查路由表來推斷627的連接範圍:")
    
    fstate_file = f"{data_dir}/dynamic_state_100ms_for_10s/fstate_0.txt"
    satellites_can_reach_627 = set()
    
    if os.path.exists(fstate_file):
        with open(fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    # 找到所有直接下行到627的衛星
                    if dst == 627 and next_hop == 627:
                        satellites_can_reach_627.add(src)
    
    print(f"可以直接下行到GS627的衛星: {sorted(satellites_can_reach_627)}")
    
    # 檢查163和189是否在其中
    if 163 in satellites_can_reach_627:
        print("✓ 163可以直接連接到627")
    else:
        print("❌ 163無法直接連接到627")
    
    if 189 in satellites_can_reach_627:
        print("✓ 189可以直接連接到627")
    else:
        print("❌ 189無法直接連接到627")
    
    if 164 in satellites_can_reach_627:
        print("✓ 164可以直接連接到627")
    else:
        print("❌ 164無法直接連接到627")
    
    # 比較Free One算法的結果
    free_one_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_free_one_only_over_isls_fast/dynamic_state_100ms_for_10s"
    free_fstate_file = f"{free_one_dir}/fstate_0.txt"
    
    free_satellites_can_reach_627 = set()
    
    if os.path.exists(free_fstate_file):
        with open(free_fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    if dst == 627 and next_hop == 627:
                        free_satellites_can_reach_627.add(src)
    
    print(f"\nFree One算法中可以直接下行到GS627的衛星: {sorted(free_satellites_can_reach_627)}")
    
    # 分析差異
    only_in_virtual_pid = satellites_can_reach_627 - free_satellites_can_reach_627
    only_in_free_one = free_satellites_can_reach_627 - satellites_can_reach_627
    common = satellites_can_reach_627 & free_satellites_can_reach_627
    
    print(f"\n差異分析:")
    print(f"只在Virtual PID中能連接627的衛星: {sorted(only_in_virtual_pid)}")
    print(f"只在Free One中能連接627的衛星: {sorted(only_in_free_one)}")
    print(f"兩個算法都能連接627的衛星: {sorted(common)}")
    
    # 結論
    print(f"\n結論:")
    if 163 not in satellites_can_reach_627 and 163 not in free_satellites_can_reach_627:
        print("163確實無法直接連接到627，所以必須通過164")
        print("這解釋了為什麼路由是 625→189→163→164→627")
    elif 189 in satellites_can_reach_627 or 189 in free_satellites_can_reach_627:
        print("189可能可以直接連接到627，路由可以優化為 625→189→627")

if __name__ == "__main__":
    check_gsl_range_for_gs627()