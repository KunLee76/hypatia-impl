#!/usr/bin/env python3
"""
分析ISL拓撲中163和139的直接連接情況
確認為什麼選擇了4跳而不是2跳的路徑
"""

import os
import networkx as nx

def analyze_163_139_connection():
    """分析163→139的連接選項"""
    
    base_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state"
    isl_file = os.path.join(base_dir, "gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/isls.txt")
    
    print("🔍 分析163→139的ISL連接選項...")
    print("=" * 60)
    
    # 載入ISL拓撲
    G = nx.Graph()
    with open(isl_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                sat1, sat2 = int(parts[0]), int(parts[1])
                G.add_edge(sat1, sat2)
    
    # 檢查163的所有鄰居
    neighbors_163 = list(G.neighbors(163))
    neighbors_139 = list(G.neighbors(139))
    
    print(f"📡 衛星163的鄰居: {sorted(neighbors_163)}")
    print(f"📡 衛星139的鄰居: {sorted(neighbors_139)}")
    
    # 檢查163和139是否直接相連
    direct_connection = G.has_edge(163, 139)
    print(f"\n🔗 163↔139直接連接: {'✅ YES' if direct_connection else '❌ NO'}")
    
    if direct_connection:
        print("   → 163和139有直接ISL連接，應該可以2跳路由！")
        print("   → 問題可能在算法的路徑選擇邏輯")
    else:
        print("   → 163和139沒有直接連接，需要透過中繼")
        
        # 找所有163→139的路徑
        try:
            all_paths = list(nx.all_shortest_paths(G, 163, 139))
            print(f"   → 163→139的所有最短路徑:")
            for i, path in enumerate(all_paths):
                hops = len(path) - 1
                print(f"      路徑{i+1}: {' → '.join(map(str, path))} ({hops}跳)")
                
            # 檢查是否有更短的路徑
            shortest_length = nx.shortest_path_length(G, 163, 139)
            print(f"   → 最短路徑長度: {shortest_length} 跳")
            
        except nx.NetworkXNoPath:
            print("   → ❌ 163和139完全不連通")
    
    # 檢查PID 213內的完整子圖連接
    pid_213_sats = [137, 138, 139, 163, 164, 189]
    subgraph = G.subgraph(pid_213_sats)
    
    print(f"\n🗂️  PID 213子圖分析:")
    print(f"   衛星: {pid_213_sats}")
    print(f"   子圖邊數: {subgraph.number_of_edges()}")
    
    # 檢查子圖中189→139的路徑
    if nx.has_path(subgraph, 189, 139):
        subgraph_paths = list(nx.all_shortest_paths(subgraph, 189, 139))
        print(f"   189→139子圖最短路徑:")
        for i, path in enumerate(subgraph_paths):
            hops = len(path) - 1
            print(f"      路徑{i+1}: {' → '.join(map(str, path))} ({hops}跳)")
        
        # 與algorithm_free_one比較
        if len(subgraph_paths) > 1:
            print(f"   ⚠️  有多條等長路徑，NetworkX可能選擇了不同的路徑")
            
            # 檢查哪條路徑包含163→139直接連接
            for i, path in enumerate(subgraph_paths):
                if len(path) >= 3:
                    segments = [(path[j], path[j+1]) for j in range(len(path)-1)]
                    if (163, 139) in segments:
                        print(f"      路徑{i+1}包含163→139直接連接")
    
    # 檢查具體的ISL連接
    key_connections = [
        (163, 139), (163, 137), (137, 139), 
        (163, 164), (164, 139), (137, 138), (138, 139)
    ]
    
    print(f"\n🔗 關鍵ISL連接檢查:")
    for sat1, sat2 in key_connections:
        connected = G.has_edge(sat1, sat2)
        print(f"   {sat1}↔{sat2}: {'✅' if connected else '❌'}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    analyze_163_139_connection()