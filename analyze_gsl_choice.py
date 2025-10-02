#!/usr/bin/env python3
"""
分析為什麼Virtual PID選擇189而不是383作為625到627的路由
"""

import os

def analyze_gsl_choice():
    print("🔍 分析GSL選擇邏輯...")
    
    # 檢查地面站在範圍內的衛星
    vpid_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/dynamic_state_100ms_for_10s"
    
    # 檢查GSL介面資訊
    gsl_info_file = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/gsl_interfaces_info.txt"
    
    if os.path.exists(gsl_info_file):
        print("📡 GSL介面資訊：")
        with open(gsl_info_file, 'r') as f:
            lines = f.readlines()
            # 只顯示625和627相關的
            for line in lines:
                if '625' in line or '627' in line:
                    print(f"  {line.strip()}")
    
    # 檢查地面站
    gs_file = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/ground_stations.txt"
    if os.path.exists(gs_file):
        print("\n🗺️ 地面站位置：")
        with open(gs_file, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if i == 1:  # GS 625 (index 0 對應 GS 625)
                    print(f"  GS 625: {line.strip()}")
                elif i == 3:  # GS 627 (index 2 對應 GS 627)
                    print(f"  GS 627: {line.strip()}")
    
    print("\n🤔 可能的問題：")
    print("1. Virtual PID可能受到PID邊界約束")
    print("2. 動態GSL選擇可能沒有考慮到所有可能的衛星")
    print("3. 383可能屬於不同的PID，導致不被優先選擇")
    
    # 檢查ISL檔案來了解383和189的連接性
    isl_file = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/isls.txt"
    if os.path.exists(isl_file):
        print("\n🔗 檢查383和189的ISL連接：")
        with open(isl_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    sat1, sat2 = int(parts[0]), int(parts[1])
                    if (sat1 == 383 and sat2 in [382, 627]) or (sat2 == 383 and sat1 in [382, 627]):
                        print(f"  383連接: {line.strip()}")
                    elif (sat1 == 189 and sat2 in [163, 164]) or (sat2 == 189 and sat1 in [163, 164]):
                        print(f"  189連接: {line.strip()}")

if __name__ == "__main__":
    analyze_gsl_choice()