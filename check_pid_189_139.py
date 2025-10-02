#!/usr/bin/env python3
"""
检查卫星189和139的PID分配
"""

import sys
import os

# 添加satgen路径
sys.path.append('/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')

from satgen.dynamic_state.algorithm_hierarchical_virtual_pid_clean_fixed import *

def check_pid_assignments():
    """检查189和139的PID分配"""
    
    print("🎯 检查卫星189和139的PID分配")
    print("=" * 50)
    
    # 模拟算法环境
    data_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast"
    
    # 加载基础数据
    ground_stations = read_ground_stations_file(f"{data_dir}/ground_stations.txt")
    
    print(f"📍 地面站信息:")
    print(f"   GS0(Tokyo): {ground_stations[0]}")
    print(f"   GS2(Shanghai): {ground_stations[2]}")
    
    # 创建路由器
    router = HierarchicalRouter(len(ground_stations), 25, 15)
    
    # 获取地面站坐标
    def get_ground_station_latlon(gs_id):
        gs_data = ground_stations[gs_id]
        lat = float(gs_data['latitude_degrees_str'])
        lon = float(gs_data['longitude_degrees_str'])
        return lat, lon
        
    # 检查地面站PID
    gs0_lat, gs0_lon = get_ground_station_latlon(0)  # Tokyo
    gs2_lat, gs2_lon = get_ground_station_latlon(2)  # Shanghai
    
    pid_gs0 = router.latlon_to_pid(gs0_lat, gs0_lon)
    pid_gs2 = router.latlon_to_pid(gs2_lat, gs2_lon)
    
    print(f"🌍 地面站PID分配:")
    print(f"   GS0(Tokyo): lat={gs0_lat}, lon={gs0_lon} -> PID={pid_gs0}")
    print(f"   GS2(Shanghai): lat={gs2_lat}, lon={gs2_lon} -> PID={pid_gs2}")
    
    # 检查统一后的PID
    def unified_pid_for_adjacent_regions(base_pid):
        if base_pid in [212, 213]:  # Tokyo和Shanghai区域  
            return 213  # 统一到PID 213
        return base_pid
        
    unified_pid_gs0 = unified_pid_for_adjacent_regions(pid_gs0)
    unified_pid_gs2 = unified_pid_for_adjacent_regions(pid_gs2)
    
    print(f"🤝 统一后PID:")
    print(f"   GS0 -> 统一PID {unified_pid_gs0}")
    print(f"   GS2 -> 统一PID {unified_pid_gs2}")
    print(f"   same_pid = {unified_pid_gs0 == unified_pid_gs2}")

if __name__ == "__main__":
    check_pid_assignments()