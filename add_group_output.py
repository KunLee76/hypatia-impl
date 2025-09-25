#!/usr/bin/env python3
"""
為Virtual PID算法添加群組信息輸出功能
"""

import sys
import os

def add_group_output_to_virtual_pid():
    """為virtual_pid算法添加群組輸出功能"""
    
    file_path = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_pid.py"
    
    # 讀取原文件
    with open(file_path, 'r') as f:
        content = f.read()
    
    # 檢查是否已經添加了群組輸出功能
    if "# Group assignment output" in content:
        print("✅ 群組輸出功能已存在")
        return
    
    # 找到寫入 fstate 的位置，在其後添加群組輸出
    insert_point = content.find('print(f"  > Virtual PID routing: {len(fstate)} fstate entries written")')
    
    if insert_point == -1:
        print("❌ 無法找到插入點")
        return
    
    # 準備要插入的代碼
    group_output_code = '''
        
        # Group assignment output
        output_filename_groups = f"{output_directory}/pid_groups_{time_ns}.txt"
        with open(output_filename_groups, "w+") as f_groups:
            # 寫入PID群組信息
            f_groups.write("# PID Group Assignment\\n")
            f_groups.write("# Format: pid_idx,grid_coord_i,grid_coord_j,lat_range_min,lat_range_max,lon_range_min,lon_range_max,agent_sat,member_count,member_satellites\\n")
            
            for pid_idx in range(len(router.pids)):
                pid_coord = router.pids[pid_idx]
                members = router.pid_members.get(pid_idx, set())
                agent = router.pid_agent_sat.get(pid_idx)
                
                # 計算地理範圍
                grid_deg = router.grid_deg
                lat_min = -90 + pid_coord[0] * grid_deg
                lat_max = lat_min + grid_deg
                lon_min = -180 + pid_coord[1] * grid_deg
                lon_max = lon_min + grid_deg
                
                member_list = sorted(list(members)) if members else []
                member_str = "|".join(map(str, member_list))
                
                f_groups.write(f"{pid_idx},{pid_coord[0]},{pid_coord[1]},{lat_min},{lat_max},{lon_min},{lon_max},{agent if agent is not None else -1},{len(members)},{member_str}\\n")
        
        # 寫入地面站群組分配
        output_filename_gs_groups = f"{output_directory}/gs_pid_assignment_{time_ns}.txt"
        with open(output_filename_gs_groups, "w+") as f_gs:
            f_gs.write("# Ground Station PID Assignment\\n")
            f_gs.write("# Format: gs_routing_id,gs_index,gs_name,gs_lat,gs_lon,pid_idx,grid_coord_i,grid_coord_j\\n")
            
            for gs_idx, gs_info in enumerate(ground_stations):
                gs_routing_id = num_satellites + gs_idx
                gs_lat = gs_info['lat_rad'] * 180 / 3.14159265359  # 轉回度數
                gs_lon = gs_info['lon_rad'] * 180 / 3.14159265359
                gs_name = gs_info.get('name', f'GS_{gs_idx}')
                
                pid_idx = router.latlon_to_pid(gs_lat, gs_lon)
                if pid_idx is not None:
                    pid_coord = router.pids[pid_idx]
                    f_gs.write(f"{gs_routing_id},{gs_idx},{gs_name},{gs_lat:.6f},{gs_lon:.6f},{pid_idx},{pid_coord[0]},{pid_coord[1]}\\n")
                else:
                    f_gs.write(f"{gs_routing_id},{gs_idx},{gs_name},{gs_lat:.6f},{gs_lon:.6f},-1,-1,-1\\n")
        
        print(f"  > Group assignment output: {output_filename_groups}")
        print(f"  > Ground station groups: {output_filename_gs_groups}")'''
    
    # 插入代碼
    new_content = content[:insert_point] + content[insert_point:insert_point+100] + group_output_code + content[insert_point+100:]
    
    # 寫回文件
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    print("✅ 已添加群組輸出功能到 virtual_pid 算法")

def show_group_analysis_summary():
    """顯示群組分析總結"""
    print("🌐 Virtual PID 群組分析總結")
    print("=" * 60)
    print("""
📋 主要發現:

🎯 地面站ID映射:
  • 路由系統中的地面站ID = 衛星數量(625) + 地面站索引
  • GS625 = 地面站0 (Tokyo, 35.69°N, 139.69°E)
  • GS626 = 地面站1 (Delhi, 28.67°N, 77.22°E)  
  • GS627 = 地面站2 (Shanghai, 31.22°N, 121.46°E)

🗺️ 10°×10° 網格分組 (您使用的配置):
  • GS625 (Tokyo): PID 463, 網格坐標(12,31)
  • GS626 (Delhi): PID 421, 網格坐標(11,25)
  • GS627 (Shanghai): PID 462, 網格坐標(12,30)
  • 結果: 3個不同PID群組 → 跨群組路由

📊 20°×20° 網格分組 (作為對比):
  • GS625 (Tokyo): PID 123, 網格坐標(6,15)
  • GS626 (Delhi): PID 102, 網格坐標(5,12)
  • GS627 (Shanghai): PID 123, 網格坐標(6,15)
  • 結果: 2個不同PID群組 → 部分跨群組路由

🔍 群組分配邏輯:
  • PID索引 = grid_i * (360/網格度數) + grid_j
  • grid_i = int((緯度 + 90) / 網格度數)
  • grid_j = int((經度 + 180) / 網格度數)

⚡ 路由意義:
  • 同PID群組內: 直接路由或通過代理衛星
  • 跨PID群組: 必須通過代理衛星間的路由
  • 您看到的625→626/627路由成功，說明跨群組路由正常工作

🛠️ 如何查看群組信息:
  1. 使用 quick_pid_analysis.py 快速查詢
  2. 運行算法時會輸出群組分配文件(如果添加了輸出功能)
  3. 分析路由路徑中的代理衛星
""")

if __name__ == "__main__":
    show_group_analysis_summary()
    
    print("\n" + "="*60)
    response = input("\n是否要為 virtual_pid 算法添加群組輸出功能? (y/n): ")
    if response.lower() == 'y':
        add_group_output_to_virtual_pid()
    else:
        print("跳過添加群組輸出功能")