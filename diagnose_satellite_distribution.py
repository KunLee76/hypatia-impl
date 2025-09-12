#!/usr/bin/env python3
"""
診斷衛星位置分布和分群失效問題
"""

import sys
import os
sys.path.append("satgenpy")
import ephem
from datetime import datetime, timezone


def diagnose_satellite_distribution():
    """
    診斷衛星位置分布問題
    """
    
    print("🔬 衛星位置分布診斷")
    print("=" * 50)
    
    # 讀取TLE文件
    tles_file = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_region_fast/tles.txt"
    
    if not os.path.exists(tles_file):
        print(f"❌ 找不到TLE文件: {tles_file}")
        return
    
    # 計算多個時間點的衛星位置
    time_points = [50, 1000, 5000, 10000, 30000]  # ms
    
    for time_ms in time_points:
        print(f"\n⏰ 時間點: {time_ms}ms")
        print("-" * 30)
        
        # 轉換時間
        time_ns = time_ms * 1000000
        epoch_time = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        sim_time = epoch_time.timestamp() + time_ns / 1e9
        date = datetime.fromtimestamp(sim_time, tz=timezone.utc)
        
        positions = []
        
        with open(tles_file, 'r') as f:
            lines = f.readlines()
        
        # 跳過第一行（25 25 配置信息），從第二行開始解析
        line_start = 1
        
        # 計算前10個衛星的位置作為樣本
        for i in range(line_start, min(31, len(lines)), 3):
            if i + 2 < len(lines):
                try:
                    sat = ephem.readtle(lines[i].strip(), lines[i+1].strip(), lines[i+2].strip())
                    sat.compute(date)
                    
                    lat = float(sat.sublat) * 180.0 / 3.14159
                    lon = float(sat.sublong) * 180.0 / 3.14159
                    
                    positions.append((lat, lon))
                    
                    if len(positions) <= 10:
                        print(f"   SAT-{len(positions)-1:2d}: ({lat:6.2f}°, {lon:7.2f}°)")
                        
                except Exception as e:
                    print(f"   SAT-{(i-line_start)//3}: TLE解析錯誤 - {e}")
        
        # 統計位置分布
        if positions:
            lats = [pos[0] for pos in positions]
            lons = [pos[1] for pos in positions]
            
            lat_range = max(lats) - min(lats)
            lon_range = max(lons) - min(lons)
            
            print(f"   📊 緯度範圍: {min(lats):.2f}° 到 {max(lats):.2f}° (跨度: {lat_range:.2f}°)")
            print(f"   📊 經度範圍: {min(lons):.2f}° 到 {max(lons):.2f}° (跨度: {lon_range:.2f}°)")
            
            # 分析分群效果
            grid_sizes = [10.0, 5.0, 1.0, 0.5]
            for grid_size in grid_sizes:
                groups = set()
                for lat, lon in positions:
                    lat_index = int((lat + 90.0) // grid_size)
                    lon_index = int((lon + 180.0) // grid_size)
                    num_lon_cells = int(360.0 // grid_size)
                    region_id = lat_index * num_lon_cells + lon_index
                    groups.add(region_id)
                
                print(f"   🌍 {grid_size}°網格: {len(groups)} 個群組")


if __name__ == "__main__":
    diagnose_satellite_distribution()
