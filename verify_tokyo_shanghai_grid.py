#!/usr/bin/env python3
"""
驗證東京和上海的地理網格歸屬
確認它們是否確實在同一個15°×15°網格內
"""

import math

def check_tokyo_shanghai_grid():
    """檢查東京和上海的地理網格歸屬"""
    
    print("🌏 檢查東京和上海的地理網格歸屬")
    print("=" * 60)
    
    # 東京和上海的實際座標
    tokyo_lat, tokyo_lon = 35.69, 139.69
    shanghai_lat, shanghai_lon = 31.22, 121.46
    
    print(f"📍 實際座標:")
    print(f"   東京: ({tokyo_lat:.2f}°N, {tokyo_lon:.2f}°E)")
    print(f"   上海: ({shanghai_lat:.2f}°N, {shanghai_lon:.2f}°E)")
    
    # 15°×15°網格計算
    grid_deg = 15
    lat_min, lat_max = -90, 90
    lon_min, lon_max = -180, 180
    
    def latlon_to_grid(lat, lon):
        """計算經緯度對應的網格索引"""
        if not (lat_min <= lat < lat_max and lon_min <= lon < lon_max):
            return None, None
        gi = int((lat - lat_min) // grid_deg)
        gj = int((lon - lon_min) // grid_deg)
        return gi, gj
    
    def grid_to_pid(gi, gj):
        """網格索引轉PID"""
        lat_bins = list(range(lat_min, lat_max, grid_deg))
        lon_bins = list(range(lon_min, lon_max, grid_deg))
        return gi * len(lon_bins) + gj
    
    # 計算東京的網格
    tokyo_gi, tokyo_gj = latlon_to_grid(tokyo_lat, tokyo_lon)
    tokyo_pid = grid_to_pid(tokyo_gi, tokyo_gj)
    
    # 計算上海的網格
    shanghai_gi, shanghai_gj = latlon_to_grid(shanghai_lat, shanghai_lon)
    shanghai_pid = grid_to_pid(shanghai_gi, shanghai_gj)
    
    print(f"\n📊 網格計算結果:")
    print(f"   東京網格: ({tokyo_gi}, {tokyo_gj}) → PID {tokyo_pid}")
    print(f"   上海網格: ({shanghai_gi}, {shanghai_gj}) → PID {shanghai_pid}")
    
    # 計算網格邊界
    tokyo_lat_start = lat_min + tokyo_gi * grid_deg
    tokyo_lat_end = tokyo_lat_start + grid_deg
    tokyo_lon_start = lon_min + tokyo_gj * grid_deg
    tokyo_lon_end = tokyo_lon_start + grid_deg
    
    shanghai_lat_start = lat_min + shanghai_gi * grid_deg
    shanghai_lat_end = shanghai_lat_start + grid_deg
    shanghai_lon_start = lon_min + shanghai_gj * grid_deg
    shanghai_lon_end = shanghai_lon_start + grid_deg
    
    print(f"\n🗺️  網格邊界:")
    print(f"   東京網格範圍: [{tokyo_lat_start}°, {tokyo_lat_end}°) × [{tokyo_lon_start}°, {tokyo_lon_end}°)")
    print(f"   上海網格範圍: [{shanghai_lat_start}°, {shanghai_lat_end}°) × [{shanghai_lon_start}°, {shanghai_lon_end}°)")
    
    # 檢查是否在同一網格
    same_grid = (tokyo_gi == shanghai_gi) and (tokyo_gj == shanghai_gj)
    
    print(f"\n🎯 結論:")
    if same_grid:
        print(f"   ✅ 東京和上海在同一個15°×15°網格內 (PID {tokyo_pid})")
        print(f"   ✅ 符合您的設計理念：同網格統一PID")
    else:
        print(f"   ❌ 東京和上海在不同網格內")
        print(f"   ❌ 需要檢查為什麼會被統一到PID 213")
        
        # 計算距離和相鄰關係
        gi_diff = abs(tokyo_gi - shanghai_gi)
        gj_diff = abs(tokyo_gj - shanghai_gj)
        print(f"   📏 網格間距: Δlat={gi_diff}, Δlon={gj_diff}")
        
        if gi_diff <= 1 and gj_diff <= 1:
            print(f"   📍 它們是相鄰網格，可能通過路徑包含策略統一")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_tokyo_shanghai_grid()