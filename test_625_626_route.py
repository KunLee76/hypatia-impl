#!/usr/bin/env python3

"""
簡化的路由測試：專門測試625→626路由的優化效果
"""

import sys
import time
import networkx as nx

# 添加路徑
sys.path.append('/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')

try:
    from satgen.dynamic_state.algorithm_hierarchical_virtual_pid_clean_fixed import VirtualPIDRouter
    print("✅ 成功導入優化後的算法模塊")
except ImportError as e:
    print(f"❌ 導入算法模塊失敗: {e}")
    sys.exit(1)

def create_kuiper_like_topology():
    """創建類似Kuiper的Plus Grid拓撲 (25x25)"""
    satellites_per_orbit = 25
    num_orbits = 25
    total_satellites = satellites_per_orbit * num_orbits  # 625顆衛星
    
    G = nx.Graph()
    
    # 添加節點
    for i in range(total_satellites):
        G.add_node(i)
    
    print(f"🛰️  創建 {total_satellites} 顆衛星 ({num_orbits} 軌道 × {satellites_per_orbit} 衛星/軌道)")
    
    # 添加同軌道ISL (intra-orbit)
    intra_orbit_edges = 0
    for orbit in range(num_orbits):
        for pos in range(satellites_per_orbit):
            sat_id = orbit * satellites_per_orbit + pos
            next_sat = orbit * satellites_per_orbit + ((pos + 1) % satellites_per_orbit)
            G.add_edge(sat_id, next_sat, weight=1000000.0)
            intra_orbit_edges += 1
    
    # 添加跨軌道ISL (inter-orbit) - Plus Grid模式
    inter_orbit_edges = 0
    for orbit in range(num_orbits):
        next_orbit = (orbit + 1) % num_orbits
        for pos in range(satellites_per_orbit):
            # Plus Grid: 每顆衛星連接相鄰軌道的對應位置衛星
            sat_id = orbit * satellites_per_orbit + pos
            next_orbit_sat = next_orbit * satellites_per_orbit + pos
            
            # 49%的跨軌道ISL - 只在部分位置添加
            if pos % 2 == 0:  # 偶數位置添加跨軌道ISL
                G.add_edge(sat_id, next_orbit_sat, weight=1000000.0)
                inter_orbit_edges += 1
    
    print(f"🔗 同軌道ISL: {intra_orbit_edges} 條")
    print(f"🌐 跨軌道ISL: {inter_orbit_edges} 條")
    print(f"📊 跨軌道ISL比例: {inter_orbit_edges/(intra_orbit_edges+inter_orbit_edges)*100:.1f}%")
    
    return G

def create_ground_stations():
    """創建測試用的地面站"""
    # 625 (Chennai, India) 和 626 (Delhi, India) 的模擬位置
    ground_stations = {
        625: (13.0827, 80.2707),  # Chennai: 北緯13°, 東經80°
        626: (28.6139, 77.2090)   # Delhi: 北緯28°, 東經77°
    }
    return ground_stations

def mock_get_sat_latlon(satellite_id, t):
    """模擬衛星位置函數 - 基於Kuiper軌道參數"""
    import math
    
    # Kuiper軌道參數
    orbit_period = 5760  # 96分鐘軌道週期
    orbit_inclination = 53  # 軌道傾角
    satellites_per_orbit = 25
    
    # 計算軌道和位置
    orbit_id = satellite_id // satellites_per_orbit
    position_in_orbit = satellite_id % satellites_per_orbit
    
    # 軌道相位計算
    orbit_phase = (t / orbit_period + position_in_orbit / satellites_per_orbit) % 1.0
    
    # 緯度計算（考慮軌道傾角）
    lat = orbit_inclination * math.sin(2 * math.pi * orbit_phase)
    
    # 經度計算（考慮軌道分布）
    lon_offset = orbit_id * (360 / 25)  # 25個軌道均勻分布
    lon = (360 * orbit_phase + lon_offset) % 360 - 180
    
    return lat, lon

def find_shortest_path_with_algo(graph, router, src_gs, dst_gs, t):
    """使用Virtual PID算法找最短路徑"""
    try:
        # 獲取地面站位置
        src_lat, src_lon = src_gs
        dst_lat, dst_lon = dst_gs
        
        # 為目標地面站創建地理優化圖
        print(f"🎯 為目標 Delhi ({dst_lat:.4f}, {dst_lon:.4f}) 創建地理優化圖...")
        geo_optimized_graph = router.create_geo_optimized_graph(graph, dst_lat, dst_lon, t)
        
        # 找到最佳衛星代理
        print("🔍 尋找最佳衛星代理...")
        
        # 模擬選擇接入衛星的過程
        min_distance_to_src = float('inf')
        min_distance_to_dst = float('inf')
        best_src_sat = None
        best_dst_sat = None
        
        # 簡化選擇：選擇距離地面站最近的衛星
        for sat_id in range(625):
            sat_lat, sat_lon = router.get_sat_latlon(sat_id, t)
            
            # 計算到源地面站的距離
            src_dist = ((sat_lat - src_lat)**2 + (sat_lon - src_lon)**2)**0.5
            if src_dist < min_distance_to_src:
                min_distance_to_src = src_dist
                best_src_sat = sat_id
            
            # 計算到目標地面站的距離  
            dst_dist = ((sat_lat - dst_lat)**2 + (sat_lon - dst_lon)**2)**0.5
            if dst_dist < min_distance_to_dst:
                min_distance_to_dst = dst_dist
                best_dst_sat = sat_id
        
        print(f"📡 源接入衛星: {best_src_sat} (距離 Chennai: {min_distance_to_src:.4f})")
        print(f"📡 目標接入衛星: {best_dst_sat} (距離 Delhi: {min_distance_to_dst:.4f})")
        
        # 在地理優化圖上計算最短路徑
        if best_src_sat is not None and best_dst_sat is not None:
            try:
                path = nx.shortest_path(geo_optimized_graph, best_src_sat, best_dst_sat, weight='weight')
                path_length = nx.shortest_path_length(geo_optimized_graph, best_src_sat, best_dst_sat, weight='weight')
                return path, path_length
            except nx.NetworkXNoPath:
                print("❌ 無法找到路徑")
                return None, None
        else:
            print("❌ 無法找到合適的接入衛星")
            return None, None
            
    except Exception as e:
        print(f"❌ 路徑計算出錯: {e}")
        return None, None

def analyze_route_efficiency(path, router, t):
    """分析路由效率"""
    if not path or len(path) < 2:
        return
    
    print("\n📈 路由分析:")
    print(f"🛤️  路由路徑: {' → '.join(map(str, path))}")
    print(f"📏 跳數: {len(path)-1}")
    
    # 分析地理移動方向
    print("\n🌍 地理移動分析:")
    for i in range(len(path)-1):
        src_sat = path[i]
        dst_sat = path[i+1]
        
        src_lat, src_lon = router.get_sat_latlon(src_sat, t)
        dst_lat, dst_lon = router.get_sat_latlon(dst_sat, t)
        
        # 計算移動方向
        lat_move = dst_lat - src_lat
        lon_move = dst_lon - src_lon
        
        direction = ""
        if abs(lat_move) > abs(lon_move):
            direction = "北" if lat_move > 0 else "南"
        else:
            direction = "東" if lon_move > 0 else "西"
        
        # 判斷是否為跨軌道ISL
        is_cross_orbit = router._is_cross_orbit_isl(src_sat, dst_sat)
        link_type = "跨軌道" if is_cross_orbit else "同軌道"
        
        print(f"  {src_sat} → {dst_sat}: {direction}向移動 ({link_type}ISL)")

def main():
    """主測試函數"""
    print("🚀 測試625→626路由優化效果...")
    print("=" * 60)
    
    # 創建網絡拓撲
    print("🔧 創建Kuiper Plus Grid拓撲...")
    satellite_graph = create_kuiper_like_topology()
    
    # 創建路由器
    router = VirtualPIDRouter(grid_deg=15, allow_diagonal_neighbor=False)
    router.get_sat_latlon = mock_get_sat_latlon
    router.get_sat_neighbors = lambda sid, _t: list(satellite_graph.neighbors(sid))
    
    # 地面站
    ground_stations = create_ground_stations()
    chennai_pos = ground_stations[625]  # Chennai
    delhi_pos = ground_stations[626]    # Delhi
    
    print("\n📍 地面站位置:")
    print(f"  625 (Chennai): {chennai_pos}")
    print(f"  626 (Delhi): {delhi_pos}")
    
    # 測試時間
    simulation_time = 100.0
    
    print(f"\n🎯 測試625→626路由 (模擬時間: {simulation_time}s)...")
    
    # 使用優化算法找路由
    start_time = time.time()
    path, path_length = find_shortest_path_with_algo(
        satellite_graph, router, chennai_pos, delhi_pos, simulation_time
    )
    end_time = time.time()
    
    if path:
        print("\n✅ 成功找到路由!")
        print(f"⏱️  計算耗時: {end_time - start_time:.4f} 秒")
        print(f"📊 路徑權重: {path_length:.0f}")
        
        # 分析路由效率
        analyze_route_efficiency(path, router, simulation_time)
        
        # 檢查是否有早期退出
        print("\n🎯 早期退出分析:")
        if len(path) <= 6:  # 6跳以內認為效率較好
            print("✅ 路由跳數合理，地理優化效果良好")
        else:
            print("⚠️  路由跳數較多，可能需要進一步優化")
            
        # 檢查是否朝著正確方向移動
        if path and len(path) >= 3:
            mid_sat = path[len(path)//2]
            mid_lat, mid_lon = router.get_sat_latlon(mid_sat, simulation_time)
            
            # 檢查中間點是否更接近目標
            chennai_to_mid = ((mid_lat - chennai_pos[0])**2 + (mid_lon - chennai_pos[1])**2)**0.5
            chennai_to_delhi = ((delhi_pos[0] - chennai_pos[0])**2 + (delhi_pos[1] - chennai_pos[1])**2)**0.5
            
            if chennai_to_mid < chennai_to_delhi:
                print("✅ 路由朝著正確的地理方向移動")
            else:
                print("⚠️  路由可能存在地理繞行")
    else:
        print("❌ 未能找到有效路由")
    
    print("\n" + "=" * 60)
    print("📋 測試完成")

if __name__ == "__main__":
    main()