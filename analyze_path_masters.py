#!/usr/bin/env python3
"""
分析625→627路徑中的衛星是否都是master
"""

import sys
sys.path.append("satgenpy")
import satgen
import os
import pickle
import math

def analyze_path_masters():
    """分析路徑中的衛星角色"""
    
    # 讀取群組數據
    data_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/data"
    
    # 加載群組分配數據
    with open(os.path.join(data_dir, "satellite_groups.pickle"), 'rb') as f:
        pid_to_sats = pickle.load(f)
    
    # 加載master分配數據  
    with open(os.path.join(data_dir, "satellite_group_to_master.pickle"), 'rb') as f:
        pid_to_master = pickle.load(f)
    
    # 路徑中的衛星
    path_sats = [625, 189, 163, 164, 138, 139, 627]
    
    print("🔍 分析路徑中的衛星角色:")
    print("路徑: 625 → 189 → 163 → 164 → 138 → 139 → 627")
    print()
    
    # 建立衛星到PID的映射
    sat_to_pid = {}
    for pid, sats in pid_to_sats.items():
        for sat in sats:
            sat_to_pid[sat] = pid
    
    # 分析每個衛星
    for i, sat in enumerate(path_sats):
        if sat >= 625:  # 地面站
            print(f"節點 {i+1}: 衛星/地面站 {sat} - 地面站")
            continue
            
        pid = sat_to_pid.get(sat, "未知")
        if pid == "未知":
            print(f"節點 {i+1}: 衛星 {sat} - ❌ 未找到PID")
            continue
            
        master = pid_to_master.get(pid, None)
        is_master = (sat == master)
        
        # 獲取同PID的其他衛星
        group_members = pid_to_sats.get(pid, set())
        other_members = [s for s in group_members if s != sat]
        
        status = "🔴 MASTER" if is_master else "🟢 普通衛星"
        print(f"節點 {i+1}: 衛星 {sat} - PID {pid} - {status}")
        print(f"      Master: {master}, 群組成員數: {len(group_members)}")
        print(f"      其他成員: {sorted(other_members)[:10]}{'...' if len(other_members) > 10 else ''}")
        print()
    
    # 統計master數量
    master_count = sum(1 for sat in path_sats[1:-1] if sat < 625 and sat == pid_to_master.get(sat_to_pid.get(sat, -1), None))
    total_sat_count = len([sat for sat in path_sats[1:-1] if sat < 625])
    
    print(f"📊 統計結果:")
    print(f"路徑中的衛星節點數: {total_sat_count}")
    print(f"其中master數量: {master_count}")
    print(f"Master比例: {master_count/total_sat_count*100:.1f}%")
    
    if master_count == total_sat_count:
        print("⚠️  所有衛星都是master - 這說明算法退化為傳統的master-based路由!")
        print("   需要修正同群組內的路由邏輯，實現真正的子圖最短路徑")
    else:
        print("✅ 路徑中包含普通衛星 - 算法正常工作")

if __name__ == "__main__":
    analyze_path_masters()