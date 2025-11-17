#!/usr/bin/env python3
"""
測試新竹地面站生成

驗證：
1. 格式正確性
2. 笛卡爾座標計算
3. 與其他地面站的相容性
"""

import sys
sys.path.append("satgenpy")
import satgen

def test_hsinchu_ground_station():
    print("=" * 70)
    print("測試新竹地面站生成")
    print("=" * 70)
    
    # 測試檔案路徑
    input_file = "paper/satellite_networks_state/input_data/ground_stations_cities_sorted_by_estimated_2025_pop_top_100_with_hsinchu.basic.txt"
    output_file = "test_ground_stations_with_hsinchu.txt"
    
    print(f"\n1️⃣  讀取輸入檔: {input_file}")
    
    # 生成擴展地面站檔案
    print(f"2️⃣  生成擴展地面站檔: {output_file}")
    satgen.extend_ground_stations(input_file, output_file)
    
    # 讀取並驗證
    print(f"\n3️⃣  驗證生成結果:")
    ground_stations = satgen.read_ground_stations_extended(output_file)
    
    print(f"   總地面站數: {len(ground_stations)}")
    
    # 檢查新竹地面站 (ID 100)
    hsinchu = None
    for gs in ground_stations:
        if gs["gid"] == 100:
            hsinchu = gs
            break
    
    if hsinchu:
        print(f"\n✅ 找到新竹地面站 (ID: {hsinchu['gid']})")
        print(f"   名稱: {hsinchu['name']}")
        print(f"   緯度: {hsinchu['latitude_degrees_str']}°")
        print(f"   經度: {hsinchu['longitude_degrees_str']}°")
        print(f"   海拔: {hsinchu['elevation_m_float']} m")
        print(f"   笛卡爾座標 (X): {hsinchu['cartesian_x']:.2f} m")
        print(f"   笛卡爾座標 (Y): {hsinchu['cartesian_y']:.2f} m")
        print(f"   笛卡爾座標 (Z): {hsinchu['cartesian_z']:.2f} m")
        
        # 計算與其他城市的距離（驗證座標正確性）
        print(f"\n4️⃣  距離驗證:")
        
        # 找台北 (最近的大城市，實際上清單中沒有台北，改用上海)
        shanghai = None
        tokyo = None
        for gs in ground_stations:
            if gs["name"] == "Shanghai":
                shanghai = gs
            if gs["name"] == "Tokyo":
                tokyo = gs
        
        if shanghai:
            import math
            dx = hsinchu['cartesian_x'] - shanghai['cartesian_x']
            dy = hsinchu['cartesian_y'] - shanghai['cartesian_y']
            dz = hsinchu['cartesian_z'] - shanghai['cartesian_z']
            dist_shanghai = math.sqrt(dx**2 + dy**2 + dz**2) / 1000  # km
            print(f"   新竹 → 上海: {dist_shanghai:.1f} km")
            
        if tokyo:
            dx = hsinchu['cartesian_x'] - tokyo['cartesian_x']
            dy = hsinchu['cartesian_y'] - tokyo['cartesian_y']
            dz = hsinchu['cartesian_z'] - tokyo['cartesian_z']
            dist_tokyo = math.sqrt(dx**2 + dy**2 + dz**2) / 1000  # km
            print(f"   新竹 → 東京: {dist_tokyo:.1f} km")
        
        print(f"\n5️⃣  格式檢查:")
        
        # 檢查完整性
        required_fields = ['gid', 'name', 'latitude_degrees_str', 'longitude_degrees_str',
                          'elevation_m_float', 'cartesian_x', 'cartesian_y', 'cartesian_z']
        all_present = all(field in hsinchu for field in required_fields)
        
        if all_present:
            print(f"   ✅ 所有必要欄位都存在")
        else:
            print(f"   ❌ 缺少必要欄位")
            return False
        
        # 檢查 ID 連續性
        ids = sorted([gs['gid'] for gs in ground_stations])
        expected_ids = list(range(len(ground_stations)))
        
        if ids == expected_ids:
            print(f"   ✅ ID 連續 (0-{len(ground_stations)-1})")
        else:
            print(f"   ❌ ID 不連續")
            return False
        
        print(f"\n{'=' * 70}")
        print(f"✅ 新竹地面站測試通過！")
        print(f"{'=' * 70}")
        print(f"\n📌 使用方式：")
        print(f"   修改 main_starlink_550.py 中的地面站來源:")
        print(f"   將 'ground_stations_cities_sorted_by_estimated_2025_pop_top_100.basic.txt'")
        print(f"   改為 'ground_stations_cities_sorted_by_estimated_2025_pop_top_100_with_hsinchu.basic.txt'")
        print(f"\n   或者創建新的 main_helper 參數，例如:")
        print(f"   gs_selection='ground_stations_top_100_with_hsinchu'")
        
        return True
    else:
        print(f"\n❌ 找不到新竹地面站")
        return False

if __name__ == "__main__":
    success = test_hsinchu_ground_station()
    sys.exit(0 if success else 1)
