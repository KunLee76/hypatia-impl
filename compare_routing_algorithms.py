#!/usr/bin/env python3
"""
Hypatia 路由算法控制信令比較工具

比較 Hierarchical Virtual PID 算法與 Floyd-Warshall 基線算法的控制信令開銷

使用方法:
1. 先運行兩個算法生成統計數據
2. 使用此腳本進行比較分析
"""

import sys
import os
import argparse
from pathlib import Path

# 添加路徑以導入算法模塊
sys.path.append('satgenpy')

def load_algorithm_stats_from_output(algorithm_name, log_file_path):
    """
    從算法執行的輸出文件中提取控制信令統計
    
    Args:
        algorithm_name: 算法名稱
        log_file_path: 日誌文件路徑
    
    Returns:
        dict: 統計數據摘要
    """
    
    if not Path(log_file_path).exists():
        raise FileNotFoundError(f"找不到日誌文件: {log_file_path}")
    
    print(f"正在分析 {algorithm_name} 的日誌文件: {log_file_path}")
    
    # 嘗試從不同的來源加載統計數據
    
    # 方法1: 如果算法有直接的統計導出
    try:
        if algorithm_name == "hierarchical_pid":
            from satgen.dynamic_state.algorithm_hierarchical_virtual_pid import _SIGNALING_STATS
            return {
                "algorithm": algorithm_name,
                "stats": _SIGNALING_STATS.get_stats_summary(),
                "source": "direct_stats_object"
            }
        elif algorithm_name == "baseline_floyd_warshall":
            from satgen.dynamic_state.algorithm_free_one_only_over_isls_with_stats import _BASELINE_SIGNALING_STATS
            return {
                "algorithm": algorithm_name,
                "stats": _BASELINE_SIGNALING_STATS.get_stats_summary(),
                "source": "direct_stats_object"
            }
    except Exception as e:
        print(f"  無法直接加載統計對象: {e}")
    
    # 方法2: 解析日誌文件中的統計輸出
    with open(log_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找統計輸出
    import re
    
    # 查找控制信令統計信息
    signaling_patterns = {
        'routing_updates': r'\[SIGNALING\].*路由更新.*?(\d+)/(\d+).*?條目',
        'total_events': r'\[SIGNALING\].*累計統計.*?(\d+)\s*事件',
        'total_bytes': r'\[SIGNALING\].*累計統計.*?(\d+)\s*字節',
        'topology_changes': r'\[SIGNALING\].*拓撲變化'
    }
    
    extracted_stats = {
        "routing_updates": 0,
        "total_events": 0,
        "total_bytes": 0,
        "topology_changes": 0,
        "algorithm": algorithm_name
    }
    
    # 提取統計數據
    for stat_name, pattern in signaling_patterns.items():
        matches = re.findall(pattern, content)
        if matches:
            if stat_name in ['total_events', 'total_bytes']:
                # 取最後一個匹配（最終統計）
                extracted_stats[stat_name] = int(matches[-1])
            elif stat_name == 'routing_updates':
                # 計算路由更新總數
                extracted_stats[stat_name] = len(matches)
            elif stat_name == 'topology_changes':
                extracted_stats[stat_name] = len(matches)
    
    return {
        "algorithm": algorithm_name,
        "stats": extracted_stats,
        "source": "log_file_parsing"
    }

def compare_algorithms(hierarchical_stats, baseline_stats):
    """
    比較兩個算法的控制信令開銷
    """
    
    print("\n" + "="*60)
    print("控制信令算法比較報告")
    print("="*60)
    
    h_stats = hierarchical_stats["stats"]
    b_stats = baseline_stats["stats"]
    
    # 處理不同的統計數據格式
    def get_stat(stats, key, default=0):
        if isinstance(stats, dict):
            if key == "total_events" and "total_events" in stats:
                return stats["total_events"]
            elif key == "total_bytes" and "total_bytes" in stats:
                return stats["total_bytes"]
            elif key == "routing_updates":
                if "by_type" in stats and "routing_update" in stats["by_type"]:
                    return stats["by_type"]["routing_update"]["count"]
                elif "routing_updates" in stats:
                    return stats["routing_updates"]
            elif key == "gateway_updates":
                if "by_type" in stats and "gateway_update" in stats["by_type"]:
                    return stats["by_type"]["gateway_update"]["count"]
                elif "gateway_updates" in stats:
                    return stats["gateway_updates"]
            elif key == "pid_rebuilds":
                if "by_type" in stats and "pid_rebuild" in stats["by_type"]:
                    return stats["by_type"]["pid_rebuild"]["count"]
                elif "pid_rebuilds" in stats:
                    return stats["pid_rebuilds"]
            elif key == "topology_changes":
                if "by_type" in stats and "topology_change" in stats["by_type"]:
                    return stats["by_type"]["topology_change"]["count"]
                elif "topology_changes" in stats:
                    return stats["topology_changes"]
        return default
    
    # 提取關鍵統計數據
    h_total_events = get_stat(h_stats, "total_events")
    h_total_bytes = get_stat(h_stats, "total_bytes")
    h_routing = get_stat(h_stats, "routing_updates")
    h_gateway = get_stat(h_stats, "gateway_updates")
    h_pid = get_stat(h_stats, "pid_rebuilds")
    h_topo = get_stat(h_stats, "topology_changes")
    
    b_total_events = get_stat(b_stats, "total_events")
    b_total_bytes = get_stat(b_stats, "total_bytes")
    b_routing = get_stat(b_stats, "routing_updates")
    b_topo = get_stat(b_stats, "topology_changes")
    
    print(f"\nHierarchical Virtual PID 算法:")
    print(f"  總事件數: {h_total_events:,}")
    print(f"  總字節數: {h_total_bytes:,}")
    print(f"  路由更新: {h_routing}")
    print(f"  網關更新: {h_gateway}")
    print(f"  PID重建: {h_pid}")
    print(f"  拓撲變化: {h_topo}")
    
    print(f"\nFloyd-Warshall 基線算法:")
    print(f"  總事件數: {b_total_events:,}")
    print(f"  總字節數: {b_total_bytes:,}")
    print(f"  路由更新: {b_routing}")
    print(f"  網關更新: 0 (不支持)")
    print(f"  PID重建: 0 (不支持)")
    print(f"  拓撲變化: {b_topo}")
    
    # 計算改進幅度
    print(f"\n性能改進分析:")
    
    if b_total_bytes > 0:
        bytes_improvement = (b_total_bytes - h_total_bytes) / b_total_bytes * 100
        print(f"  控制開銷減少: {bytes_improvement:.1f}%")
        print(f"  絕對節省: {b_total_bytes - h_total_bytes:,} 字節")
    
    if b_total_events > 0:
        events_diff = b_total_events - h_total_events
        print(f"  事件數差異: {events_diff:+,}")
    
    if b_routing > 0:
        routing_improvement = (b_routing - h_routing) / b_routing * 100
        print(f"  路由更新減少: {routing_improvement:.1f}%")
    
    print(f"\n算法特性比較:")
    print(f"  Hierarchical PID:")
    print(f"    - 分層路由架構，區域化管理")
    print(f"    - PID網格化，減少全網計算")
    print(f"    - 智能網關選擇")
    print(f"    - 增量路由更新")
    
    print(f"  Floyd-Warshall 基線:")
    print(f"    - 全網最短路徑計算")
    print(f"    - 每次快照重新計算所有路徑")
    print(f"    - 無分層管理")
    print(f"    - 高控制開銷")
    
    if bytes_improvement > 0:
        print(f"\n🎉 結論: Hierarchical PID 算法顯著降低了控制信令開銷!")
        print(f"   在相同的網絡條件下節省了 {bytes_improvement:.1f}% 的控制開銷")
    else:
        print(f"\n⚠️ 注意: 需要進一步分析控制開銷的來源")
    
    return {
        "hierarchical_improvement_percentage": bytes_improvement if b_total_bytes > 0 else 0,
        "absolute_bytes_saved": b_total_bytes - h_total_bytes if b_total_bytes > 0 else 0,
        "hierarchical_stats": h_stats,
        "baseline_stats": b_stats
    }

def main():
    parser = argparse.ArgumentParser(description='比較 Hypatia 路由算法的控制信令開銷')
    parser.add_argument('--hierarchical-log', required=True, help='Hierarchical PID 算法的日誌文件')
    parser.add_argument('--baseline-log', required=True, help='Floyd-Warshall 基線算法的日誌文件')
    parser.add_argument('--output', help='輸出比較報告文件路徑')
    
    args = parser.parse_args()
    
    try:
        # 加載兩個算法的統計數據
        hierarchical_stats = load_algorithm_stats_from_output("hierarchical_pid", args.hierarchical_log)
        baseline_stats = load_algorithm_stats_from_output("baseline_floyd_warshall", args.baseline_log)
        
        print(f"成功加載統計數據:")
        print(f"  Hierarchical PID: {hierarchical_stats['source']}")
        print(f"  Floyd-Warshall: {baseline_stats['source']}")
        
        # 進行比較
        comparison_result = compare_algorithms(hierarchical_stats, baseline_stats)
        
        # 保存報告
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write("Hypatia 路由算法控制信令比較報告\\n")
                f.write("="*50 + "\\n\\n")
                f.write(f"Hierarchical PID 改進: {comparison_result['hierarchical_improvement_percentage']:.1f}%\\n")
                f.write(f"絕對節省: {comparison_result['absolute_bytes_saved']:,} 字節\\n")
            print(f"\\n比較報告已保存到: {args.output}")
        
        print(f"\\n比較完成!")
        
    except Exception as e:
        print(f"錯誤: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()