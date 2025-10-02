#!/usr/bin/env python3
"""
分析卫星189到139之间的最短路径
"""

import networkx as nx

def load_isl_network(isls_file):
    """加载ISL网络拓扑"""
    G = nx.Graph()
    
    with open(isls_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                sat1, sat2 = int(parts[0]), int(parts[1])
                # 只考虑卫星节点 (0-624)
                if sat1 <= 624 and sat2 <= 624:
                    G.add_edge(sat1, sat2)
    
    return G

def analyze_path_189_139():
    """分析189到139的路径"""
    isls_file = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/isls.txt"
    
    print("🛰️ 分析卫星189到139的连通性")
    print("=" * 50)
    
    # 加载网络
    G = load_isl_network(isls_file)
    print(f"📡 ISL网络: {G.number_of_nodes()} 卫星, {G.number_of_edges()} 连接")
    
    # 检查189和139的邻居
    if 189 in G:
        neighbors_189 = list(G.neighbors(189))
        print(f"🔗 卫星189的邻居: {neighbors_189}")
    else:
        print("❌ 卫星189不在网络中")
        return
        
    if 139 in G:
        neighbors_139 = list(G.neighbors(139))
        print(f"🔗 卫星139的邻居: {neighbors_139}")
    else:
        print("❌ 卫星139不在网络中")
        return
    
    # 检查是否连通
    if nx.has_path(G, 189, 139):
        try:
            path = nx.shortest_path(G, 189, 139)
            print(f"✅ 最短路径 189→139: {' → '.join(map(str, path))}")
            print(f"📏 路径长度: {len(path)-1} 跳")
            
            # 分析路径中每一跳
            for i in range(len(path)-1):
                print(f"   跳{i+1}: {path[i]} → {path[i+1]}")
                
        except nx.NetworkXNoPath:
            print("❌ 无路径连接189和139")
    else:
        print("❌ 189和139不连通")
    
    # 检查是否在同一个连通分量中
    if nx.is_connected(G):
        print("✅ 整个ISL网络是连通的")
    else:
        # 找到189和139所在的连通分量
        components = list(nx.connected_components(G))
        comp_189 = None
        comp_139 = None
        
        for i, comp in enumerate(components):
            if 189 in comp:
                comp_189 = i
            if 139 in comp:
                comp_139 = i
                
        print(f"🔍 网络有 {len(components)} 个连通分量")
        print(f"   卫星189在分量 {comp_189}")  
        print(f"   卫星139在分量 {comp_139}")

if __name__ == "__main__":
    analyze_path_189_139()