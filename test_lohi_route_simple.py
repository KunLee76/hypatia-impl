#!/usr/bin/env python3
"""
簡化版路徑分析 - 只檢查幾個時間點以避免記憶體問題
"""

import sys
import os

# 讀取單個 fstate 文件
def load_fstate(filepath):
    fstate = {}
    with open(filepath, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 3:
                src = int(parts[0])
                dst = int(parts[1])
                next_hop = int(parts[2])
                fstate[(src, dst)] = next_hop
    return fstate

# 追蹤路徑
def get_path(src, dst, fstate, max_hops=100):
    path = [src]
    current = src
    for _ in range(max_hops):
        if current == dst:
            return path
        next_hop = fstate.get((current, dst))
        if next_hop is None or next_hop == -1:
            return None
        if next_hop in path:  # 偵測循環
            print(f"警告：在 {current} -> {dst} 發現路由循環")
            return None
        path.append(next_hop)
        current = next_hop
    print(f"警告：超過最大跳數 {max_hops}")
    return None

# 主程式
if __name__ == "__main__":
    base_dir = "/home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_lohi"
    dynamic_state_dir = f"{base_dir}/dynamic_state_100ms_for_20s"
    
    src = 1584  # 東京
    dst = 1585  # 德里
    
    # 只測試幾個時間點
    test_times_ns = [0, 1000000000, 5000000000, 10000000000, 19000000000]  # 0s, 1s, 5s, 10s, 19s
    
    print(f"分析路徑：{src} (東京) -> {dst} (德里)")
    print(f"算法：LoHi (p×s = 6×10)")
    print("=" * 80)
    
    for t_ns in test_times_ns:
        fstate_file = f"{dynamic_state_dir}/fstate_{t_ns}.txt"
        
        if not os.path.exists(fstate_file):
            print(f"\n時間 {t_ns/1e9:.1f}s: 文件不存在")
            continue
        
        print(f"\n時間 {t_ns/1e9:.1f}s:")
        
        # 載入 fstate（每次清空）
        fstate = load_fstate(fstate_file)
        print(f"  載入 {len(fstate)} 個路由條目")
        
        # 計算路徑
        path = get_path(src, dst, fstate)
        
        if path:
            print(f"  路徑長度：{len(path)} 跳")
            print(f"  路徑：{' -> '.join(map(str, path))}")
        else:
            print(f"  ❌ 無法找到路徑")
        
        # 反向路徑
        path_back = get_path(dst, src, fstate)
        if path_back:
            print(f"  反向路徑長度：{len(path_back)} 跳")
        else:
            print(f"  ❌ 無法找到反向路徑")
        
        # 清理記憶體
        del fstate
    
    print("\n" + "=" * 80)
    print("分析完成！")
