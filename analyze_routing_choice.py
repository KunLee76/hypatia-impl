#!/usr/bin/env python3
"""
分析為什麼不使用190作為中間節點的問題
"""

import os

def analyze_routing_choice():
    # 設置路徑
    data_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast"
    fstate_dir = f"{data_dir}/dynamic_state_100ms_for_10s"
    
    # 分析190相關的路由
    fstate_file = f"{fstate_dir}/fstate_0.txt"
    
    routes_190 = {}
    routes_163 = {}
    
    if os.path.exists(fstate_file):
        with open(fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    # 190的所有出站路由到地面站
                    if src == 190 and dst >= 625:
                        routes_190[dst] = next_hop
                    
                    # 163的所有出站路由到地面站
                    if src == 163 and dst >= 625:
                        routes_163[dst] = next_hop
    
    print("190的路由選擇:")
    for gs in sorted(routes_190.keys())[:10]:  # 前10個
        print(f"  190 -> GS{gs} 下一跳: {routes_190[gs]}")
    
    print("\n163的路由選擇:")
    for gs in sorted(routes_163.keys())[:10]:  # 前10個
        print(f"  163 -> GS{gs} 下一跳: {routes_163[gs]}")
    
    # 檢查地面站627的特殊情況
    print(f"\n針對GS627:")
    print(f"  190 -> GS627 下一跳: {routes_190.get(627, 'N/A')}")
    print(f"  163 -> GS627 下一跳: {routes_163.get(627, 'N/A')}")
    
    # 檢查Free One算法的路由
    free_one_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_free_one_only_over_isls_fast/dynamic_state_100ms_for_10s"
    free_fstate_file = f"{free_one_dir}/fstate_0.txt"
    
    print(f"\n檢查Free One算法的路由:")
    if os.path.exists(free_fstate_file):
        with open(free_fstate_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
                    
                    if src == 189 and dst == 627:
                        print(f"  Free One: 189 -> GS627 下一跳: {next_hop}")
                    
                    if src == 163 and dst == 627:
                        print(f"  Free One: 163 -> GS627 下一跳: {next_hop}")
                    
                    if src == 190 and dst == 627:
                        print(f"  Free One: 190 -> GS627 下一跳: {next_hop}")
    
    # 分析PID分配
    print(f"\n檢查衛星PID分配:")
    print("根據25x25網格，15度x15度的劃分:")
    print("- 189大約在第8行第14列 (PID=8*25+14=214)")
    print("- 163大約在第7行第13列 (PID=7*25+13=188)")  
    print("- 164大約在第7行第14列 (PID=7*25+14=189)")
    print("- 190大約在第8行第15列 (PID=8*25+15=215)")
    print("- 138大約在第6行第13列 (PID=6*25+13=163)")
    
    # 問題分析
    print(f"\n問題分析:")
    print("1. 189和164在不同PID (214 vs 189)，需要跨PID路由")
    print("2. 189→163 (跨PID 214→188) 和 189→190 (同PID 214→215)")
    print("3. Virtual PID可能優先選擇特定的跨PID gateway")
    print("4. 需要檢查gateway選擇邏輯和PID間的路由策略")

if __name__ == "__main__":
    analyze_routing_choice()