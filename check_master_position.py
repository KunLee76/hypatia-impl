#!/usr/bin/env python3
"""
驗證master節點位置是否在網格幾何中心
分析當前的master選擇邏輯並提出改進方案
"""

import math
import sys
import os

# 添加路徑以便導入模塊
sys.path.insert(0, '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')

def check_master_node_positioning():
    """檢查master節點選擇邏輯"""
    
    print("🔍 檢查Master節點選擇邏輯")
    print("=" * 60)
    
    # 15°×15°網格參數
    grid_deg = 15
    lat_min, lat_max = -90, 90
    lon_min, lon_max = -180, 180
    
    def get_pid_grid_center(pid):
        """計算PID對應網格的幾何中心座標"""
        lat_bins = len(range(lat_min, lat_max, grid_deg))  # 12個緯度區間
        lon_bins = len(range(lon_min, lon_max, grid_deg))  # 24個經度區間
        
        # 從PID反推網格索引
        gi = pid // lon_bins  # 緯度索引
        gj = pid % lon_bins   # 經度索引
        
        # 計算網格邊界
        lat_start = lat_min + gi * grid_deg
        lat_end = lat_start + grid_deg
        lon_start = lon_min + gj * grid_deg  
        lon_end = lon_start + grid_deg
        
        # 返回網格中心
        center_lat = (lat_start + lat_end) / 2
        center_lon = (lon_start + lon_end) / 2
        return center_lat, center_lon
    
    def calculate_distance(lat1, lon1, lat2, lon2):
        """計算兩點之間的距離（簡化歐幾里得距離）"""
        return ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5
    
    # 測試幾個關鍵PID的網格中心
    test_pids = [212, 213]  # 上海和東京的PID
    
    for pid in test_pids:
        center_lat, center_lon = get_pid_grid_center(pid)
        print(f"\n📍 PID {pid} 網格中心:")
        print(f"   座標: ({center_lat:.1f}°, {center_lon:.1f}°)")
        
        # 計算網格邊界
        lat_bins = len(range(lat_min, lat_max, grid_deg))
        lon_bins = len(range(lon_min, lon_max, grid_deg))
        gi = pid // lon_bins
        gj = pid % lon_bins
        lat_start = lat_min + gi * grid_deg
        lat_end = lat_start + grid_deg
        lon_start = lon_min + gj * grid_deg  
        lon_end = lon_start + grid_deg
        
        print(f"   網格範圍: [{lat_start}°, {lat_end}°) × [{lon_start}°, {lon_end}°)")
        
        if pid == 212:
            print(f"   🇨🇳 上海實際位置: (31.22°N, 121.46°E)")
            distance = calculate_distance(center_lat, center_lon, 31.22, 121.46)
            print(f"   📏 距離網格中心: {distance:.2f}°")
        elif pid == 213:
            print(f"   🇯🇵 東京實際位置: (35.69°N, 139.69°E)")
            distance = calculate_distance(center_lat, center_lon, 35.69, 139.69)
            print(f"   📏 距離網格中心: {distance:.2f}°")
    
    print(f"\n💡 當前Master選擇邏輯分析:")
    print(f"   ❌ 使用 min(members)：選擇ID最小的衛星")
    print(f"   ✅ 應該使用：選擇最接近網格中心的衛星")
    print(f"   🔧 改進方案：計算每個衛星到網格中心的距離，選擇最近的")
    
    print(f"\n🎯 Master節點設計理念:")
    print(f"   ✓ Master是虛擬節點概念")
    print(f"   ✓ 隨時間變化由不同實體衛星接管")
    print(f"   ✓ 應位於網格幾何中心附近")
    print(f"   ✓ 負責PID間的gateway路由決策")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_master_node_positioning()