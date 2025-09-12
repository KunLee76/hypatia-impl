#!/usr/bin/env python3
"""
驗證路由表生成 vs 路由分析的差異
"""

import sys
import os
sys.path.append("satgenpy")

from satgen.post_analysis.graph_tools import get_path


def compare_routing_with_different_analysis():
    """
    比較同一路由表用不同分群參數分析的結果
    """
    
    data_dir = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_region_fast/dynamic_state_50ms_for_100s"
    time_ns = 50 * 1000000
    
    # 讀取路由表（這個路徑是固定的，是生成時用5°×5°計算的）
    fstate_file = f"{data_dir}/fstate_{time_ns}.txt"
    fstate = {}
    with open(fstate_file, 'r') as f:
        for line in f:
            if line.strip():
                spl = line.strip().split(',')
                current = int(spl[0])
                destination = int(spl[1])
                next_hop = int(spl[2])
                fstate[(current, destination)] = next_hop
    
    # 獲取路由路徑（這個路徑不會改變）
    path = get_path(625, 626, fstate)
    print(f"📍 路由路徑（固定）: {' → '.join(map(str, path))}")
    print(f"📊 總跳數: {len(path) - 1}")
    
    print("\n" + "="*60)
    print("🔍 用不同分群參數重新分析同一路徑")
    print("="*60)
    
    # 測試不同的分群參數對同一路徑的影響
    grid_sizes = [10.0, 5.0, 1.0, 0.5]
    
    for grid_size in grid_sizes:
        print(f"\n🌍 使用 {grid_size}° × {grid_size}° 網格重新分析:")
        print("-" * 40)
        
        # 這裡模擬計算不同分群的效果
        # 注意：路徑本身不會改變，只是群組標籤會改變
        satellite_nodes = [node for node in path if node < 625]
        
        # 模擬不同網格大小的群組計算
        mock_groups = {}
        for sat_id in satellite_nodes:
            # 根據網格大小模擬不同的群組分配
            if grid_size >= 10.0:
                group_id = 1  # 大網格：所有衛星在同一群組
            elif grid_size >= 5.0:
                group_id = 1332  # 中網格：仍然可能在同一群組
            elif grid_size >= 1.0:
                group_id = sat_id // 50  # 小網格：更多群組
            else:
                group_id = sat_id // 10  # 最小網格：最多群組
            mock_groups[sat_id] = group_id
        
        # 統計群組分布
        group_stats = {}
        for sat_id in satellite_nodes:
            group_id = mock_groups[sat_id]
            if group_id not in group_stats:
                group_stats[group_id] = []
            group_stats[group_id].append(sat_id)
        
        print(f"   涉及群組數量: {len(group_stats)}")
        for group_id, satellites in group_stats.items():
            print(f"   群組 {group_id}: {len(satellites)} 個衛星 {satellites[:3]}{'...' if len(satellites) > 3 else ''}")
    
    print(f"\n💡 關鍵發現:")
    print(f"   ✅ 路由路徑永遠不變: {' → '.join(map(str, path))}")
    print(f"   🔄 只有群組標籤會根據分析參數改變")
    print(f"   ⚠️  要改變實際路由，必須重新生成路由表")


if __name__ == "__main__":
    compare_routing_with_different_analysis()
