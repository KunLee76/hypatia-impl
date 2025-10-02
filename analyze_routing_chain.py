#!/usr/bin/env python3
"""
简化的路由链分析脚本
"""

def analyze_routing_chain():
    routing_file = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/dynamic_state_100ms_for_10s/fstate_0.txt"
    
    print("🔍 分析路由链完整性")
    print("=" * 60)
    
    # 读取所有路由规则
    routes = {}
    with open(routing_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split(',')
                if len(parts) >= 3:
                    src, dst, next_hop = parts[0], parts[1], parts[2]
                    if src not in routes:
                        routes[src] = {}
                    routes[src][dst] = next_hop
    
    print(f"✅ 载入 {sum(len(dst_routes) for dst_routes in routes.values())} 条路由规则")
    print(f"✅ 涉及 {len(routes)} 个源节点")
    
    # 分析625→627的路由链
    print("\n🔗 625→627 路由链分析:")
    print("-" * 40)
    
    src = "625"
    dst = "627"
    
    if src in routes and dst in routes[src]:
        next_hop = routes[src][dst]
        print(f"  {src} → {dst}: next_hop = {next_hop}")
        
        # 检查next_hop是否能继续路由到dst
        if next_hop == dst:
            print("  ✅ 直接路由 (next_hop就是目标)")
        elif next_hop in routes and dst in routes[next_hop]:
            second_hop = routes[next_hop][dst]
            print(f"  {next_hop} → {dst}: next_hop = {second_hop}")
            
            if second_hop == dst:
                print("  ✅ 二跳路由链完整")
            else:
                print(f"  ⚠️  需要继续分析 {second_hop} → {dst}")
                if second_hop in routes and dst in routes[second_hop]:
                    third_hop = routes[second_hop][dst]
                    print(f"  {second_hop} → {dst}: next_hop = {third_hop}")
                    if third_hop == dst:
                        print("  ✅ 三跳路由链完整")
                    else:
                        print(f"  ❌ 路由链过长或循环: {third_hop}")
                else:
                    print(f"  ❌ 路由链断裂: {second_hop} 没有到 {dst} 的路由")
        else:
            print(f"  ❌ 路由链断裂: {next_hop} 没有到 {dst} 的路由")
    else:
        print(f"  ❌ 没有找到 {src} → {dst} 的路由")
    
    # 分析189的所有路由
    print(f"\n🛰️ 卫星189的所有出站路由:")
    print("-" * 40)
    
    sat_189 = "189"
    if sat_189 in routes:
        destinations = routes[sat_189]
        print(f"  卫星189有 {len(destinations)} 条出站路由:")
        for dst, next_hop in sorted(destinations.items(), key=lambda x: int(x[0])):
            if next_hop == dst:
                print(f"    189 → GS{dst}: 直连")
            else:
                print(f"    189 → GS{dst}: 经过卫星{next_hop}")
    else:
        print("  ❌ 卫星189没有任何出站路由")
    
    # 检查直接服务的地面站
    print(f"\n📡 直连地面站分析:")
    print("-" * 40)
    
    direct_connections = {}
    for src in routes:
        for dst, next_hop in routes[src].items():
            if next_hop == dst and src != dst:  # 直连且不是自环
                if src not in direct_connections:
                    direct_connections[src] = []
                direct_connections[src].append(dst)
    
    key_satellites = ["625", "189", "139"]
    for sat in key_satellites:
        if sat in direct_connections:
            gs_list = sorted(direct_connections[sat], key=int)
            print(f"  卫星{sat}直连地面站: {gs_list}")
        else:
            print(f"  卫星{sat}: 无直连地面站")

if __name__ == "__main__":
    analyze_routing_chain()