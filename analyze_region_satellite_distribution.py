#!/usr/bin/env python3
"""
分析地理網格中衛星分布的詳細統計

目標：
1. 統計550個區域中每個區域的衛星數量
2. 分析最小、最大、平均衛星覆蓋數
3. 分析衛星分布的均勻性
4. 識別空區域和衛星密集區域
"""

import sys
import os
import math
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

def add_satgen_path():
    """添加satgen路徑"""
    satgen_path = '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy'
    if satgen_path not in sys.path:
        sys.path.append(satgen_path)

def generate_satellite_positions(num_satellites=625):
    """
    生成衛星位置 (模擬25x25 Starlink constellation)
    基於TLE數據的近似位置
    """
    satellites = []
    
    # 25軌道，每軌道25顆衛星
    n_orbits = 25
    sats_per_orbit = 25
    
    # Starlink constellation 參數 (近似)
    inclination = 53.0  # 軌道傾角 (度)
    altitude = 550      # 軌道高度 (km)
    
    for orbit in range(n_orbits):
        # RAAN (升交點赤經) 在0-360度均勻分布
        raan = orbit * (360.0 / n_orbits)
        
        for sat in range(sats_per_orbit):
            # 真近點角在0-360度均勻分布
            true_anomaly = sat * (360.0 / sats_per_orbit)
            
            # 簡化的地面軌跡計算 (忽略橢圓軌道和攝動)
            # 在實際應用中需要更精確的軌道力學計算
            
            # 計算地面軌跡 (sub-satellite point)
            # 這裡使用簡化公式
            lon = (raan + true_anomaly) % 360
            if lon > 180:
                lon -= 360
                
            # 緯度受軌道傾角限制
            lat = inclination * math.sin(math.radians(true_anomaly))
            
            satellites.append({
                'id': orbit * sats_per_orbit + sat,
                'orbit': orbit,
                'sat_in_orbit': sat,
                'lat': lat,
                'lon': lon,
                'raan': raan,
                'true_anomaly': true_anomaly
            })
    
    return satellites

def get_region_id(lat, lon, lat_step=20.0, lon_step=20.0):
    """計算地理區域ID (同algorithm_hierarchical_region中的邏輯)"""
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

def analyze_satellite_distribution(lat_step=20.0, lon_step=20.0):
    """分析衛星在地理網格中的分布"""
    print("🛰️ 分析衛星地理分布")
    print("=" * 50)
    
    # 生成衛星位置
    satellites = generate_satellite_positions()
    print(f"總衛星數量: {len(satellites)}")
    
    # 分配衛星到區域
    region_to_sats = defaultdict(list)
    sat_to_region = {}
    
    for sat in satellites:
        region_id = get_region_id(sat['lat'], sat['lon'], lat_step, lon_step)
        region_to_sats[region_id].append(sat)
        sat_to_region[sat['id']] = region_id
    
    # 統計分析
    print(f"\n📊 區域統計 (網格大小: {lat_step}°×{lon_step}°)")
    print(f"總區域數量: {len(region_to_sats)}")
    
    # 每個區域的衛星數量
    satellites_per_region = [len(sats) for sats in region_to_sats.values()]
    
    if satellites_per_region:
        min_sats = min(satellites_per_region)
        max_sats = max(satellites_per_region)
        avg_sats = np.mean(satellites_per_region)
        median_sats = np.median(satellites_per_region)
        std_sats = np.std(satellites_per_region)
        
        print(f"\n🔢 衛星分布統計:")
        print(f"  最少衛星數: {min_sats}")
        print(f"  最多衛星數: {max_sats}")
        print(f"  平均衛星數: {avg_sats:.2f}")
        print(f"  中位數: {median_sats:.2f}")
        print(f"  標準差: {std_sats:.2f}")
        
        # 分布直方圖統計
        print(f"\n📈 衛星數量分布:")
        sat_count_distribution = defaultdict(int)
        for count in satellites_per_region:
            sat_count_distribution[count] += 1
        
        for sat_count in sorted(sat_count_distribution.keys()):
            region_count = sat_count_distribution[sat_count]
            percentage = (region_count / len(region_to_sats)) * 100
            print(f"  {sat_count}顆衛星: {region_count}個區域 ({percentage:.1f}%)")
        
        # 空區域檢查
        total_possible_regions = int((180/lat_step) * (360/lon_step))
        empty_regions = total_possible_regions - len(region_to_sats)
        print(f"\n🕳️ 空區域統計:")
        print(f"  理論總區域數: {total_possible_regions}")
        print(f"  有衛星覆蓋的區域: {len(region_to_sats)}")
        print(f"  無衛星覆蓋的區域: {empty_regions}")
        print(f"  覆蓋率: {(len(region_to_sats)/total_possible_regions)*100:.1f}%")
        
        # 找出特殊區域
        print(f"\n🎯 特殊區域:")
        
        # 衛星最少的區域
        min_regions = [rid for rid, sats in region_to_sats.items() if len(sats) == min_sats]
        print(f"  衛星最少區域 ({min_sats}顆): {len(min_regions)}個區域")
        if len(min_regions) <= 5:
            for rid in min_regions:
                lat_idx = rid // int(360/lon_step)
                lon_idx = rid % int(360/lon_step)
                lat_center = lat_idx * lat_step - 90 + lat_step/2
                lon_center = lon_idx * lon_step - 180 + lon_step/2
                print(f"    區域{rid}: 中心({lat_center:.1f}°, {lon_center:.1f}°)")
        
        # 衛星最多的區域
        max_regions = [rid for rid, sats in region_to_sats.items() if len(sats) == max_sats]
        print(f"  衛星最多區域 ({max_sats}顆): {len(max_regions)}個區域")
        if len(max_regions) <= 5:
            for rid in max_regions:
                lat_idx = rid // int(360/lon_step)
                lon_idx = rid % int(360/lon_step)
                lat_center = lat_idx * lat_step - 90 + lat_step/2
                lon_center = lon_idx * lon_step - 180 + lon_step/2
                print(f"    區域{rid}: 中心({lat_center:.1f}°, {lon_center:.1f}°)")
    
    return region_to_sats, sat_to_region, satellites

def generate_distribution_plot(region_to_sats, lat_step=20.0, lon_step=20.0):
    """生成衛星分布視覺化圖表"""
    print(f"\n📊 生成分布圖表...")
    
    try:
        satellites_per_region = [len(sats) for sats in region_to_sats.values()]
        
        # 直方圖
        plt.figure(figsize=(12, 8))
        
        # 衛星數量分布直方圖
        plt.subplot(2, 2, 1)
        plt.hist(satellites_per_region, bins=range(min(satellites_per_region), max(satellites_per_region)+2), 
                 alpha=0.7, edgecolor='black')
        plt.xlabel('每個區域的衛星數量')
        plt.ylabel('區域數量')
        plt.title(f'衛星分布直方圖 (網格: {lat_step}°×{lon_step}°)')
        plt.grid(True, alpha=0.3)
        
        # 統計數據
        plt.subplot(2, 2, 2)
        stats = [
            f"總區域數: {len(region_to_sats)}",
            f"最少衛星: {min(satellites_per_region)}",
            f"最多衛星: {max(satellites_per_region)}",
            f"平均衛星: {np.mean(satellites_per_region):.2f}",
            f"標準差: {np.std(satellites_per_region):.2f}"
        ]
        plt.text(0.1, 0.9, '\n'.join(stats), transform=plt.gca().transAxes, 
                 fontsize=12, verticalalignment='top',
                 bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
        plt.axis('off')
        plt.title('統計摘要')
        
        # 累積分布
        plt.subplot(2, 2, 3)
        sorted_counts = sorted(satellites_per_region)
        cumulative = np.arange(1, len(sorted_counts)+1) / len(sorted_counts) * 100
        plt.plot(sorted_counts, cumulative, 'b-', linewidth=2)
        plt.xlabel('每個區域的衛星數量')
        plt.ylabel('累積百分比 (%)')
        plt.title('累積分布函數')
        plt.grid(True, alpha=0.3)
        
        # 箱形圖
        plt.subplot(2, 2, 4)
        plt.boxplot(satellites_per_region, vert=True)
        plt.ylabel('每個區域的衛星數量')
        plt.title('箱形圖')
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 保存圖表
        output_file = f'satellite_distribution_{lat_step}x{lon_step}.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"圖表已保存: {output_file}")
        
        plt.show()
        
    except Exception as e:
        print(f"⚠️ 生成圖表時出錯: {e}")

def compare_different_grid_sizes():
    """比較不同網格大小的衛星分布"""
    print(f"\n🔍 比較不同網格大小的衛星分布")
    print("=" * 50)
    
    grid_sizes = [
        (5.0, 5.0),   # 細網格
        (10.0, 10.0), # 中等網格
        (20.0, 20.0), # 粗網格 (當前使用)
        (30.0, 30.0)  # 更粗網格
    ]
    
    for lat_step, lon_step in grid_sizes:
        print(f"\n--- 網格大小: {lat_step}°×{lon_step}° ---")
        
        # 重新計算分布
        satellites = generate_satellite_positions()
        region_to_sats = defaultdict(list)
        
        for sat in satellites:
            region_id = get_region_id(sat['lat'], sat['lon'], lat_step, lon_step)
            region_to_sats[region_id].append(sat)
        
        if region_to_sats:
            satellites_per_region = [len(sats) for sats in region_to_sats.values()]
            min_sats = min(satellites_per_region)
            max_sats = max(satellites_per_region)
            avg_sats = np.mean(satellites_per_region)
            std_sats = np.std(satellites_per_region)
            
            total_regions = int((180/lat_step) * (360/lon_step))
            coverage = (len(region_to_sats) / total_regions) * 100
            
            print(f"  區域數: {len(region_to_sats)}/{total_regions} (覆蓋率: {coverage:.1f}%)")
            print(f"  衛星數: 最少={min_sats}, 最多={max_sats}, 平均={avg_sats:.2f}, 標準差={std_sats:.2f}")

if __name__ == "__main__":
    print("🌍 衛星地理分布分析工具")
    print("=" * 50)
    
    try:
        # 主要分析 (20°×20° 網格)
        region_to_sats, sat_to_region, satellites = analyze_satellite_distribution(20.0, 20.0)
        
        # 生成圖表
        generate_distribution_plot(region_to_sats, 20.0, 20.0)
        
        # 比較不同網格大小
        compare_different_grid_sizes()
        
        print(f"\n✅ 分析完成！")
        print(f"主要發現:")
        print(f"  - 使用20°×20°網格時，約有{len(region_to_sats)}個區域有衛星覆蓋")
        print(f"  - 每個區域平均覆蓋{np.mean([len(sats) for sats in region_to_sats.values()]):.2f}顆衛星")
        print(f"  - 衛星分布的不均勻性可能影響路由效率")
        
    except Exception as e:
        print(f"❌ 分析出錯: {e}")
        import traceback
        traceback.print_exc()
