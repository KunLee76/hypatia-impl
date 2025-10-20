#!/usr/bin/env python3
"""
測試控制信令統計功能

這個腳本測試 ControlSignalingStats 類的基本功能，
並生成一些示例統計數據用於演示分析工具。
"""

import sys
import os
sys.path.append('satgenpy')

from satgen.dynamic_state.algorithm_hierarchical_virtual_pid import ControlSignalingStats
import time

def test_basic_functionality():
    """測試基本功能"""
    print("測試 ControlSignalingStats 基本功能...")
    
    # 創建統計對象
    stats = ControlSignalingStats()
    
    # 測試各種記錄方法
    print("1. 測試路由更新記錄...")
    stats.record_routing_update(0, 100, changed_entries=50, total_entries=1000)
    stats.record_routing_update(1, 200, changed_entries=30, total_entries=1000)
    
    print("2. 測試網關更新記錄...")
    stats.record_gateway_update(0, 150, num_gateways=5, num_pids=25)
    stats.record_gateway_update(1, 250, num_gateways=7, num_pids=25, bytes=200)
    
    print("3. 測試PID重建記錄...")
    stats.record_pid_rebuild(1, 300, num_pids=25, changed_pids=5)
    
    print("4. 測試拓撲變化記錄...")
    stats.record_topology_change(1, 350, delta_isl=10, delta_gsl=-2)
    
    print("5. 測試通用事件記錄...")
    stats.record_event("custom_event", 2, 400, count=3, bytes=120, 
                      detail={"source": "test", "type": "custom"})
    
    # 獲取基本統計
    basic_stats = stats.get_stats()
    print(f"\n基本統計: {basic_stats}")
    
    # 獲取詳細摘要
    summary = stats.get_stats_summary()
    print(f"\n詳細摘要: {summary}")
    
    # 測試時間窗口過濾
    window_summary = stats.get_stats_summary(start_time_ms=150, end_time_ms=350)
    print(f"\n時間窗口摘要 (150-350ms): {window_summary}")
    
    # 獲取CSV數據
    csv_data = stats.get_timeline_csv()
    print(f"\nCSV數據樣本:\n{csv_data[:500]}...")
    
    print("✓ 基本功能測試完成")
    return stats

def generate_sample_data():
    """生成示例數據用於演示"""
    print("\n生成示例統計數據...")
    
    # 模擬兩個不同的算法
    algos = {
        "hierarchical_pid": ControlSignalingStats(),
        "baseline_shortest_path": ControlSignalingStats()
    }
    
    # 模擬100個時間點的數據
    for snapshot in range(100):
        sim_time_ms = snapshot * 100  # 每100ms一個快照
        
        # 算法1 (hierarchical_pid) - 較少的路由更新，但更多的網關管理
        if snapshot % 5 == 0:  # 每5個快照更新一次路由
            algos["hierarchical_pid"].record_routing_update(
                snapshot, sim_time_ms, 
                changed_entries=20 + snapshot % 30,  # 變化的條目數
                total_entries=1000
            )
        
        if snapshot % 10 == 0:  # 每10個快照更新網關
            algos["hierarchical_pid"].record_gateway_update(
                snapshot, sim_time_ms,
                num_gateways=5 + snapshot % 10,
                num_pids=25
            )
        
        if snapshot % 25 == 0:  # 每25個快照重建PID
            algos["hierarchical_pid"].record_pid_rebuild(
                snapshot, sim_time_ms,
                num_pids=25,
                changed_pids=3 + snapshot % 5
            )
        
        # 算法2 (baseline) - 更頻繁的路由更新，無網關管理
        if snapshot % 2 == 0:  # 每2個快照更新路由
            algos["baseline_shortest_path"].record_routing_update(
                snapshot, sim_time_ms,
                changed_entries=80 + snapshot % 50,  # 更多變化
                total_entries=1000
            )
        
        # 兩個算法都有拓撲變化
        if snapshot % 20 == 0:
            for algo_name in algos:
                algos[algo_name].record_topology_change(
                    snapshot, sim_time_ms,
                    delta_isl=5 + snapshot % 10,
                    delta_gsl=-(snapshot % 3)
                )
    
    # 保存統計數據
    output_dir = "test_log_output"
    os.makedirs(output_dir, exist_ok=True)
    
    for algo_name, stats in algos.items():
        filepath = os.path.join(output_dir, f"{algo_name}_signaling_stats.txt")
        stats.save_stats_to_file(filepath)
        print(f"✓ 保存 {algo_name} 統計數據到: {filepath}")
    
    return algos

def test_analysis_integration():
    """測試與分析工具的集成"""
    print("\n測試分析工具集成...")
    
    try:
        from analyze_signaling_stats import load_algorithm_stats, compare_algorithms, analyze_time_window
        
        # 嘗試加載示例數據
        try:
            stats1 = load_algorithm_stats("hierarchical_pid", "test_log_output")
            stats2 = load_algorithm_stats("baseline_shortest_path", "test_log_output")
            print("✓ 成功加載統計數據")
            
            # 測試時間窗口分析
            window_result = analyze_time_window(stats1['timeline'], 
                                             start_time=0, window_size_ms=2000)
            print(f"✓ 時間窗口分析結果: {window_result['total_events']} 事件, "
                  f"{window_result['total_bytes']} 字節")
            
            # 測試算法比較
            comparison = compare_algorithms(stats1, stats2)
            print(f"✓ 算法比較完成，字節差異: {comparison['differences']['total_bytes_diff']}")
            
        except FileNotFoundError:
            print("! 找不到統計文件，請先運行 generate_sample_data()")
        
    except ImportError as e:
        print(f"! 無法導入分析工具: {e}")

def main():
    print("=== 控制信令統計功能測試 ===\n")
    
    # 測試基本功能
    stats = test_basic_functionality()
    
    # 生成示例數據
    algos = generate_sample_data()
    
    # 測試分析集成
    test_analysis_integration()
    
    print(f"\n=== 測試完成 ===")
    print("下一步：")
    print("1. 運行 'python analyze_signaling_stats.py --algo1 hierarchical_pid --plot' 查看可視化")
    print("2. 運行 'python analyze_signaling_stats.py --algo1 hierarchical_pid --algo2 baseline_shortest_path --plot' 比較算法")
    print("3. 在實際的Hypatia模擬中集成統計收集")

if __name__ == '__main__':
    main()