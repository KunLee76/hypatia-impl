#!/usr/bin/env python3
"""
分析Virtual PID算法中的群組分配

目標：
1. 分析地面站和衛星在不同時間點的PID群組歸屬
2. 顯示625、626、627等地面站屬於哪個PID群組
3. 顯示每個PID群組的agent衛星和成員衛星
4. 分析群組邊界和分配邏輯
"""

import sys
import os
import math
import numpy as np
from collections import defaultdict
from datetime import datetime, timezone

# 添加satgen路徑
sys.path.append('/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')

from satgen.dynamic_state.algorithm_hierarchical_virtual_pid import VirtualPIDRouter

def read_ground_stations(gs_file):
    """讀取地面站坐標文件"""
    ground_stations = []
    with open(gs_file, 'r') as f:
        for line_idx, line in enumerate(f):
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

def read_satellites_tles(tles_file):
    """讀取衛星TLE文件"""
    satellites = []
    with open(tles_file, 'r') as f:
        lines = f.readlines()
    
    # 每三行為一組TLE數據
    for i in range(0, len(lines), 3):
        if i + 2 < len(lines):
            name_line = lines[i].strip()
            line1 = lines[i + 1].strip()
            line2 = lines[i + 2].strip()
            
            # 從name_line解析衛星ID
            try:
                # 格式通常是 "Starlink-1" 或類似
                sat_id = len(satellites)  # 簡單使用順序ID
                satellites.append({
                    'id': sat_id,
                    'name': name_line,
                    'line1': line1,
                    'line2': line2
                })
            except:
                continue
    
    return satellites

def get_satellite_position_simple(sat_id, t_ns, satellites):
    """
    簡化的衛星位置計算（用於演示）
    實際應用中會使用更精確的軌道力學計算
    """
    # 這裡使用簡化的模擬位置，在實際應用中需要TLE解算
    # 25x25 constellation, 25軌道，每軌道25顆衛星
    n_orbits = 25
    sats_per_orbit = 25
    
    if sat_id >= n_orbits * sats_per_orbit:
        return None, None
    
    orbit = sat_id // sats_per_orbit
    sat_in_orbit = sat_id % sats_per_orbit
    
    # 簡化軌道參數
    inclination = 53.0
    time_factor = (t_ns / 1e9) / 5400  # 大約90分鐘軌道週期
    
    # 計算地面軌跡
    raan = orbit * (360.0 / n_orbits)
    true_anomaly = (sat_in_orbit * (360.0 / sats_per_orbit) + time_factor * 360) % 360
    
    lon = (raan + true_anomaly) % 360
    if lon > 180:
        lon -= 360
        
    lat = inclination * math.sin(math.radians(true_anomaly))
    
    return lat, lon

def analyze_pid_groups_at_time(t_ns, ground_stations, satellites, grid_deg=10):
    """分析特定時間點的PID群組分配"""
    print(f"\n🕐 分析時間點: {t_ns//1000000}ms (t={t_ns}ns)")
    print("=" * 60)
    
    # 創建VirtualPIDRouter
    router = VirtualPIDRouter(grid_deg=grid_deg)
    
    # 設置衛星位置獲取函數
    def get_sat_latlon(sat_id, t):
        return get_satellite_position_simple(sat_id, t, satellites)
    
    router.get_sat_latlon = get_sat_latlon
    
    # 更新PID成員和代理
    sat_ids = [sat['id'] for sat in satellites[:625]]  # 前625顆衛星
    router.update_pid_members_and_agents(t_ns, sat_ids)
    
    print(f"📊 PID群組統計:")
    print(f"  總PID數量: {len(router.pids)}")
    print(f"  網格大小: {grid_deg}°×{grid_deg}°")
    
    # 統計有衛星的PID群組
    active_pids = []
    empty_pids = []
    
    for pid_idx in range(len(router.pids)):
        members = router.pid_members.get(pid_idx, set())
        agent = router.pid_agent_sat.get(pid_idx)
        
        if members:
            active_pids.append({
                'pid_idx': pid_idx,
                'pid_coord': router.pids[pid_idx],
                'members': members,
                'agent': agent,
                'member_count': len(members)
            })
        else:
            empty_pids.append(pid_idx)
    
    print(f"  有衛星的PID: {len(active_pids)}")
    print(f"  空PID: {len(empty_pids)}")
    
    if active_pids:
        member_counts = [pid_info['member_count'] for pid_info in active_pids]
        print(f"  每PID平均衛星數: {np.mean(member_counts):.2f}")
        print(f"  衛星數範圍: {min(member_counts)} - {max(member_counts)}")
    
    # 分析地面站的PID歸屬
    print(f"\n🏗️ 地面站PID分配:")
    gs_pid_assignments = {}
    
    for gs in ground_stations:
        pid_idx = router.latlon_to_pid(gs['lat'], gs['lon'])
        gs_pid_assignments[gs['id']] = {
            'gs_info': gs,
            'pid_idx': pid_idx,
            'pid_coord': router.pids[pid_idx] if pid_idx is not None else None
        }
    
    # 重點關注625, 626, 627
    target_gs_ids = [625, 626, 627]
    print(f"\n🎯 重點地面站分析:")
    
    for gs_id in target_gs_ids:
        if gs_id < len(ground_stations):
            gs_info = gs_pid_assignments[gs_id]
            gs = gs_info['gs_info']
            pid_idx = gs_info['pid_idx']
            pid_coord = gs_info['pid_coord']
            
            print(f"\n  地面站 {gs_id} ({gs['name']}):")
            print(f"    坐標: ({gs['lat']:.2f}°, {gs['lon']:.2f}°)")
            print(f"    PID群組: {pid_idx}")
            print(f"    PID坐標: {pid_coord}")
            
            if pid_idx is not None:
                # 找到這個PID的詳細信息
                pid_info = next((p for p in active_pids if p['pid_idx'] == pid_idx), None)
                if pid_info:
                    print(f"    PID成員衛星: {sorted(pid_info['members'])}")
                    print(f"    PID代理衛星: {pid_info['agent']}")
                    print(f"    PID衛星數量: {pid_info['member_count']}")
                else:
                    print(f"    ⚠️  該PID群組當前無衛星覆蓋")
    
    # 顯示PID網格結構
    print(f"\n📐 PID網格結構 ({grid_deg}°×{grid_deg}°):")
    lat_bins = len(set(coord[0] for coord in router.pids))
    lon_bins = len(set(coord[1] for coord in router.pids))
    print(f"  緯度分割: {lat_bins} 格 ({180//grid_deg} 預期)")
    print(f"  經度分割: {lon_bins} 格 ({360//grid_deg} 預期)")
    
    # 查找625, 626, 627是否在同一PID
    target_pids = []
    for gs_id in target_gs_ids:
        if gs_id < len(ground_stations):
            pid_idx = gs_pid_assignments[gs_id]['pid_idx']
            if pid_idx is not None:
                target_pids.append(pid_idx)
    
    if target_pids:
        unique_pids = set(target_pids)
        print(f"\n🔍 地面站625,626,627的PID歸屬:")
        print(f"  涉及的PID數量: {len(unique_pids)}")
        if len(unique_pids) == 1:
            print(f"  ✅ 都在同一PID群組: {list(unique_pids)[0]}")
        else:
            print(f"  📍 分布在不同PID群組: {sorted(unique_pids)}")
    
    return router, gs_pid_assignments, active_pids

def calculate_pid_boundaries(grid_deg=10):
    """計算PID邊界坐標"""
    print(f"\n📏 PID群組邊界計算 (網格: {grid_deg}°×{grid_deg}°)")
    print("=" * 50)
    
    lat_boundaries = list(range(-90, 91, grid_deg))
    lon_boundaries = list(range(-180, 181, grid_deg))
    
    print(f"緯度邊界: {lat_boundaries}")
    print(f"經度邊界: {lon_boundaries}")
    
    # 計算PID中心點
    print(f"\n📍 PID中心點:")
    pid_centers = []
    for i, lat_start in enumerate(lat_boundaries[:-1]):
        lat_end = lat_boundaries[i+1]
        lat_center = (lat_start + lat_end) / 2
        
        for j, lon_start in enumerate(lon_boundaries[:-1]):
            lon_end = lon_boundaries[j+1]
            lon_center = (lon_start + lon_end) / 2
            
            pid_idx = i * len(lon_boundaries[:-1]) + j
            pid_centers.append({
                'pid_idx': pid_idx,
                'grid_coord': (i, j),
                'lat_range': (lat_start, lat_end),
                'lon_range': (lon_start, lon_end),
                'center': (lat_center, lon_center)
            })
    
    print(f"總PID數量: {len(pid_centers)}")
    return pid_centers

def find_ground_station_pid(gs_lat, gs_lon, grid_deg=10):
    """手動計算地面站所屬的PID"""
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

def main():
    print("🌐 Virtual PID 群組分析工具")
    print("=" * 50)
    
    # 設置文件路徑
    data_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state"
    gs_file = f"{data_dir}/input_data/ground_stations_cities_sorted_by_estimated_2025_pop_top_100.basic.txt"
    
    try:
        # 讀取地面站
        print("📡 載入地面站數據...")
        ground_stations = read_ground_stations(gs_file)
        print(f"✅ 載入 {len(ground_stations)} 個地面站")
        
        # 模擬衛星數據
        print("🛰️ 生成衛星數據...")
        satellites = [{'id': i} for i in range(625)]
        print(f"✅ 生成 {len(satellites)} 顆衛星")
        
        # 分析不同網格大小
        grid_sizes = [10, 20]  # 10°×10° 和 20°×20°
        
        for grid_deg in grid_sizes:
            print(f"\n{'='*60}")
            print(f"🔍 分析網格大小: {grid_deg}°×{grid_deg}°")
            print(f"{'='*60}")
            
            # 計算PID邊界
            pid_centers = calculate_pid_boundaries(grid_deg)
            
            # 手動計算625, 626, 627的PID
            print(f"\n🎯 手動計算地面站625,626,627的PID:")
            target_gs_ids = [625, 626, 627]
            
            for gs_id in target_gs_ids:
                if gs_id < len(ground_stations):
                    gs = ground_stations[gs_id]
                    pid_info = find_ground_station_pid(gs['lat'], gs['lon'], grid_deg)
                    
                    print(f"\n  地面站 {gs_id} ({gs['name']}):")
                    print(f"    坐標: ({gs['lat']:.6f}°, {gs['lon']:.6f}°)")
                    if pid_info:
                        print(f"    PID群組: {pid_info['pid_idx']}")
                        print(f"    網格坐標: {pid_info['grid_coord']}")
                        print(f"    緯度範圍: {pid_info['lat_range']}")
                        print(f"    經度範圍: {pid_info['lon_range']}")
                    else:
                        print(f"    ⚠️  坐標超出範圍")
            
            # 使用實際的VirtualPIDRouter分析
            time_points = [0, 1000000000, 5000000000]  # 0s, 1s, 5s
            
            for t_ns in time_points:
                router, gs_assignments, active_pids = analyze_pid_groups_at_time(
                    t_ns, ground_stations, satellites, grid_deg
                )
        
        print(f"\n✅ 分析完成！")
        print(f"\n📋 主要發現:")
        print(f"  - 使用不同的網格大小會影響PID群組分配")
        print(f"  - 10°×10°網格提供更細粒度的分群")
        print(f"  - 20°×20°網格與hierarchical_region相似")
        print(f"  - 地面站的PID歸屬取決於其地理坐標和網格大小")
        
    except Exception as e:
        print(f"❌ 分析出錯: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()