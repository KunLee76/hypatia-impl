#!/usr/bin/env python3
"""
分析Virtual PID vs Free One的路由差異
"""

import os

def analyze_routing_difference():
    print("🔍 分析路由差異...")
    print("Free One: 625 → 383 → 382 → 627 (3跳)")
    print("Virtual PID: 625 → 189 → 163 → 164 → 627 (4跳)")
    print()
    
    # 檢查fstate文件
    vpid_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/dynamic_state_100ms_for_10s"
    free_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_free_one_only_over_isls_fast/dynamic_state_100ms_for_10s"
    
    print("🔍 檢查625的GSL選擇...")
    
    # 分析Virtual PID中625的路由選擇
    vpid_fstate = os.path.join(vpid_dir, "fstate_0.txt")
    if os.path.exists(vpid_fstate):
        with open(vpid_fstate, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    if src == 625 and dst == 627:
                        print(f"Virtual PID: 625 → 627 的下一跳是 {next_hop}")
                    elif src == 625 and dst in [382, 383, 189]:
                        print(f"Virtual PID: 625 → {dst} 的下一跳是 {next_hop}")
    
    # 分析Free One中625的路由選擇
    free_fstate = os.path.join(free_dir, "fstate_0.txt")
    if os.path.exists(free_fstate):
        with open(free_fstate, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    if src == 625 and dst == 627:
                        print(f"Free One: 625 → 627 的下一跳是 {next_hop}")
                    elif src == 625 and dst in [382, 383, 189]:
                        print(f"Free One: 625 → {dst} 的下一跳是 {next_hop}")
    
    print()
    print("📍 關鍵差異分析：")
    print("1. Free One選擇了383作為中間節點")
    print("2. Virtual PID選擇了189作為中間節點")
    print("3. 可能的原因：")
    print("   - GSL動態選擇算法不同")
    print("   - PID邊界限制了路由選擇")
    print("   - Gateway選擇策略需要優化")

if __name__ == "__main__":
    analyze_routing_difference()