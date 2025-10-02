#!/usr/bin/env python3
"""
分析PID分配的详细调试脚本
"""
import sys
import os

# 添加路径以导入必要的模块
sys.path.append('/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')

from satgen.dynamic_state.algorithm_hierarchical_virtual_pid_clean_fixed import calculate_fstate_hierarchical_virtual_pid_clean_fixed
from satgen.ground_stations import read_ground_stations_extended
from satgen.tles import read_tles
from satgen.isls import read_isls

def analyze_pid_assignments():
    base_path = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast"
    
    print("🔍 分析PID分配...")
    print("=" * 60)
    
    # 读取必要的数据文件
    print("📖 读取卫星和地面站数据...")
    satellites = read_tles(f"{base_path}/tles.txt")
    ground_stations = read_ground_stations_extended(f"{base_path}/ground_stations.txt")
    isls = read_isls(f"{base_path}/isls.txt")
    
    print(f"✅ 载入 {len(satellites)} 颗卫星")
    print(f"✅ 载入 {len(ground_stations)} 个地面站")
    
    # 检查关键地面站的坐标
    print("\n🌍 关键地面站坐标:")
    print("-" * 40)
    
    key_stations = [0, 2]  # GS0(东京), GS2(上海)
    for gs_id in key_stations:
        if gs_id < len(ground_stations):
            gs = ground_stations[gs_id]
            lat = float(gs["latitude_degrees_str"])
            lon = float(gs["longitude_degrees_str"])
            print(f"  GS{gs_id}({gs['name']}): lat={lat:.2f}°, lon={lon:.2f}°")
    
    # 创建一个临时的router实例来测试PID计算
    from satgen.dynamic_state.hierarchical_virtual_pid import HierarchicalVirtualPidRouter
    
    # 设置router参数 (与main script一致)
    router = HierarchicalVirtualPidRouter(
        satellites=satellites,
        ground_stations=ground_stations,
        isls=isls,
        pid_lat_degrees=15.0,  # 15度纬度网格
        pid_lon_degrees=15.0,  # 15度经度网格
        pos_lat_degrees=1.0,
        pos_lon_degrees=1.0
    )
    
    print("\n🧮 PID计算结果:")
    print("-" * 40)
    
    # 计算关键地面站的PID
    for gs_id in key_stations:
        if gs_id < len(ground_stations):
            gs = ground_stations[gs_id]
            lat = float(gs["latitude_degrees_str"])
            lon = float(gs["longitude_degrees_str"])
            pid = router.latlon_to_pid(lat, lon)
            print(f"  GS{gs_id}({gs['name']}): PID={pid}")
    
    # 计算关键卫星的PID (在t=0时刻)
    print("\n🛰️  关键卫星PID (t=0):")
    print("-" * 40)
    
    step = 0
    key_satellites = [189, 139, 625]  # 问题相关的卫星
    for sat_id in key_satellites:
        if sat_id < len(satellites):
            sat_lat, sat_lon = router.get_sat_latlon(sat_id, step)
            pid = router.latlon_to_pid(sat_lat, sat_lon)
            print(f"  卫星{sat_id}: lat={sat_lat:.2f}°, lon={sat_lon:.2f}°, PID={pid}")
    
    print(f"\n📊 统计信息:")
    print(f"  PID网格大小: {router.pid_lat_degrees}° x {router.pid_lon_degrees}°")

if __name__ == "__main__":
    analyze_pid_assignments()