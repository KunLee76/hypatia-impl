#!/usr/bin/env python3

"""
調試地理權重優化是否正常工作
"""

import sys
import networkx as nx

# 添加路徑
sys.path.append('/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')

try:
    from satgen.dynamic_state.algorithm_hierarchical_virtual_pid_clean_fixed import VirtualPIDRouter
    print("✅ 成功導入算法模塊")
except ImportError as e:
    print(f"❌ 導入失敗: {e}")
    sys.exit(1)

def create_simple_test_graph():
    """創建簡單的測試圖，使用正確的Plus Grid衛星ID"""
    G = nx.Graph()
    
    # 使用正確的Plus Grid衛星ID
    # 軌道0: 0, 1, 2 (ID: 0, 1, 2)
    # 軌道1: 25, 26, 27 (ID: 25, 26, 27)
    satellites = [0, 1, 2, 25, 26, 27]
    
    for sat_id in satellites:
        G.add_node(sat_id)
    
    # 同軌道ISL (軌道0)
    G.add_edge(0, 1, weight=1000000.0)
    G.add_edge(1, 2, weight=1000000.0)
    G.add_edge(2, 0, weight=1000000.0)  # 環形
    
    # 同軌道ISL (軌道1)
    G.add_edge(25, 26, weight=1000000.0)
    G.add_edge(26, 27, weight=1000000.0)
    G.add_edge(27, 25, weight=1000000.0)  # 環形
    
    # 跨軌道ISL
    G.add_edge(0, 25, weight=1000000.0)  # 跨軌道
    G.add_edge(1, 26, weight=1000000.0)  # 跨軌道
    G.add_edge(2, 27, weight=1000000.0)  # 跨軌道
    
    return G

def mock_get_sat_latlon_simple(satellite_id, t):
    """簡化的位置函數，用於測試"""
    # 軌道0: 衛星ID 0-24
    # 軌道1: 衛星ID 25-49
    if satellite_id < 25:  # 軌道0
        pos = satellite_id
        lat = 30.0  # 北緯30度
        lon = -60.0 + (pos % 3) * 60.0  # -60, 0, 60度
    else:  # 軌道1
        pos = satellite_id - 25
        lat = -30.0  # 南緯30度
        lon = -60.0 + (pos % 3) * 60.0  # -60, 0, 60度
    
    return lat, lon

def test_geo_optimization_debug():
    """調試地理優化效果"""
    print("🔍 調試地理權重優化...")
    
    # 創建簡單測試圖
    test_graph = create_simple_test_graph()
    router = VirtualPIDRouter(grid_deg=15, allow_diagonal_neighbor=False)
    router.get_sat_latlon = mock_get_sat_latlon_simple
    
    # 模擬目標位置：北極 (90, 0)
    target_lat, target_lon = 90.0, 0.0
    t = 100.0
    
    print(f"🎯 目標位置: ({target_lat}, {target_lon})")
    print(f"📊 原始圖邊數: {test_graph.number_of_edges()}")
    print(f"📊 原始圖節點: {test_graph.number_of_nodes()}")
    
    # 打印原始權重
    print("\n📋 原始邊權重:")
    for u, v, data in test_graph.edges(data=True):
        sat_u_lat, sat_u_lon = router.get_sat_latlon(u, t)
        sat_v_lat, sat_v_lon = router.get_sat_latlon(v, t)
        is_cross = router._is_cross_orbit_isl(u, v)
        orbit_type = "跨軌道" if is_cross else "同軌道"
        print(f"  {u}({sat_u_lat:.1f},{sat_u_lon:.1f}) → {v}({sat_v_lat:.1f},{sat_v_lon:.1f}): {data['weight']:.0f} ({orbit_type})")
    
    # 創建地理優化圖
    print(f"\n🌍 創建地理優化圖 (目標: {target_lat}, {target_lon})...")
    try:
        geo_graph = router.create_geo_optimized_graph(test_graph, target_lat, target_lon, t)
        print("✅ 地理優化圖創建成功")
        
        # 打印優化後權重
        print("\n📋 優化後邊權重:")
        for u, v, data in geo_graph.edges(data=True):
            sat_u_lat, sat_u_lon = router.get_sat_latlon(u, t)
            sat_v_lat, sat_v_lon = router.get_sat_latlon(v, t)
            is_cross = router._is_cross_orbit_isl(u, v)
            orbit_type = "跨軌道" if is_cross else "同軌道"
            
            # 計算權重變化
            original_weight = test_graph[u][v]['weight']
            new_weight = data['weight']
            change = (new_weight - original_weight) / original_weight * 100
            
            print(f"  {u}({sat_u_lat:.1f},{sat_u_lon:.1f}) → {v}({sat_v_lat:.1f},{sat_v_lon:.1f}): {new_weight:.0f} ({change:+.1f}%) ({orbit_type})")
        
        # 檢查跨軌道邊緩存
        if hasattr(router, '_cross_orbit_edges') and router._cross_orbit_edges:
            print(f"\n🔍 跨軌道邊緩存: {len(router._cross_orbit_edges)} 條")
            for src, dst in router._cross_orbit_edges:
                print(f"  {src} → {dst}")
        else:
            print("\n⚠️  跨軌道邊緩存為空或未初始化")
        
        # 測試路由差異
        print("\n🛤️  測試路由: 0 → 27")
        try:
            original_path = nx.shortest_path(test_graph, 0, 27, weight='weight')
            geo_path = nx.shortest_path(geo_graph, 0, 27, weight='weight')
            
            original_cost = nx.shortest_path_length(test_graph, 0, 27, weight='weight')
            geo_cost = nx.shortest_path_length(geo_graph, 0, 27, weight='weight')
            
            print(f"  原始路徑: {' → '.join(map(str, original_path))} (成本: {original_cost:.0f})")
            print(f"  優化路徑: {' → '.join(map(str, geo_path))} (成本: {geo_cost:.0f})")
            
            if original_path != geo_path:
                print("✅ 地理優化改變了路由路徑")
            else:
                print("⚠️  地理優化沒有改變路由路徑")
                
        except nx.NetworkXNoPath:
            print("❌ 找不到路徑")
        
    except Exception as e:
        print(f"❌ 地理優化失敗: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函數"""
    print("🚀 開始地理權重優化調試...")
    print("=" * 60)
    
    test_geo_optimization_debug()
    
    print("\n" + "=" * 60)
    print("📋 調試完成")

if __name__ == "__main__":
    main()