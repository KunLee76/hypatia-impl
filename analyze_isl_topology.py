#!/usr/bin/env python3
"""
深度分析ISL拓撲中163和137的直接連接
找出為什麼跳數優化沒有生效的根本原因
"""

import os
import sys
import networkx as nx

# Add the path to import satgen modules
sys.path.append(os.path.join(os.path.dirname(__file__), "paper", "satellite_networks_state"))

def analyze_isl_connectivity():
    """深度分析ISL拓撲和路由選擇"""
    
    # 檢查ISL文件
    base_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state"
    isl_file = os.path.join(base_dir, "gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/isls.txt")
    
    if not os.path.exists(isl_file):
        print(f"❌ ISL文件不存在: {isl_file}")
        return
    
    print("🔗 分析ISL拓撲連接...")
    print("=" * 80)
    
    # 讀取ISL連接
    G = nx.Graph()
    key_satellites = [189, 163, 137, 138, 139, 164]  # PID 213相關的衛星
    isl_connections = []
    
    with open(isl_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                sat1, sat2 = int(parts[0]), int(parts[1])
                G.add_edge(sat1, sat2)
                
                # 記錄關鍵衛星的連接
                if sat1 in key_satellites and sat2 in key_satellites:
                    isl_connections.append((sat1, sat2))
    
    print(f"📊 關鍵衛星間的ISL連接 (PID 213相關):")
    for conn in sorted(isl_connections):
        print(f"   {conn[0]} ↔ {conn[1]}")
    
    # 檢查每個衛星的鄰居
    print(f"\n🔍 關鍵衛星的鄰居分析:")
    for sat in key_satellites:
        neighbors = list(G.neighbors(sat))
        key_neighbors = [n for n in neighbors if n in key_satellites]
        print(f"   衛星 {sat}: 總鄰居 {len(neighbors)}, 關鍵鄰居 {key_neighbors}")
    
    # 特別檢查163和137的連接
    print(f"\n🚨 特別分析 163 ↔ 137 連接:")
    if G.has_edge(163, 137):
        print("   ✅ 163 和 137 有直接ISL連接")
    else:
        print("   ❌ 163 和 137 沒有直接ISL連接")
        # 找最短路徑
        try:
            path_163_137 = nx.shortest_path(G, 163, 137)
            print(f"   📍 163→137 最短路徑: {' → '.join(map(str, path_163_137))}")
            print(f"   📏 路徑長度: {len(path_163_137) - 1} 跳")
        except nx.NetworkXNoPath:
            print("   💥 163 和 137 完全不連通！")
    
    # 檢查完整的189→139路徑
    print(f"\n🛤️  分析完整路徑 189→139:")
    try:
        path_189_139 = nx.shortest_path(G, 189, 139)
        print(f"   最短路徑: {' → '.join(map(str, path_189_139))}")
        print(f"   路徑長度: {len(path_189_139) - 1} 跳")
        
        # 檢查是否與預期的189→163→137→138→139一致
        expected_path = [189, 163, 137, 138, 139]
        if path_189_139 == expected_path:
            print("   ✅ 路徑與預期一致")
        else:
            print(f"   ⚠️  路徑不同於預期 {expected_path}")
            
        # 檢查預期路徑是否存在
        path_exists = True
        for i in range(len(expected_path) - 1):
            if not G.has_edge(expected_path[i], expected_path[i+1]):
                print(f"   ❌ 預期路徑中斷: {expected_path[i]} ↔ {expected_path[i+1]} 無連接")
                path_exists = False
        
        if path_exists:
            print("   ✅ 預期路徑的所有連接都存在")
            
    except nx.NetworkXNoPath:
        print("   💥 189 和 139 完全不連通！")
    
    # 分析為什麼選擇了164而不是137
    print(f"\n🤔 分析路由選擇邏輯:")
    if G.has_edge(163, 164) and G.has_edge(163, 137):
        print("   163 同時連接到 164 和 137")
        print("   可能的原因：")
        print("   1. NetworkX shortest_path 在多條等長路徑時選擇節點ID較小的")
        print("   2. 演算法中的路徑選擇邏輯問題")
        print("   3. PID內子圖構建問題")
    elif G.has_edge(163, 164) and not G.has_edge(163, 137):
        print("   163 只連接到 164，沒有連接到 137")
        print("   這可能是ISL拓撲的問題")
    elif G.has_edge(163, 137) and not G.has_edge(163, 164):
        print("   163 只連接到 137，沒有連接到 164")
        print("   路由應該會選擇 137")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    analyze_isl_connectivity()