#!/usr/bin/env python3
"""
分析Virtual PID路徑中衛星的群組歸屬
"""

import pickle
import os
from collections import defaultdict

def analyze_path_satellites():
    # 路徑數據
    paths = {
        "625→626 (t=0)": [625, 189, 163, 137, 111, 85, 86, 60, 61, 62, 63, 64, 626],
        "625→626 (t=30.6s)": [625, 188, 189, 163, 164, 138, 112, 86, 60, 61, 62, 63, 64, 626],
        "625→627 (t=0)": [625, 189, 163, 164, 138, 139, 627],
        "625→627 (t=30.6s)": [625, 188, 189, 163, 164, 138, 139, 627]
    }
    
    # 讀取群組數據
    data_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_fast/data"
    
    try:
        with open(os.path.join(data_dir, "satellite_groups.pickle"), 'rb') as f:
            satellite_groups = pickle.load(f)
        
        with open(os.path.join(data_dir, "satellite_group_to_master.pickle"), 'rb') as f:
            group_to_master = pickle.load(f)
            
        print("Virtual PID 路徑分析報告")
        print("=" * 60)
        
        # 建立衛星到群組的映射
        sat_to_group = {}
        for group_id, satellites in satellite_groups.items():
            for sat in satellites:
                if sat < 1584:  # 只考慮衛星
                    sat_to_group[sat] = group_id
        
        # 分析每條路徑
        for path_name, path in paths.items():
            print(f"\n路徑: {path_name}")
            print("-" * 40)
            print(f"完整路徑: {' → '.join(map(str, path))}")
            print("\n衛星分析:")
            
            # 只分析衛星節點 (跳過地面站)
            satellites_in_path = [sat for sat in path if sat < 1584]
            
            group_info = defaultdict(list)
            
            for sat in satellites_in_path:
                group_id = sat_to_group.get(sat, "未知")
                if group_id != "未知":
                    master = group_to_master.get(group_id, "無")
                    is_master = "🔸 Master" if sat == master else "• 一般衛星"
                    group_info[group_id].append((sat, is_master))
            
            # 按群組顯示
            for group_id in sorted(group_info.keys()):
                print(f"  群組 {group_id}:")
                for sat, role in group_info[group_id]:
                    print(f"    衛星 {sat:3d} - {role}")
            
            print(f"\n  總共跨越 {len(group_info)} 個群組")
    
    except FileNotFoundError as e:
        print(f"找不到數據文件: {e}")
        print("請確認數據目錄是否正確")

if __name__ == "__main__":
    analyze_path_satellites()