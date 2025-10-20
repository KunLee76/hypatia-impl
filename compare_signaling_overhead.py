#!/usr/bin/env python3
"""
比較兩個路由演算法的控制信令開銷
"""

import os
import sys
import subprocess
import json
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

def run_simulation_with_algorithm(algorithm_name, output_dir, duration_seconds=300):
    """
    運行指定演算法的模擬
    
    Args:
        algorithm_name: 演算法名稱 ("algorithm_free_one_only_over_isls" 或 "algorithm_hierarchical_virtual_pid")
        output_dir: 輸出目錄
        duration_seconds: 模擬時長（秒）
    
    Returns:
        統計數據字典
    """
    print(f"Running simulation with {algorithm_name}...")
    
    # 創建輸出目錄
    alg_output_dir = os.path.join(output_dir, algorithm_name)
    os.makedirs(alg_output_dir, exist_ok=True)
    
    # 運行模擬（這裡需要根據你的實際模擬腳本調整）
    cmd = [
        "python3", 
        "paper/satellite_networks_state/main_25x25_fast.py",
        "--algorithm", algorithm_name,
        "--output-dir", alg_output_dir,
        "--duration", str(duration_seconds)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        if result.returncode != 0:
            print(f"Error running {algorithm_name}: {result.stderr}")
            return None
    except Exception as e:
        print(f"Failed to run simulation: {e}")
        return None
    
    # 讀取統計數據
    stats_file = os.path.join(alg_output_dir, "signaling_stats.txt")
    if os.path.exists(stats_file):
        return parse_stats_file(stats_file)
    else:
        print(f"Stats file not found: {stats_file}")
        return None

def parse_stats_file(filepath):
    """解析統計文件"""
    stats = {}
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            if '=' in line:
                key, value = line.strip().split('=', 1)
                try:
                    stats[key] = int(value)
                except ValueError:
                    stats[key] = value
    return stats

def compare_algorithms(base_algorithm, test_algorithm, output_dir, duration_seconds=300):
    """
    比較兩個演算法的控制信令開銷
    
    Args:
        base_algorithm: 基準演算法
        test_algorithm: 測試演算法
        output_dir: 輸出目錄
        duration_seconds: 模擬時長
    """
    print(f"Comparing {base_algorithm} vs {test_algorithm}")
    
    # 運行兩個演算法
    base_stats = run_simulation_with_algorithm(base_algorithm, output_dir, duration_seconds)
    test_stats = run_simulation_with_algorithm(test_algorithm, output_dir, duration_seconds)
    
    if not base_stats or not test_stats:
        print("Failed to collect statistics from one or both algorithms")
        return
    
    # 生成比較報告
    generate_comparison_report(base_algorithm, base_stats, test_algorithm, test_stats, output_dir)
    
    # 生成圖表
    generate_comparison_charts(base_algorithm, base_stats, test_algorithm, test_stats, output_dir)

def generate_comparison_report(base_alg, base_stats, test_alg, test_stats, output_dir):
    """生成比較報告"""
    report_file = os.path.join(output_dir, "signaling_comparison_report.txt")
    
    with open(report_file, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("控制信令開銷比較報告\n")
        f.write("=" * 60 + "\n")
        f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"基準演算法: {base_alg}\n")
        f.write(f"測試演算法: {test_alg}\n\n")
        
        # 詳細統計
        f.write("詳細統計:\n")
        f.write("-" * 40 + "\n")
        f.write(f"{'指標':<25} {'基準':<15} {'測試':<15} {'差異':<15} {'百分比':<10}\n")
        f.write("-" * 80 + "\n")
        
        metrics = ['routing_updates', 'gateway_updates', 'pid_rebuilds', 'topology_changes', 'total_messages']
        
        for metric in metrics:
            base_val = base_stats.get(metric, 0)
            test_val = test_stats.get(metric, 0)
            diff = test_val - base_val
            percent = ((test_val - base_val) / base_val * 100) if base_val > 0 else float('inf')
            
            f.write(f"{metric:<25} {base_val:<15} {test_val:<15} {diff:<15} {percent:+.1f}%\n")
        
        f.write("\n")
        
        # 總結
        total_base = base_stats.get('total_messages', 0)
        total_test = test_stats.get('total_messages', 0)
        total_diff = total_test - total_base
        total_percent = ((total_test - total_base) / total_base * 100) if total_base > 0 else 0
        
        f.write("總結:\n")
        f.write("-" * 20 + "\n")
        f.write(f"基準演算法總控制信令: {total_base}\n")
        f.write(f"測試演算法總控制信令: {total_test}\n")
        f.write(f"信令開銷差異: {total_diff} ({total_percent:+.1f}%)\n")
        
        if total_diff < 0:
            f.write(f"✓ {test_alg} 減少了 {abs(total_diff)} 個控制信令 ({abs(total_percent):.1f}%)\n")
        elif total_diff > 0:
            f.write(f"⚠ {test_alg} 增加了 {total_diff} 個控制信令 ({total_percent:.1f}%)\n")
        else:
            f.write(f"= 兩個演算法的控制信令開銷相同\n")
    
    print(f"比較報告已保存到: {report_file}")

def generate_comparison_charts(base_alg, base_stats, test_alg, test_stats, output_dir):
    """生成比較圖表"""
    metrics = ['routing_updates', 'gateway_updates', 'pid_rebuilds', 'topology_changes', 'total_messages']
    metric_labels = ['路由更新', 'Gateway更新', 'PID重建', '拓撲變化', '總信令數']
    
    base_values = [base_stats.get(m, 0) for m in metrics]
    test_values = [test_stats.get(m, 0) for m in metrics]
    
    # 創建圖表
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # 柱狀圖比較
    x = range(len(metrics))
    width = 0.35
    
    ax1.bar([i - width/2 for i in x], base_values, width, label=base_alg, alpha=0.8)
    ax1.bar([i + width/2 for i in x], test_values, width, label=test_alg, alpha=0.8)
    
    ax1.set_xlabel('控制信令類型')
    ax1.set_ylabel('信令數量')
    ax1.set_title('控制信令開銷比較')
    ax1.set_xticks(x)
    ax1.set_xticklabels(metric_labels, rotation=45, ha='right')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 差異百分比圖
    differences = []
    for base_val, test_val in zip(base_values, test_values):
        if base_val > 0:
            diff_percent = (test_val - base_val) / base_val * 100
        else:
            diff_percent = 0
        differences.append(diff_percent)
    
    colors = ['red' if d > 0 else 'green' if d < 0 else 'gray' for d in differences]
    bars = ax2.bar(x, differences, color=colors, alpha=0.7)
    
    ax2.set_xlabel('控制信令類型')
    ax2.set_ylabel('差異百分比 (%)')
    ax2.set_title(f'{test_alg} 相對於 {base_alg} 的信令差異')
    ax2.set_xticks(x)
    ax2.set_xticklabels(metric_labels, rotation=45, ha='right')
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax2.grid(True, alpha=0.3)
    
    # 添加數值標籤
    for i, (bar, diff) in enumerate(zip(bars, differences)):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + (1 if height >= 0 else -3),
                f'{diff:+.1f}%', ha='center', va='bottom' if height >= 0 else 'top')
    
    plt.tight_layout()
    
    # 保存圖表
    chart_file = os.path.join(output_dir, "signaling_comparison.png")
    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"比較圖表已保存到: {chart_file}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python compare_signaling_overhead.py <base_algorithm> <test_algorithm> [duration_seconds]")
        print("Example: python compare_signaling_overhead.py algorithm_free_one_only_over_isls algorithm_hierarchical_virtual_pid 300")
        sys.exit(1)
    
    base_algorithm = sys.argv[1]
    test_algorithm = sys.argv[2]
    duration_seconds = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    
    output_dir = f"signaling_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"開始比較控制信令開銷...")
    print(f"基準演算法: {base_algorithm}")
    print(f"測試演算法: {test_algorithm}")
    print(f"模擬時長: {duration_seconds} 秒")
    print(f"輸出目錄: {output_dir}")
    
    compare_algorithms(base_algorithm, test_algorithm, output_dir, duration_seconds)
    
    print("\n比較完成！")
    print(f"結果保存在: {output_dir}/")

if __name__ == "__main__":
    main()