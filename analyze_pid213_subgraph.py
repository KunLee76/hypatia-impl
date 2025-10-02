#!/usr/bin/env python3
"""
分析PID 213子图的连通性问题
"""

import networkx as nx

def analyze_pid213_subgraph():
    """分析PID 213内部的连通性"""
    
    print("🔍 分析PID 213子图连通性")
    print("=" * 50)
    
    # 根據修正後的路徑包含策略，PID 213包含完整連接路徑：[137, 138, 139, 163, 164, 188, 189, 213, 358, ...]
    # 從算法輸出可以看到："衛星列表: [137, 138, 139, 163, 164]..." 且總共10個衛星
    pid213_satellites = [137, 138, 139, 163, 164, 188, 189, 213, 358]  # 這是我們看到的路徑衛星
    # 注意：可能還有第10個衛星，但從當前信息可以確定這9個
    print(f"📡 PID 213卫星: {pid213_satellites}")
    
    # 加载ISL网络
    isls_file = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/isls.txt"
    
    G = nx.Graph()
    with open(isls_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                sat1, sat2 = int(parts[0]), int(parts[1])
                if sat1 <= 624 and sat2 <= 624:
                    G.add_edge(sat1, sat2)
    
    # 创建PID 213的子图
    pid213_subgraph = G.subgraph(pid213_satellites)
    
    print(f"🌐 PID 213子图信息:")
    print(f"   节点数: {pid213_subgraph.number_of_nodes()}")
    print(f"   边数: {pid213_subgraph.number_of_edges()}")
    print(f"   是否连通: {nx.is_connected(pid213_subgraph)}")
    
    # 检查各节点的度数
    print(f"\n🔗 节点连接度:")
    for sat in pid213_satellites:
        if sat in pid213_subgraph:
            degree = pid213_subgraph.degree(sat)
            neighbors = list(pid213_subgraph.neighbors(sat))
            print(f"   卫星{sat}: 度数={degree}, 邻居={neighbors}")
        else:
            print(f"   卫星{sat}: 不在子图中")
    
    # 检查189到139的路径
    print(f"\n🛤️ 189到139的路径分析:")
    if 189 in pid213_subgraph and 139 in pid213_subgraph:
        if nx.has_path(pid213_subgraph, 189, 139):
            try:
                path = nx.shortest_path(pid213_subgraph, 189, 139)
                print(f"   ✅ 子图内路径: {' → '.join(map(str, path))}")
            except nx.NetworkXNoPath:
                print(f"   ❌ 子图内无路径")
        else:
            print(f"   ❌ 子图内189和139不连通")
            
            # 检查连通分量
            components = list(nx.connected_components(pid213_subgraph))
            print(f"   🔍 子图有{len(components)}个连通分量:")
            for i, comp in enumerate(components):
                comp_list = sorted(list(comp))
                print(f"     分量{i+1}: {comp_list}")
                if 189 in comp:
                    print(f"       (189在此分量)")
                if 139 in comp:
                    print(f"       (139在此分量)")
    else:
        print(f"   ❌ 189或139不在PID 213子图中")
    
    # 检查原始全图中的路径（用于对比）
    print(f"\n🌍 原始全图中189→139路径:")
    if nx.has_path(G, 189, 139):
        path = nx.shortest_path(G, 189, 139)
        print(f"   完整路径: {' → '.join(map(str, path))}")
        print(f"   路径长度: {len(path)-1} 跳")
        
        # 检查路径中哪些节点不在PID 213中
        missing_nodes = [node for node in path if node not in pid213_satellites]
        if missing_nodes:
            print(f"   ⚠️ 路径中不在PID 213的节点: {missing_nodes}")
        else:
            print(f"   ✅ 路径中所有节点都在PID 213中")

if __name__ == "__main__":
    analyze_pid213_subgraph()