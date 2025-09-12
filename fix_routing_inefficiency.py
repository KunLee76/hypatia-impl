#!/usr/bin/env python3
"""
修復分層路由算法中地面站路由低效問題的解決方案

問題分析：
- Tokyo→Shanghai: 1,760km 但需要21跳路由 (84 km/跳)
- Tokyo→Delhi: 5,834km 只需要14跳路由 (417 km/跳)  
- 分層路由算法將地理上相近的地面站分配到不同region，強制通過遠距離衛星路由

解決策略：
1. 地理感知的region分配
2. 相鄰region地面站直接連接
3. 動態master選擇
4. 地面站優先路由策略
"""

import sys
import os
import math

def calculate_geo_distance(lat1, lon1, lat2, lon2):
    """計算兩點間地理距離 (km)"""
    R = 6371  # 地球半徑
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def analyze_current_routing_efficiency():
    """分析當前路由效率"""
    print("=== 當前路由效率分析 ===")
    
    # 已知的路由數據
    routes = [
        ("Tokyo", "Delhi", 1760, 14, (35.69, 139.69), (28.67, 77.22)),
        ("Tokyo", "Shanghai", 1760, 21, (35.69, 139.69), (31.22, 121.46)), 
        ("Delhi", "Shanghai", 4244, 12, (28.67, 77.22), (31.22, 121.46))
    ]
    
    print("地理距離 vs 路由跳數:")
    for src, dst, dist, hops, src_pos, dst_pos in routes:
        actual_dist = calculate_geo_distance(src_pos[0], src_pos[1], dst_pos[0], dst_pos[1])
        efficiency = actual_dist / hops
        status = "⚠️ 異常低效" if efficiency < 200 else "✅ 正常"
        print(f"  {src}→{dst}: {actual_dist:.0f}km, {hops}跳 → {efficiency:.0f} km/跳 {status}")

def propose_fixes():
    """提出修復建議"""
    print("\n=== 修復建議 ===")
    
    print("1. 🗺️ 地理感知region分配:")
    print("   - 基於地理距離而非grid位置分配地面站")
    print("   - 相近地面站應分配到同一region")
    print("   - 考慮地面站密度均衡")
    
    print("\n2. 🔗 增強地面站連接策略:")
    print("   - 允許相鄰region地面站直接通信")
    print("   - 為近距離地面站建立優先路由")
    print("   - 減少對master衛星的依賴")
    
    print("\n3. 🛰️ 智能master選擇:")
    print("   - 動態選擇距離最近的master衛星")
    print("   - 考慮ISL拓撲結構優化master位置")
    print("   - 避免跨region長距離路由")
    
    print("\n4. ⚡ 路由優化策略:")
    print("   - 地面站間距離 < 2000km 時優先直接路由")
    print("   - 多路徑負載均衡")
    print("   - 考慮延遲和帶寬最優化")

def generate_fix_script():
    """生成修復腳本"""
    print("\n=== 生成修復方案 ===")
    
    fix_script = """
# 修改 algorithm_hierarchical_region.py 的建議代碼

def assign_ground_stations_to_regions_geographically(ground_stations, regions):
    \"\"\"基於地理位置分配地面站到regions\"\"\"
    import math
    
    def geo_distance(gs1, gs2):
        # 計算地理距離
        R = 6371
        lat1, lon1 = math.radians(gs1.lat), math.radians(gs1.lon) 
        lat2, lon2 = math.radians(gs2.lat), math.radians(gs2.lon)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))
    
    # 為每個地面站找到最近的region中心
    for gs in ground_stations:
        min_distance = float('inf')
        best_region = None
        
        for region in regions:
            # 計算到region中心的距離
            region_center_lat = sum(sat.lat for sat in region.satellites) / len(region.satellites)
            region_center_lon = sum(sat.lon for sat in region.satellites) / len(region.satellites)
            
            distance = geo_distance(gs, MockGS(region_center_lat, region_center_lon))
            if distance < min_distance:
                min_distance = distance
                best_region = region
        
        best_region.ground_stations.append(gs)
        
        # 如果地面站距離很近 (<2000km)，允許直接連接
        for other_region in regions:
            if other_region != best_region:
                for other_gs in other_region.ground_stations:
                    if geo_distance(gs, other_gs) < 2000:  # 2000km內直接連接
                        add_direct_gs_link(gs, other_gs)

def optimize_master_selection(region):
    \"\"\"為region選擇最優master衛星\"\"\"
    if not region.ground_stations:
        return region.satellites[0]  # 默認選擇
    
    # 計算到所有地面站的平均距離最小的衛星
    best_master = None
    min_avg_distance = float('inf')
    
    for satellite in region.satellites:
        total_distance = 0
        for gs in region.ground_stations:
            distance = satellite_to_gs_distance(satellite, gs)
            total_distance += distance
        
        avg_distance = total_distance / len(region.ground_stations)
        if avg_distance < min_avg_distance:
            min_avg_distance = avg_distance
            best_master = satellite
    
    return best_master

def add_geographical_routing_priority(fstate, ground_stations):
    \"\"\"為地理上相近的地面站添加優先路由\"\"\"
    for i, gs1 in enumerate(ground_stations):
        for j, gs2 in enumerate(ground_stations[i+1:], i+1):
            distance = geo_distance(gs1, gs2)
            
            if distance < 2000:  # 2000km內優先直接路由
                # 檢查是否有更短路徑
                current_path_length = len(get_path(gs1.id, gs2.id, fstate))
                
                if current_path_length > 5:  # 如果當前路徑超過5跳
                    # 尋找更優路由
                    optimize_short_distance_routing(gs1, gs2, fstate)
"""
    
    print("建議修改的核心函數:")
    print(fix_script)

if __name__ == "__main__":
    print("🔧 分層路由地面站低效問題修復分析")
    print("=" * 50)
    
    analyze_current_routing_efficiency()
    propose_fixes()
    generate_fix_script()
    
    print("\n✅ 修復建議已生成！")
    print("下一步：修改 algorithm_hierarchical_region.py 實現這些優化")
