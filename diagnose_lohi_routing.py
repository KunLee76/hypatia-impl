#!/usr/bin/env python3
"""
診斷 LoHi 路由問題
"""

# 讀取 fstate
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

# 診斷路由
def diagnose_route(src, dst, fstate):
    print(f"\n診斷路由：{src} -> {dst}")
    current = src
    visited = set()
    hops = 0
    
    while current != dst and hops < 20:
        if current in visited:
            print(f"  ❌ 循環！節點 {current} 已訪問過")
            print(f"  訪問序列：{visited}")
            return
        
        visited.add(current)
        next_hop = fstate.get((current, dst))
        
        if next_hop is None:
            print(f"  ❌ 在節點 {current} 找不到到 {dst} 的路由條目")
            return
        
        if next_hop == -1:
            print(f"  ❌ 在節點 {current} 的路由被標記為 -1 (不可達)")
            return
        
        print(f"  {current} -> {next_hop}")
        current = next_hop
        hops += 1
    
    if current == dst:
        print(f"  ✓ 成功到達目的地，總共 {hops} 跳")
    else:
        print(f"  ❌ 超過 20 跳仍未到達")

# 主程式
if __name__ == "__main__":
    fstate_file = "/home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_lohi/dynamic_state_100ms_for_20s/fstate_0.txt"
    
    print("載入 fstate_0.txt...")
    fstate = load_fstate(fstate_file)
    print(f"載入 {len(fstate)} 個路由條目")
    
    # 診斷東京 -> 德里
    diagnose_route(1584, 1585, fstate)
    
    # 診斷反向
    diagnose_route(1585, 1584, fstate)
    
    # 檢查是否存在 287 的路由問題
    print("\n" + "=" * 80)
    print("檢查節點 287 的路由：")
    for dst in [1584, 1585]:
        entry = fstate.get((287, dst))
        if entry is not None:
            print(f"  (287, {dst}) -> {entry}")
