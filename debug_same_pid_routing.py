#!/usr/bin/env python3
"""
檢查625→627路由的uplink/downlink衛星分配
確認PID 213內的子圖路由是否正確
"""

import os
import sys
import networkx as nx

def analyze_uplink_downlink():
    """分析625→627的uplink/downlink衛星分配"""
    
    base_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state"
    gs_file = os.path.join(base_dir, "gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/ground_stations.txt")
    
    if not os.path.exists(gs_file):
        print(f"❌ 地面站文件不存在: {gs_file}")
        return
    
    print("🔍 分析625→627的uplink/downlink衛星分配...")
    print("=" * 70)
    
    # 讀取地面站文件
    with open(gs_file, 'r') as f:
        lines = f.readlines()
    
    # 查找625和627地面站的資訊
    gs_625_info = None
    gs_627_info = None
    
    for line in lines[1:]:  # 跳過標題行
        parts = line.strip().split()
        if len(parts) >= 6:
            gs_id = int(parts[0])
            if gs_id == 625:
                gs_625_info = {
                    'id': gs_id,
                    'name': parts[1],
                    'lat': float(parts[2]),
                    'lon': float(parts[3]),
                    'elevation': float(parts[4]),
                    'cart_x': float(parts[5]),
                    'cart_y': float(parts[6]) if len(parts) > 6 else 0,
                    'cart_z': float(parts[7]) if len(parts) > 7 else 0
                }
            elif gs_id == 627:
                gs_627_info = {
                    'id': gs_id,
                    'name': parts[1], 
                    'lat': float(parts[2]),
                    'lon': float(parts[3]),
                    'elevation': float(parts[4]),
                    'cart_x': float(parts[5]),
                    'cart_y': float(parts[6]) if len(parts) > 6 else 0,
                    'cart_z': float(parts[7]) if len(parts) > 7 else 0
                }
    
    print(f"📡 地面站 625: {gs_625_info}")
    print(f"📡 地面站 627: {gs_627_info}")
    
    # 從路由檔案中直接檢查625→627的路由
    fwd_file = os.path.join(base_dir, "gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/dynamic_state_100ms_for_10s/fstate_1000000000.txt")
    
    print(f"\n🔍 檢查路由表中625→627的詳細路由...")
    
    with open(fwd_file, 'r') as f:
        lines = f.readlines()
    
    # 分析完整的路由鏈
    current = 625
    target = 627
    full_path = [625]
    
    hop_count = 0
    max_hops = 15  # 防止死迴圈
    
    while current != target and hop_count < max_hops:
        found_next = False
        
        for line in lines:
            line = line.strip()
            if line.startswith(f"{current},{target},"):
                parts = line.split(',')
                if len(parts) >= 3:
                    next_hop = int(parts[2])
                    print(f"   {current} → {next_hop} (target={target})")
                    
                    full_path.append(next_hop)
                    current = next_hop
                    hop_count += 1
                    found_next = True
                    break
        
        if not found_next:
            print(f"   ❌ 無法找到從 {current} 到 {target} 的路由")
            break
    
    print(f"\n🛤️  完整路徑追蹤: {' → '.join(map(str, full_path))}")
    print(f"📊 總跳數: {hop_count}")
    
    # 檢查ISL拓撲中PID 213子圖的最短路徑
    isl_file = os.path.join(base_dir, "gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/isls.txt")
    
    if os.path.exists(isl_file):
        print(f"\n🔗 PID 213子圖最短路徑驗證:")
        
        # 構建ISL圖
        G = nx.Graph()
        with open(isl_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    G.add_edge(int(parts[0]), int(parts[1]))
        
        # PID 213的衛星
        pid_213_sats = [137, 138, 139, 163, 164, 189]  # 根據之前的輸出
        
        # 構建PID 213子圖
        pid_subgraph = G.subgraph(pid_213_sats)
        
        print(f"   PID 213衛星: {pid_213_sats}")
        print(f"   子圖節點: {list(pid_subgraph.nodes())}")
        print(f"   子圖邊數: {pid_subgraph.number_of_edges()}")
        
        # 計算189→139的子圖最短路徑
        try:
            subgraph_path = nx.shortest_path(pid_subgraph, 189, 139)
            print(f"   189→139子圖最短路徑: {' → '.join(map(str, subgraph_path))}")
            print(f"   子圖路徑長度: {len(subgraph_path) - 1} 跳")
            
            if subgraph_path == [189, 163, 137, 138, 139]:
                print("   ✅ 子圖路徑符合預期")
            else:
                print("   ⚠️  子圖路徑與預期不同")
                
        except nx.NetworkXNoPath:
            print("   ❌ 189和139在子圖中不連通")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    analyze_uplink_downlink()