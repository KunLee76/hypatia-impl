#!/usr/bin/env python3
"""
快速分析Virtual PID算法中625、626、627地面站的群組分配
"""

def find_ground_station_pid(gs_lat, gs_lon, grid_deg=10):
    """計算地面站所屬的PID"""
    lat_min, lat_max = -90, 90
    lon_min, lon_max = -180, 180
    
    # 確保坐標在範圍內
    if not (lat_min <= gs_lat < lat_max and lon_min <= gs_lon < lon_max):
        return None
    
    gi = int((gs_lat - lat_min) // grid_deg)
    gj = int((gs_lon - lon_min) // grid_deg)
    
    # 計算PID索引
    num_lon_cells = int(360 // grid_deg)
    pid_idx = gi * num_lon_cells + gj
    
    return {
        'pid_idx': pid_idx,
        'grid_coord': (gi, gj),
        'lat_range': (lat_min + gi * grid_deg, lat_min + (gi + 1) * grid_deg),
        'lon_range': (lon_min + gj * grid_deg, lon_min + (gj + 1) * grid_deg)
    }

def read_ground_stations(gs_file):
    """讀取地面站坐標文件"""
    ground_stations = []
    with open(gs_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                parts = line.strip().split(',')
                if len(parts) >= 4:
                    gs_id = int(parts[0])
                    gs_name = parts[1]
                    gs_lat = float(parts[2])
                    gs_lon = float(parts[3])
                    ground_stations.append({
                        'id': gs_id,
                        'name': gs_name,
                        'lat': gs_lat,
                        'lon': gs_lon
                    })
    return ground_stations

def main():
    print("🌐 Virtual PID 地面站群組快速分析")
    print("=" * 50)
    
    # 讀取地面站文件
    gs_file = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/input_data/ground_stations_cities_sorted_by_estimated_2025_pop_top_100.basic.txt"
    ground_stations = read_ground_stations(gs_file)
    
    print(f"📡 載入 {len(ground_stations)} 個地面站")
    print(f"地面站ID範圍: {ground_stations[0]['id']} - {ground_stations[-1]['id']}")
    
    # 說明ID映射
    num_satellites = 625
    print(f"\n🔢 ID映射說明:")
    print(f"  衛星數量: {num_satellites} (ID: 0-624)")
    print(f"  地面站ID在路由系統中: {num_satellites} + 地面站索引")
    print(f"  例如：地面站0 在路由中是ID {num_satellites + 0}")
    print(f"       地面站99 在路由中是ID {num_satellites + 99}")
    
    # 計算625, 626, 627對應的實際地面站
    target_routing_ids = [625, 626, 627]
    print(f"\n🎯 分析路由系統中的地面站 {target_routing_ids}:")
    
    for routing_id in target_routing_ids:
        gs_index = routing_id - num_satellites
        if 0 <= gs_index < len(ground_stations):
            gs = ground_stations[gs_index]
            print(f"\n路由ID {routing_id} = 地面站索引 {gs_index}:")
            print(f"  名稱: {gs['name']}")
            print(f"  坐標: ({gs['lat']:.6f}°, {gs['lon']:.6f}°)")
            
            # 分析不同網格大小下的PID分配
            for grid_deg in [10, 20]:
                pid_info = find_ground_station_pid(gs['lat'], gs['lon'], grid_deg)
                if pid_info:
                    print(f"  {grid_deg}°×{grid_deg}° 網格:")
                    print(f"    PID群組: {pid_info['pid_idx']}")
                    print(f"    網格坐標: {pid_info['grid_coord']}")
                    print(f"    緯度範圍: {pid_info['lat_range']}")
                    print(f"    經度範圍: {pid_info['lon_range']}")
        else:
            print(f"\n路由ID {routing_id}: 無效 (超出地面站範圍)")
    
    # 比較625, 626, 627是否在同一PID
    for grid_deg in [10, 20]:
        print(f"\n🔍 {grid_deg}°×{grid_deg}° 網格下的群組歸屬:")
        pids = []
        for routing_id in target_routing_ids:
            gs_index = routing_id - num_satellites
            if 0 <= gs_index < len(ground_stations):
                gs = ground_stations[gs_index]
                pid_info = find_ground_station_pid(gs['lat'], gs['lon'], grid_deg)
                if pid_info:
                    pids.append(pid_info['pid_idx'])
                    print(f"  GS{routing_id}: PID {pid_info['pid_idx']}")
        
        if pids:
            unique_pids = set(pids)
            if len(unique_pids) == 1:
                print(f"  ✅ 所有地面站都在同一PID群組: {list(unique_pids)[0]}")
            else:
                print(f"  📍 地面站分布在 {len(unique_pids)} 個不同PID群組: {sorted(unique_pids)}")
    
    print(f"\n✅ 分析完成！")

if __name__ == "__main__":
    main()