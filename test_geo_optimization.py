#!/usr/bin/env python3
"""
測試動態跨軌道ISL地理權重優化效果
驗證625→626路由是否從10跳優化到更短路徑
"""

import os
import sys

# 設置路徑
project_root = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia"
sys.path.append(f"{project_root}/satgenpy")

def test_625_to_626_optimization():
    """測試625→626路由優化效果"""
    
    print("=== 動態跨軌道ISL地理權重優化測試 ===")
    print()
    
    # 測試數據路徑
    test_data_dir = f"{project_root}/temp_test_188_routing"
    
    # 檢查測試數據是否存在
    routing_file = f"{test_data_dir}/fstate_188.txt"
    if not os.path.exists(routing_file):
        print(f"❌ 測試數據不存在: {routing_file}")
        print("請先生成測試數據")
        return False
    
    print("🔍 **讀取路由表...**")
    
    # 讀取路由表
    fstate = {}
    with open(routing_file, 'r') as f:
        for line in f:
            if 'int(' in line and '->' in line:
                parts = line.strip().split(' -> ')
                if len(parts) >= 2:
                    src_part = parts[0].split('int(')[1].split(')')[0]
                    dst_part = parts[1].split('int(')[1].split(')')[0] if 'int(' in parts[1] else parts[1].strip()
                    
                    try:
                        src = int(src_part)
                        if dst_part.isdigit():
                            dst = int(dst_part)
                            fstate[(src, dst)] = True
                    except Exception:
                        continue
    
    print(f"✅ 讀取到 {len(fstate)} 條路由規則")
    print()
    
    # 分析625→626路由
    print("🎯 **分析625→626路由路徑...**")
    
    # 德里(625) -> 莫斯科(626)的地面站ID轉換
    num_satellites = 625  # 假設有625個衛星
    gs_625_node_id = num_satellites + 625  # 德里地面站節點ID
    gs_626_node_id = num_satellites + 626  # 莫斯科地面站節點ID
    
    print(f"德里地面站節點ID: {gs_625_node_id}")
    print(f"莫斯科地面站節點ID: {gs_626_node_id}")
    print()
    
    # 查找625→626的路由路徑
    route_found = False
    route_hops = 0
    current_node = gs_625_node_id
    route_path = [current_node]
    
    print("🔍 **追蹤路由路徑：**")
    
    visited = set()
    max_hops = 20  # 防止無限循環
    
    while current_node != gs_626_node_id and route_hops < max_hops:
        if current_node in visited:
            print("⚠️ 檢測到路由循環")
            break
        visited.add(current_node)
        
        # 查找下一跳
        next_hop = None
        for (src, dst) in fstate:
            if src == current_node:
                next_hop = dst
                break
        
        if next_hop is None:
            print(f"❌ 在節點 {current_node} 找不到下一跳")
            break
        
        route_hops += 1
        current_node = next_hop
        route_path.append(current_node)
        
        # 顯示路由跳躍
        if current_node >= num_satellites:
            print(f"步驟 {route_hops}: 節點 {route_path[-2]} → 地面站 {current_node} (ID: {current_node - num_satellites})")
        else:
            print(f"步驟 {route_hops}: 節點 {route_path[-2]} → 衛星 {current_node}")
    
    if current_node == gs_626_node_id:
        route_found = True
        print(f"✅ **路由成功！總跳數: {route_hops}**")
    else:
        print(f"❌ **路由失敗！已搜索 {route_hops} 跳**")
    
    print()
    print("📊 **完整路由路徑：**")
    for i, node in enumerate(route_path):
        if node >= num_satellites:
            print(f"  {i}: 地面站 {node - num_satellites} (節點ID: {node})")
        else:
            print(f"  {i}: 衛星 {node}")
    
    print()
    
    # 分析結果
    if route_found:
        if route_hops <= 8:
            print("🎉 **優秀！路由已優化到8跳以內**")
        elif route_hops <= 10:
            print("✅ **良好！路由跳數合理**")
        else:
            print("⚠️ **需要改進：路由跳數仍然較多**")
    else:
        print("❌ **路由失敗：無法到達目標**")
    
    return route_found

def analyze_isl_usage():
    """分析ISL使用情況"""
    
    print("\n=== ISL使用分析 ===")
    
    # 讀取Plus Grid ISL拓撲
    print("🔍 **分析Plus Grid ISL拓撲...**")
    
    NUM_SATS_PER_ORB = 25
    NUM_ORBS = 25
    
    # 統計同軌道vs跨軌道ISL
    same_orbit_isls = 0
    cross_orbit_isls = 0
    
    for sat1 in range(NUM_ORBS * NUM_SATS_PER_ORB):
        orbit1 = sat1 // NUM_SATS_PER_ORB
        pos1 = sat1 % NUM_SATS_PER_ORB
        
        # Plus Grid連接：4個鄰居
        neighbors = []
        
        # 同軌道前後
        neighbors.append((orbit1 * NUM_SATS_PER_ORB + (pos1 + 1) % NUM_SATS_PER_ORB))
        neighbors.append((orbit1 * NUM_SATS_PER_ORB + (pos1 - 1) % NUM_SATS_PER_ORB))
        
        # 跨軌道（相鄰軌道相同位置）
        if orbit1 < NUM_ORBS - 1:
            neighbors.append((orbit1 + 1) * NUM_SATS_PER_ORB + pos1)
        if orbit1 > 0:
            neighbors.append((orbit1 - 1) * NUM_SATS_PER_ORB + pos1)
        
        for sat2 in neighbors:
            if sat2 < NUM_ORBS * NUM_SATS_PER_ORB:
                orbit2 = sat2 // NUM_SATS_PER_ORB
                if orbit1 == orbit2:
                    same_orbit_isls += 1
                else:
                    cross_orbit_isls += 1
    
    same_orbit_isls //= 2  # 避免重複計算
    cross_orbit_isls //= 2
    
    print(f"📊 同軌道ISL數量: {same_orbit_isls}")
    print(f"📊 跨軌道ISL數量: {cross_orbit_isls}")
    print(f"📊 總ISL數量: {same_orbit_isls + cross_orbit_isls}")
    print(f"📊 跨軌道ISL比例: {cross_orbit_isls / (same_orbit_isls + cross_orbit_isls) * 100:.1f}%")
    
    return True

if __name__ == "__main__":
    print("🚀 開始測試動態跨軌道ISL地理權重優化...")
    print()
    
    success = test_625_to_626_optimization()
    analyze_isl_usage()
    
    print("\n=== 測試總結 ===")
    if success:
        print("✅ 測試完成")
        print("💡 提示：比較修改前後的路由跳數變化")
    else:
        print("❌ 測試未完全成功")
        print("💡 提示：檢查路由生成是否正確")
    
    print()
    print("🔧 **下一步操作建議：**")
    print("1. 運行新的路由生成算法")
    print("2. 生成新的測試數據")
    print("3. 比較優化前後的路由差異")
    print("4. 分析地理權重的實際影響")