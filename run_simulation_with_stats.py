#!/usr/bin/env python3
"""
包裝腳本：運行模擬並輸出控制信令統計
"""

import sys
import os
import argparse

# 添加 satgenpy 到路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'satgenpy'))

def run_simulation_with_stats(algorithm_name, output_dir, duration_seconds=300):
    """
    運行模擬並輸出控制信令統計
    """
    print(f"Running simulation with {algorithm_name} for {duration_seconds} seconds...")
    
    # 創建輸出目錄
    os.makedirs(output_dir, exist_ok=True)
    
    # 動態導入演算法
    if algorithm_name == "algorithm_hierarchical_virtual_pid":
        from satgen.dynamic_state import algorithm_hierarchical_virtual_pid as alg_module
    elif algorithm_name == "algorithm_free_one_only_over_isls":
        from satgen.dynamic_state import algorithm_free_one_only_over_isls as alg_module
    else:
        raise ValueError(f"Unknown algorithm: {algorithm_name}")
    
    # 初始化演算法
    alg_module.init()
    
    # 模擬簡化的網絡場景（你需要根據實際情況調整）
    # 這裡是一個示例框架
    simulate_network_scenario(alg_module, duration_seconds)
    
    # 保存統計數據
    if hasattr(alg_module, 'save_signaling_stats'):
        stats_file = os.path.join(output_dir, "signaling_stats.txt")
        alg_module.save_signaling_stats(stats_file)
        print(f"Statistics saved to: {stats_file}")
        
        # 也獲取數據並打印摘要
        if hasattr(alg_module, 'get_signaling_stats'):
            stats = alg_module.get_signaling_stats()
            print(f"Total control messages: {stats.get('total_messages', 0)}")
    else:
        print("Warning: Algorithm does not support signaling statistics")

def simulate_network_scenario(alg_module, duration_seconds):
    """
    模擬網絡場景（簡化版）
    """
    import time
    import random
    
    print("Simulating network scenario...")
    
    # 模擬網絡變化（你需要根據實際的 25x25 網格調整）
    time_steps = duration_seconds // 1  # 每秒一次更新
    
    for step in range(time_steps):
        # 模擬時間戳
        timestamp_ns = step * 1_000_000_000  # 轉換為納秒
        
        # 創建模擬的 payload（你需要根據實際數據結構調整）
        payload = create_simulation_payload(step, timestamp_ns)
        
        # 運行演算法一步
        if hasattr(alg_module, 'step'):
            result = alg_module.step(payload)
        
        # 模擬一些隨機的網絡變化
        if random.random() < 0.1:  # 10% 機率有拓撲變化
            if hasattr(alg_module, '_SIGNALING_STATS'):
                alg_module._SIGNALING_STATS.record_topology_change(timestamp_ns)
        
        # 進度顯示
        if step % 60 == 0:  # 每分鐘顯示一次
            print(f"Simulated {step} seconds...")
    
    print(f"Simulation completed: {duration_seconds} seconds")

def create_simulation_payload(step, timestamp_ns):
    """
    創建模擬的 payload 數據
    注意：這是簡化版，實際使用時需要真實的衛星網絡數據
    """
    # 這裡需要根據你的實際數據結構來調整
    # 以下是一個基本框架
    
    num_satellites = 625  # 25x25 網格
    num_ground_stations = 100
    
    payload = {
        "time_since_epoch_ns": timestamp_ns,
        "sat_ids": list(range(num_satellites)),
        "sat_nadir_latlon": {},  # 需要真實的衛星位置數據
        "G_sat_isls": None,      # 需要真實的 ISL 圖
        "satellites": num_satellites,
        "ground_stations": num_ground_stations,
        "sat_neighbor_to_if_map": {},
        "gs_pairs": [],
        "fstate": {},
        "output_dynamic_state_dir": "/tmp/sim_output",
        "ground_station_satellites_in_range": {},
        "num_isls_per_sat": [4] * num_satellites,
        "sat_neighbor_to_if": {},
        "list_gsl_interfaces_info": {},
        "enable_verbose_logs": False
    }
    
    return payload

def main():
    parser = argparse.ArgumentParser(description='Run simulation with signaling statistics')
    parser.add_argument('--algorithm', required=True, 
                       choices=['algorithm_hierarchical_virtual_pid', 'algorithm_free_one_only_over_isls'],
                       help='Algorithm to test')
    parser.add_argument('--output-dir', required=True, help='Output directory')
    parser.add_argument('--duration', type=int, default=300, help='Simulation duration in seconds')
    
    args = parser.parse_args()
    
    try:
        run_simulation_with_stats(args.algorithm, args.output_dir, args.duration)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()