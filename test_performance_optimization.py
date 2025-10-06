#!/usr/bin/env python3

"""
性能測試腳本：測試Virtual PID算法的性能優化效果
"""

import time
import sys
import networkx as nx

# 添加路徑
sys.path.append('/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')

# 嘗試導入算法模塊
try:
    from satgen.dynamic_state.algorithm_hierarchical_virtual_pid_clean_fixed import VirtualPIDRouter
    print("✅ 成功導入優化後的算法模塊")
except ImportError as e:
    print(f"❌ 導入算法模塊失敗: {e}")
    sys.exit(1)

def create_test_graph(num_satellites=625):
    """創建測試用的衛星網絡圖"""
    print(f"🔧 創建 {num_satellites} 衛星的測試網絡...")
    
    # 創建Plus Grid拓撲
    G = nx.Graph()
    
    # 添加節點
    for i in range(num_satellites):
        G.add_node(i)
    
    # 添加同軌道ISL（每個軌道25顆衛星）
    satellites_per_orbit = 25
    num_orbits = num_satellites // satellites_per_orbit
    
    for orbit in range(num_orbits):
        for pos in range(satellites_per_orbit):
            sat_id = orbit * satellites_per_orbit + pos
            next_sat = orbit * satellites_per_orbit + ((pos + 1) % satellites_per_orbit)
            G.add_edge(sat_id, next_sat, weight=1000000.0)
    
    # 添加跨軌道ISL（49%比例）
    cross_orbit_edges = 0
    target_cross_orbit = int(0.49 * satellites_per_orbit * num_orbits * 2)  # 約600條
    
    for orbit in range(num_orbits - 1):
        for pos in range(satellites_per_orbit):
            if cross_orbit_edges >= target_cross_orbit:
                break
            sat_id = orbit * satellites_per_orbit + pos
            next_orbit_sat = (orbit + 1) * satellites_per_orbit + pos
            G.add_edge(sat_id, next_orbit_sat, weight=1000000.0)
            cross_orbit_edges += 1
    
    print(f"📊 創建了 {G.number_of_nodes()} 個節點, {G.number_of_edges()} 條邊")
    return G

def create_mock_latlon_function():
    """創建模擬的衛星位置函數"""
    import math
    
    def mock_get_sat_latlon(satellite_id, t):
        # 簡化的位置計算
        orbit_period = 5760  # 96分鐘
        orbit_inclination = 53
        
        orbit_phase = (t / orbit_period) % 1.0
        lat = orbit_inclination * math.sin(2 * math.pi * orbit_phase)
        lon = (360 * orbit_phase) % 360 - 180
        
        # 衛星ID偏移
        sat_offset = satellite_id * 2.88
        lon = (lon + sat_offset) % 360 - 180
        
        return lat, lon
    
    return mock_get_sat_latlon

def create_mock_neighbors_function(graph):
    """創建模擬的鄰居函數"""
    def mock_get_sat_neighbors(satellite_id, t):
        return list(graph.neighbors(satellite_id))
    return mock_get_sat_neighbors

def test_geo_optimization_performance():
    """測試地理優化的性能"""
    print("\n🎯 測試地理權重優化性能...")
    
    # 創建測試圖和路由器
    test_graph = create_test_graph(625)
    router = VirtualPIDRouter(grid_deg=15, allow_diagonal_neighbor=False)
    
    # 設置模擬函數
    router.get_sat_latlon = create_mock_latlon_function()
    router.get_sat_neighbors = create_mock_neighbors_function(test_graph)
    
    # 測試參數
    num_ground_stations = 10  # 減少測試數量以便快速測試
    simulation_time = 100.0
    
    print(f"📊 測試參數: {len(test_graph.nodes())} 衛星, {num_ground_stations} 地面站")
    
    # 模擬地面站位置
    ground_stations = []
    for i in range(num_ground_stations):
        lat = -60 + (120 * i / (num_ground_stations - 1))  # -60到60度
        lon = -120 + (240 * i / (num_ground_stations - 1))  # -120到120度
        ground_stations.append((lat, lon))
    
    # 性能測試
    start_time = time.time()
    optimized_graphs = 0
    
    try:
        for gs_lat, gs_lon in ground_stations:
            # 測試地理優化圖創建
            router.create_geo_optimized_graph(
                test_graph, gs_lat, gs_lon, simulation_time
            )
            optimized_graphs += 1
            
            # 檢查緩存效果
            cache_size = len(router._geo_graph_cache) if hasattr(router, '_geo_graph_cache') else 0
            print(f"🔍 第 {optimized_graphs} 次優化完成, 緩存大小: {cache_size}")
    
    except Exception as e:
        print(f"❌ 測試過程中出錯: {e}")
        return False
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n📈 性能測試結果:")
    print(f"⏱️  總耗時: {total_time:.2f} 秒")
    print(f"🔄 優化圖數量: {optimized_graphs}")
    print(f"⚡ 平均每次優化: {total_time/optimized_graphs:.3f} 秒")
    
    # 檢查緩存效果
    if hasattr(router, '_geo_graph_cache'):
        cache_size = len(router._geo_graph_cache)
        print(f"💾 最終緩存大小: {cache_size}")
        if cache_size < optimized_graphs:
            print("✅ 緩存機制正常工作，避免了重複計算")
        else:
            print("⚠️  緩存可能沒有發揮最佳效果")
    
    # 性能評估
    if total_time < 10:  # 10秒以內認為性能良好
        print("🎉 性能優化效果良好！")
        return True
    else:
        print("⚠️  性能仍需進一步優化")
        return False

def test_cross_orbit_edge_detection():
    """測試跨軌道邊檢測的性能"""
    print("\n🔍 測試跨軌道邊檢測性能...")
    
    test_graph = create_test_graph(625)
    router = VirtualPIDRouter(grid_deg=15, allow_diagonal_neighbor=False)
    
    start_time = time.time()
    
    # 統計跨軌道邊
    cross_orbit_count = 0
    total_edges = test_graph.number_of_edges()
    
    for src, dst in test_graph.edges():
        if router._is_cross_orbit_isl(src, dst):
            cross_orbit_count += 1
    
    end_time = time.time()
    detection_time = end_time - start_time
    
    print("📊 跨軌道邊檢測結果:")
    print(f"🔄 總邊數: {total_edges}")
    print(f"🌐 跨軌道邊數: {cross_orbit_count}")
    print(f"📈 跨軌道比例: {cross_orbit_count/total_edges*100:.1f}%")
    print(f"⏱️  檢測耗時: {detection_time:.3f} 秒")
    
    return detection_time < 1.0  # 1秒以內認為性能良好

def main():
    """主測試函數"""
    print("🚀 開始Virtual PID算法性能優化測試...")
    print("=" * 60)
    
    # 測試跨軌道邊檢測性能
    edge_detection_ok = test_cross_orbit_edge_detection()
    
    # 測試地理優化性能
    geo_optimization_ok = test_geo_optimization_performance()
    
    print("\n" + "=" * 60)
    print("📋 測試總結:")
    print(f"🔍 跨軌道邊檢測: {'✅ 通過' if edge_detection_ok else '❌ 需優化'}")
    print(f"🎯 地理權重優化: {'✅ 通過' if geo_optimization_ok else '❌ 需優化'}")
    
    if edge_detection_ok and geo_optimization_ok:
        print("\n🎉 所有性能測試通過！算法優化成功！")
        print("💡 建議：現在可以進行完整的路由測試")
    else:
        print("\n⚠️  部分測試未通過，需要進一步優化")
        print("💡 建議：檢查緩存機制和算法邏輯")

if __name__ == "__main__":
    main()