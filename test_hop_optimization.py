#!/usr/bin/env python3
"""
測試跳數優化效果分析
分析修正後的PID演算法是否達到4跳的最佳性能
"""

import os
import sys

# Add the path to import satgen modules
sys.path.append(os.path.join(os.path.dirname(__file__), "paper", "satellite_networks_state"))

def analyze_path_efficiency():
    """分析修正後的路徑效率"""
    
    # 檢查路由文件位置
    base_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state"
    fwd_file = os.path.join(base_dir, "gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/dynamic_state_100ms_for_10s/fstate_1000000000.txt")
    
    if not os.path.exists(fwd_file):
        print(f"❌ 路由文件不存在: {fwd_file}")
        return
    
    print("🔍 分析修正後的路徑效率...")
    print("=" * 60)
    
    # 分析625→627路徑 (東京→上海)
    with open(fwd_file, 'r') as f:
        lines = f.readlines()
    
    # 尋找625的路由表項目到627
    found_625_to_627 = False
    path_info = None
    
    for line in lines:
        line = line.strip()
        if line.startswith("625,627,"):
            found_625_to_627 = True
            parts = line.split(',')
            if len(parts) >= 4:
                next_hop = parts[2]
                gsl_if = parts[3]
                path_info = (next_hop, gsl_if)
            break
    
    if not found_625_to_627:
        print("❌ 未找到 625→627 的路由項目")
        return
    
    if path_info:
        next_hop, gsl_if = path_info
        print(f"✅ 找到 625→627 路由:")
        print(f"   下一跳: {next_hop}")
        print(f"   GSL介面: {gsl_if}")
        
        # 追蹤完整路徑
        current = 625
        target = 627
        path = [current]
        hop_count = 0
        max_hops = 10  # 防止無限迴圈
        
        while current != target and hop_count < max_hops:
            # 尋找current的路由到target
            found_next = False
            for line in lines:
                line = line.strip()
                route_key = f"{current},{target},"
                if line.startswith(route_key):
                    parts = line.split(',')
                    if len(parts) >= 3:
                        next_hop = int(parts[2])
                        path.append(next_hop)
                        current = next_hop
                        hop_count += 1
                        found_next = True
                        break
            
            if not found_next:
                print(f"❌ 無法繼續追蹤路徑，在節點 {current} 卡住")
                break
        
        print(f"\n🛤️  完整路徑: {' → '.join(map(str, path))}")
        print(f"📊 跳數統計: {hop_count} 跳")
        
        # 與預期比較
        if hop_count <= 4:
            print(f"🎉 性能優化成功！達到 {hop_count} 跳，符合預期 ≤ 4 跳")
        else:
            print(f"⚠️  仍需優化：{hop_count} 跳 > 預期 4 跳")
        
        # 檢查是否使用相同PID內路由
        pid_213_satellites = [137, 138, 139, 163, 164, 189]  # PID 213的衛星
        
        same_pid_route = True
        for sat in path:
            if sat not in pid_213_satellites:
                same_pid_route = False
                break
        
        if same_pid_route:
            print("✅ 路由完全在PID 213內，符合同PID子圖路由設計")
        else:
            print("⚠️  路由跨越了PID邊界")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    analyze_path_efficiency()