#!/usr/bin/env python3
"""
分析為什麼163不能直接下行到627地面站的問題
"""

import os

def analyze_163_direct_downlink():
    # 設置路徑
    data_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast"
    fstate_dir = f"{data_dir}/dynamic_state_100ms_for_10s"
    
    # 分析路由表
    fstate_file = f"{fstate_dir}/fstate_0.txt"
    
    print("分析163的所有出站路由:")
    routes_163 = {}
    
    if os.path.exists(fstate_file):
        with open(fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    # 163的所有出站路由
                    if src == 163:
                        if dst >= 625:  # 地面站
                            routes_163[dst] = next_hop
    
    # 檢查163到627的路由
    next_hop_627 = routes_163.get(627, 'N/A')
    print(f"163 -> GS627 的下一跳: {next_hop_627}")
    
    if next_hop_627 == 164:
        print("❌ 問題確認：163確實是傳給164而不是直接下行到627")
    elif next_hop_627 == 627:
        print("✓ 163直接下行到627")
    else:
        print(f"❌ 163傳給了其他節點: {next_hop_627}")
    
    # 檢查163是否能夠直接連接到627地面站
    print("\n檢查163能否直接連接到627地面站:")
    
    # 檢查ground_station_satellites_in_range
    # 這裡我們需要讀取GSL範圍資料
    print("檢查GSL範圍資料...")
    
    # 分析164的路由，為什麼它被選為下一跳
    print(f"\n分析164的路由選擇:")
    routes_164 = {}
    
    if os.path.exists(fstate_file):
        with open(fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    if src == 164 and dst >= 625:
                        routes_164[dst] = next_hop
    
    next_hop_164_to_627 = routes_164.get(627, 'N/A')
    print(f"164 -> GS627 的下一跳: {next_hop_164_to_627}")
    
    if next_hop_164_to_627 == 627:
        print("✓ 164確實能直接下行到627")
        print("問題分析：163應該也能直接下行到627，但算法選擇了經由164")
    
    # 檢查Free One算法中163的行為
    free_one_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_free_one_only_over_isls_fast/dynamic_state_100ms_for_10s"
    free_fstate_file = f"{free_one_dir}/fstate_0.txt"
    
    print(f"\n檢查Free One算法中163的路由:")
    if os.path.exists(free_fstate_file):
        with open(free_fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    if src == 163 and dst == 627:
                        print(f"Free One: 163 -> GS627 下一跳: {next_hop}")
                        if next_hop == 627:
                            print("✓ Free One中163確實直接下行到627!")
    
    # 比較189的選擇
    print(f"\n比較189的路由選擇:")
    routes_189 = {}
    
    if os.path.exists(fstate_file):
        with open(fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    if src == 189 and dst >= 625:
                        routes_189[dst] = next_hop
    
    next_hop_189_to_627 = routes_189.get(627, 'N/A')
    print(f"189 -> GS627 的下一跳: {next_hop_189_to_627}")
    
    if next_hop_189_to_627 == 627:
        print("✓ 189可以直接下行到627")
        print("建議：189應該直接下行到627，而不是經由163→164")
    elif next_hop_189_to_627 == 163:
        print("❌ 189選擇經由163，但163又不直接下行")
    
    print(f"\n結論分析:")
    print("1. 如果163能直接連接到627，它應該直接下行")
    print("2. 如果189能直接連接到627，它應該直接下行")
    print("3. 目前的路由選擇可能不是最優的")
    print("4. 需要檢查dynamic GSL selection的邏輯是否正確選擇了最短路徑")

if __name__ == "__main__":
    analyze_163_direct_downlink()