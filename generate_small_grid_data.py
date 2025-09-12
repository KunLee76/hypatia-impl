#!/usr/bin/env python3
"""
生成小網格（如5度×5度）的分層路由數據來測試真正的master衛星效果
"""

import sys
import os
sys.path.append("../../satgenpy")
import satgen
import shutil
import time
import argparse


def generate_small_grid_data():
    """
    生成小網格的分層路由數據
    """
    
    print("🚀 開始生成小網格分層路由數據")
    print("📏 使用 5度×5度 地理網格")
    
    # 設定參數
    BASE_NAME = "25x25_small_grid"
    NICE_NAME = "25x25-SmallGrid-5x5"
    
    # 網絡參數
    MAX_GSL_LENGTH_M = 1089686
    MAX_ISL_LENGTH_M = 1000000000
    NUM_ORBS = 25
    NUM_SATS_PER_ORB = 25
    
    # 仿真參數
    duration_s = 20  # 20秒仿真
    time_step_ms = 100  # 100ms步長
    
    # 小網格參數
    REGION_LAT_STEP = 5.0  # 5度緯度
    REGION_LON_STEP = 5.0  # 5度經度
    
    print(f"  持續時間: {duration_s}s")
    print(f"  時間步長: {time_step_ms}ms") 
    print(f"  地理網格: {REGION_LAT_STEP}° × {REGION_LON_STEP}°")
    print(f"  衛星數量: {NUM_ORBS} × {NUM_SATS_PER_ORB} = {NUM_ORBS * NUM_SATS_PER_ORB}")
    
    # 創建輸出目錄
    output_dir = f"paper/satellite_networks_state/gen_data/{BASE_NAME}_algorithm_hierarchical_region_5x5"
    dynamic_state_dir = f"{output_dir}/dynamic_state_{time_step_ms}ms_for_{duration_s}s"
    
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(dynamic_state_dir, exist_ok=True)
    
    print(f"📁 輸出目錄: {output_dir}")
    
    # 生成基本網絡結構
    print("\n📡 生成衛星網絡...")
    satgen.generate_plus_grid(
        output_dir,
        NUM_ORBS,
        NUM_SATS_PER_ORB,
        53.0,  # 傾角
        550000.0,  # 高度(m)  
        MAX_GSL_LENGTH_M,
        MAX_ISL_LENGTH_M
    )
    
    # 生成地面站
    print("🌍 生成地面站...")
    satgen.generate_ground_stations_top_25(
        output_dir,
        25
    )
    
    # 生成動態狀態 (使用小網格分層路由)
    print("🧭 生成分層路由狀態...")
    start_time = time.time()
    
    satgen.generate_dynamic_state(
        output_dir,
        time_step_ms,
        duration_s * 1000,  # 轉換為ms
        MAX_GSL_LENGTH_M,
        "algorithm_hierarchical_region",
        {
            "region_lat_step": REGION_LAT_STEP,
            "region_lon_step": REGION_LON_STEP,
            "use_region_grouping": True,
            "fast_mode": True,
            "enable_verbose_logs": True
        }
    )
    
    end_time = time.time()
    print(f"⏱️ 路由計算完成，耗時: {end_time - start_time:.2f}秒")
    
    # 寫入描述文件
    with open(f"{output_dir}/description.txt", "w") as f:
        f.write(f"Small Grid Hierarchical Routing Test\n")
        f.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Grid size: {REGION_LAT_STEP}° × {REGION_LON_STEP}°\n")
        f.write(f"Satellites: {NUM_ORBS} × {NUM_SATS_PER_ORB} = {NUM_ORBS * NUM_SATS_PER_ORB}\n")
        f.write(f"Duration: {duration_s}s\n")
        f.write(f"Time step: {time_step_ms}ms\n")
        f.write(f"Algorithm: hierarchical_region with small grid\n")
    
    print(f"\n✅ 小網格數據生成完成！")
    print(f"📂 數據位置: {output_dir}")
    print(f"🧭 動態狀態: {dynamic_state_dir}")
    
    # 建議下一步分析
    print(f"\n💡 建議分析命令:")
    print(f"python analyze_master_routing.py {dynamic_state_dir} 1000 625 626 5.0")
    print(f"python analyze_master_routing.py {dynamic_state_dir} 1000 0 624 5.0")


if __name__ == "__main__":
    generate_small_grid_data()
