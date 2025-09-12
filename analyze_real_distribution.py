#!/usr/bin/env python3
"""
正確讀取實際的TLE和地面站數據，分析衛星分布統計
"""

import sys
import os
import math
from collections import defaultdict
import ephem
from datetime import datetime

def get_region_id(lat, lon, lat_step=20.0, lon_step=20.0):
    """計算地理區域ID (與algorithm_hierarchical_region中的邏輯完全一致)"""
    # Clamp values within expected ranges
    if lat < -90.0:
        lat = -90.0
    elif lat > 90.0:
        lat = 90.0
    # Normalize longitude to [-180, 180]
    lon = ((lon + 180) % 360) - 180

    lat_index = int((lat + 90.0) // lat_step)
    lon_index = int((lon + 180.0) // lon_step)
    num_lon_cells = int(360.0 // lon_step)
    return lat_index * num_lon_cells + lon_index

def get_region_center(region_id, lat_step=20.0, lon_step=20.0):
    """計算區域中心座標"""
    num_lon_cells = int(360.0 // lon_step)
    lat_index = region_id // num_lon_cells
    lon_index = region_id % num_lon_cells
    
    lat_center = lat_index * lat_step - 90 + lat_step/2
    lon_center = lon_index * lon_step - 180 + lon_step/2
    
    return lat_center, lon_center

def parse_tle_simple(line1, line2):
    """簡化的TLE解析，獲取基本軌道參數"""
    try:
        # 解析軌道傾角 (inclination)
        inclination = float(line2[8:16])
        
        # 解析升交點赤經 (RAAN)
        raan = float(line2[17:25])
        
        # 解析偏心率 (eccentricity)
        eccentricity_str = "0." + line2[26:33]
        eccentricity = float(eccentricity_str)
        
        # 解析近地點幅角 (argument of perigee)
        arg_perigee = float(line2[34:42])
        
        # 解析平近點角 (mean anomaly)
        mean_anomaly = float(line2[43:51])
        
        # 解析平均運動 (mean motion)
        mean_motion = float(line2[52:63])
        
        return {
            'inclination': inclination,
            'raan': raan,
            'eccentricity': eccentricity,
            'arg_perigee': arg_perigee,
            'mean_anomaly': mean_anomaly,
            'mean_motion': mean_motion
        }
    except:
        return None

def simple_orbit_position(orbital_elements, time_offset_minutes=0):
    """簡化的軌道位置計算"""
    try:
        inclination = math.radians(orbital_elements['inclination'])
        raan = math.radians(orbital_elements['raan'])
        mean_anomaly = math.radians(orbital_elements['mean_anomaly'])
        
        # 加上時間偏移 (簡化，忽略詳細的軌道力學)
        mean_anomaly += time_offset_minutes * (2 * math.pi / (24 * 60)) * orbital_elements['mean_motion']
        
        # 簡化：假設圓軌道，真近點角 ≈ 平近點角
        true_anomaly = mean_anomaly
        
        # 計算地面軌跡 (sub-satellite point)
        # 簡化的球面三角學
        lat = math.asin(math.sin(inclination) * math.sin(true_anomaly))
        
        # 經度 = RAAN + 地球自轉修正
        earth_rotation = time_offset_minutes * (360.0 / (24 * 60))  # 地球自轉
        lon = math.degrees(raan + true_anomaly) - earth_rotation
        
        # 正規化經度到 [-180, 180]
        lon = ((lon + 180) % 360) - 180
        
        return math.degrees(lat), lon
    except:
        return None, None

def analyze_real_satellite_distribution():
    """分析真實的衛星分布"""
    print("🛰️ 分析真實衛星分布統計")
    print("=" * 50)
    
    # 檔案路徑 (使用fast版本的數據)
    tles_file = '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_region_fast/tles.txt'
    ground_stations_file = '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_region_fast/ground_stations.txt'
    
    # 1. 讀取TLE數據
    satellites = []
    if os.path.exists(tles_file):
        with open(tles_file, 'r') as f:
            lines = f.readlines()
        
        # 跳過第一行 (25 25)
        i = 1
        sat_id = 0
        
        while i < len(lines):
            if i + 2 < len(lines):
                # 衛星名稱行
                sat_name = lines[i].strip()
                # TLE第一行
                tle_line1 = lines[i+1].strip()
                # TLE第二行
                tle_line2 = lines[i+2].strip()
                
                # 解析TLE
                orbital_elements = parse_tle_simple(tle_line1, tle_line2)
                if orbital_elements:
                    # 計算當前位置 (t=0時刻)
                    lat, lon = simple_orbit_position(orbital_elements, 0)
                    if lat is not None and lon is not None:
                        satellites.append({
                            'id': sat_id,
                            'name': sat_name,
                            'lat': lat,
                            'lon': lon,
                            'orbital_elements': orbital_elements
                        })
                
                sat_id += 1
                i += 3  # 下一顆衛星
            else:
                break
    
    print(f"成功讀取 {len(satellites)} 顆衛星")
    
    # 2. 讀取地面站數據
    ground_stations = []
    if os.path.exists(ground_stations_file):
        with open(ground_stations_file, 'r') as f:
            for line in f:
                if line.strip():
                    parts = line.strip().split(',')
                    if len(parts) >= 4:
                        try:
                            gs_id = int(parts[0])
                            name = parts[1]
                            lat = float(parts[2])
                            lon = float(parts[3])
                            ground_stations.append({
                                'id': gs_id,
                                'name': name,
                                'lat': lat,
                                'lon': lon
                            })
                        except:
                            pass
    
    print(f"成功讀取 {len(ground_stations)} 個地面站")
    
    # 3. 分析不同網格大小的衛星分布
    grid_sizes = [(20.0, 20.0), (10.0, 10.0), (5.0, 5.0)]
    
    for lat_step, lon_step in grid_sizes:
        print(f"\n📊 網格大小: {lat_step}°×{lon_step}°")
        print("-" * 50)
        
        # 分配衛星到區域
        region_to_sats = defaultdict(list)
        for sat in satellites:
            region_id = get_region_id(sat['lat'], sat['lon'], lat_step, lon_step)
            region_to_sats[region_id].append(sat)
        
        # 統計分析
        if region_to_sats:
            satellites_per_region = [len(sats) for sats in region_to_sats.values()]
            min_sats = min(satellites_per_region)
            max_sats = max(satellites_per_region)
            avg_sats = sum(satellites_per_region) / len(satellites_per_region)
            std_sats = (sum((x - avg_sats)**2 for x in satellites_per_region) / len(satellites_per_region))**0.5
            
            # 計算總區域數
            total_regions = int((180/lat_step) * (360/lon_step))
            coverage = (len(region_to_sats) / total_regions) * 100
            
            print(f"🔢 基本統計:")
            print(f"  有衛星覆蓋的區域: {len(region_to_sats)}/{total_regions} (覆蓋率: {coverage:.1f}%)")
            print(f"  每區域衛星數: 最少={min_sats}, 最多={max_sats}, 平均={avg_sats:.2f}, 標準差={std_sats:.2f}")
            
            # 詳細分布
            sat_count_dist = defaultdict(int)
            for count in satellites_per_region:
                sat_count_dist[count] += 1
            
            print(f"\n📈 衛星數量分布:")
            for sat_count in sorted(sat_count_dist.keys()):
                region_count = sat_count_dist[sat_count]
                percentage = (region_count / len(region_to_sats)) * 100
                print(f"  {sat_count}顆衛星: {region_count}個區域 ({percentage:.1f}%)")
            
            # 特殊區域分析 (只針對20°×20°網格)
            if lat_step == 20.0 and lon_step == 20.0:
                print(f"\n🎯 特殊區域分析:")
                
                # 衛星最少的區域
                min_regions = [rid for rid, sats in region_to_sats.items() if len(sats) == min_sats]
                print(f"  衛星最少區域 ({min_sats}顆): {len(min_regions)}個")
                for rid in min_regions[:3]:  # 只顯示前3個
                    lat_c, lon_c = get_region_center(rid, lat_step, lon_step)
                    print(f"    區域{rid}: 中心({lat_c:.1f}°, {lon_c:.1f}°)")
                    for sat in region_to_sats[rid][:2]:  # 只顯示前2顆衛星
                        print(f"      {sat['name']}: ({sat['lat']:.1f}°, {sat['lon']:.1f}°)")
                
                # 衛星最多的區域
                max_regions = [rid for rid, sats in region_to_sats.items() if len(sats) == max_sats]
                print(f"  衛星最多區域 ({max_sats}顆): {len(max_regions)}個")
                for rid in max_regions[:3]:
                    lat_c, lon_c = get_region_center(rid, lat_step, lon_step)
                    print(f"    區域{rid}: 中心({lat_c:.1f}°, {lon_c:.1f}°)")
                    for sat in region_to_sats[rid][:2]:
                        print(f"      {sat['name']}: ({sat['lat']:.1f}°, {sat['lon']:.1f}°)")
    
    # 4. 地面站分布分析
    print(f"\n🏠 地面站地理分布 (20°×20°網格)")
    print("-" * 50)
    
    region_to_gs = defaultdict(list)
    for gs in ground_stations:
        region_id = get_region_id(gs['lat'], gs['lon'], 20.0, 20.0)
        region_to_gs[region_id].append(gs)
    
    print(f"地面站覆蓋區域數: {len(region_to_gs)}")
    
    if region_to_gs:
        gs_per_region = [len(gss) for gss in region_to_gs.values()]
        print(f"每區域地面站數: 最少={min(gs_per_region)}, 最多={max(gs_per_region)}, 平均={sum(gs_per_region)/len(gs_per_region):.2f}")
        
        # 地面站分布
        gs_count_dist = defaultdict(int)
        for count in gs_per_region:
            gs_count_dist[count] += 1
        
        print("地面站數量分布:")
        for gs_count in sorted(gs_count_dist.keys()):
            region_count = gs_count_dist[gs_count]
            percentage = (region_count / len(region_to_gs)) * 100
            print(f"  {gs_count}個地面站: {region_count}個區域 ({percentage:.1f}%)")
        
        # 找出地面站密集區域
        max_gs_count = max(gs_per_region)
        dense_regions = [rid for rid, gss in region_to_gs.items() if len(gss) == max_gs_count]
        
        print(f"\n地面站最密集區域 ({max_gs_count}個地面站):")
        for rid in dense_regions[:3]:
            lat_c, lon_c = get_region_center(rid, 20.0, 20.0)
            print(f"  區域{rid}: 中心({lat_c:.1f}°, {lon_c:.1f}°)")
            for gs in region_to_gs[rid]:
                city_info = gs['name'].replace('City: ', '').replace('; Country:', ',')
                print(f"    GS{gs['id']}: {city_info} ({gs['lat']:.1f}°, {gs['lon']:.1f}°)")
    
    return region_to_sats, region_to_gs, satellites, ground_stations

if __name__ == "__main__":
    region_to_sats, region_to_gs, satellites, ground_stations = analyze_real_satellite_distribution()
    
    print(f"\n✅ 真實衛星分布分析完成!")
    print(f"\n📋 總結 (使用20°×20°網格):")
    
    if region_to_sats:
        satellites_per_region = [len(sats) for sats in region_to_sats.values()]
        print(f"  - 衛星總數: {len(satellites)}")
        print(f"  - 有衛星覆蓋的區域: {len(region_to_sats)}")
        print(f"  - 每個區域平均衛星數: {sum(satellites_per_region)/len(satellites_per_region):.2f}")
        print(f"  - 每個區域衛星數範圍: {min(satellites_per_region)} - {max(satellites_per_region)}")
    
    if region_to_gs:
        print(f"  - 地面站總數: {len(ground_stations)}")
        print(f"  - 有地面站的區域: {len(region_to_gs)}")
    
    print(f"\n這些數據將幫助你理解分層路由算法中的地理分群效果！")
