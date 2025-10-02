#!/usr/bin/env python3
"""
分析Free One的最優路徑：625→383→382→627
看看為什麼它比我們的路徑更短
"""

import os
import sys

def analyze_free_one_optimal_path():
    """分析Free One的最優路徑策略"""
    
    print("🔍 分析Free One最優路徑: 625→383→382→627")
    print("=" * 70)
    
    base_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state"
    
    # 檢查地面站625和627的位置
    gs_file = os.path.join(base_dir, "gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/ground_stations.txt")
    
    print("📡 檢查地面站位置:")
    if os.path.exists(gs_file):
        with open(gs_file, 'r') as f:
            lines = f.readlines()
        
        for line in lines[1:]:  # 跳過標題
            parts = line.strip().split()
            if len(parts) >= 4:
                try:
                    gs_id = int(parts[0])
                    if gs_id in [625, 627]:
                        lat, lon = float(parts[2]), float(parts[3])
                        print(f"   地面站{gs_id}: lat={lat:.2f}, lon={lon:.2f}")
                except ValueError:
                    continue
    
    # 檢查衛星383和382在不同時間點的服務範圍
    print(f"\n🛰️ 檢查衛星383和382在時間0的服務範圍:")
    
    # 從Free One的路由文件看它們如何連接到地面站
    free_file = os.path.join(base_dir, "gen_data/25x25_algorithm_free_one_only_over_isls_fast/dynamic_state_100ms_for_10s/fstate_0.txt")
    
    if os.path.exists(free_file):
        with open(free_file, 'r') as f:
            line = f.read().strip()
            print(f"   Free One路由: {line}")
        
        # 解析路由：625,627,383,0,4
        # 625→383 (GSL上行), 383→382 (ISL), 382→627 (GSL下行)
        print(f"\n📊 路徑分析:")
        print(f"   625 → 383: GSL上行連接")
        print(f"   383 → 382: ISL連接 (1跳)")
        print(f"   382 → 627: GSL下行連接")
        print(f"   總跳數: 3跳 (包含GSL)")
        print(f"   ISL跳數: 1跳 (衛星間)")
    
    # 檢查我們的算法為什麼不能使用383→382路徑
    print(f"\n🤔 分析為什麼我們不能使用383→382路徑:")
    
    # 檢查383和382的PID歸屬
    # 需要重新運行我們的算法在時間0看看383、382的PID分配
    
    print(f"   可能的原因:")
    print(f"   1. 383和382不在PID 213內，我們的統一策略阻止了跨PID路由")
    print(f"   2. 在時間0，625或627的服務衛星不同")
    print(f"   3. 我們的路徑包含策略強制使用189→139路徑")
    
    # 檢查在時間0，625和627實際連接到哪些衛星
    print(f"\n📡 時間0的GSL連接分析:")
    
    # 檢查我們算法中625和627的GSL連接
    vpid_file = os.path.join(base_dir, "gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/dynamic_state_100ms_for_10s/fstate_0.txt")
    
    if os.path.exists(vpid_file):
        print("   我們的算法GSL連接:")
        os.system(f"grep '^625,' {vpid_file} | head -5")
        print("   625連接模式:")
        os.system(f"grep '^627,' {vpid_file} | head -5")
    
    print(f"\n💡 優化建議:")
    print(f"   1. 在同PID內路由時，應該允許使用全局最短路徑作為選項")
    print(f"   2. 檢查GSL連接是否限制了路徑選擇")
    print(f"   3. 考慮在時間0使用與Free One相同的衛星對")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    analyze_free_one_optimal_path()