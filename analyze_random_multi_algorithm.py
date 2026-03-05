#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分析隨機 ISL 失效場景的多演算法比較
比較 Baseline、LoHi、GRHR (K=4) 三種演算法
"""

import json
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd
from pathlib import Path

# 使用非交互式後端
matplotlib.use('Agg')

# 支援英文標籤（避免中文字體問題）
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans']
plt.rcParams['axes.unicode_minus'] = False

# 配置
DATA_DIR = Path("paper/satellite_networks_state/analytic_result")
OUTPUT_DIR = Path("random_failure_analysis")
OUTPUT_DIR.mkdir(exist_ok=True)

# 場景配置
SCENARIOS = {
    'p1': {'label': 'Random 1% ISL Failure', 'failure_rate': '1%'},
    'p5': {'label': 'Random 5% ISL Failure', 'failure_rate': '5%'},
    'p10': {'label': 'Random 10% ISL Failure', 'failure_rate': '10%'}
}

# 控制信令模型（用於計算字節數）
CTRL_HDR_BYTES = 32
ROUTE_ENTRY_BYTES = 32
GATEWAY_ENTRY_BYTES = 32
ID_ENTRY_BYTES = 32

def calculate_bytes_from_timeline(timeline):
    """從 timeline 重新計算字節數"""
    routing_bytes = 0
    gateway_bytes = 0
    gid_bytes = 0
    pid_bytes = 0  # LoHi's PID rebuild
    control_bytes = 0  # 控制信令（不含 routing_update）
    
    for entry in timeline:
        event = entry.get('event') or entry.get('type', '')
        detail = entry.get('detail', {})
        
        if event == 'routing_update':
            changed_entries = detail.get('changed_entries', 0)
            bytes_val = CTRL_HDR_BYTES + changed_entries * ROUTE_ENTRY_BYTES
            routing_bytes += bytes_val
        elif event == 'gateway_update':
            num_messages = detail.get('num_messages', 0)
            num_entries = detail.get('num_entries', 0)
            if num_messages == 0 and num_entries == 0:
                changed_pairs = detail.get('changed_pairs', 0)
                k = detail.get('k', 0) or detail.get('k_used', 0)
                num_messages = changed_pairs
                num_entries = changed_pairs * max(k, 1)
            bytes_val = num_messages * CTRL_HDR_BYTES + num_entries * GATEWAY_ENTRY_BYTES
            gateway_bytes += bytes_val
            control_bytes += bytes_val
        elif event == 'gid_rebuild':
            changed_gids = detail.get('changed_gids', 0)
            bytes_val = CTRL_HDR_BYTES + changed_gids * ID_ENTRY_BYTES
            gid_bytes += bytes_val
            control_bytes += bytes_val
        elif event == 'pid_rebuild':
            # LoHi's PID (Path ID) rebuild: HDR + changed_pids * ID_SIZE
            changed_pids = detail.get('changed_pids', 0)
            bytes_val = CTRL_HDR_BYTES + changed_pids * ID_ENTRY_BYTES
            pid_bytes += bytes_val
            control_bytes += bytes_val
        elif event == 'topology_change':
            # 簡化的拓撲變化開銷
            bytes_val = CTRL_HDR_BYTES
            control_bytes += bytes_val
    
    return {
        'routing_bytes': routing_bytes,
        'gateway_bytes': gateway_bytes,
        'gid_bytes': gid_bytes,
        'pid_bytes': pid_bytes,
        'control_bytes': control_bytes,
        'total_bytes': routing_bytes + gateway_bytes + gid_bytes + pid_bytes
    }

def load_stats(filepath, algorithm_type='grhr'):
    """載入統計文件並計算指標
    
    Args:
        filepath: 統計文件路徑
        algorithm_type: 'grhr', 'lohi', 或 'baseline'
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    summary = data.get('summary', {})
    by_type = summary.get('by_type', {})
    timeline = data.get('timeline', [])
    
    # 從 timeline 計算字節數
    bytes_info = calculate_bytes_from_timeline(timeline)
    
    # 計算控制信令：只有 GRHR 排除 routing_update
    control_signaling_bytes = bytes_info['total_bytes']
    control_events = summary.get('total_events', 0)
    
    if algorithm_type == 'grhr':
        # GRHR: 排除 routing_update（衛星自行計算，無需傳輸）
        routing_bytes = by_type.get('routing_update', {}).get('bytes', 0)
        routing_events = by_type.get('routing_update', {}).get('count', 0)
        # 如果 summary 沒有 bytes，使用我們計算的
        if routing_bytes == 0:
            routing_bytes = bytes_info['routing_bytes']
        control_signaling_bytes = bytes_info['total_bytes'] - routing_bytes
        control_events = summary.get('total_events', 0) - routing_events
    
    # 事件類型統計
    event_stats = {}
    for event_type, stats in by_type.items():
        event_stats[event_type] = stats.get('count', 0)
    
    return {
        'total_events': summary.get('total_events', 0),
        'control_events': control_events,
        'control_signaling_bytes': control_signaling_bytes,
        'total_bytes': bytes_info['total_bytes'],
        'control_bytes': bytes_info['control_bytes'],
        'routing_bytes': bytes_info['routing_bytes'],
        'gateway_bytes': bytes_info['gateway_bytes'],
        'gid_bytes': bytes_info['gid_bytes'],
        'pid_bytes': bytes_info['pid_bytes'],
        'event_stats': event_stats,
        'by_type': by_type,
        'data': data  # 保留原始數據用於時間軸繪圖
    }

def generate_comparison_chart(scenario, stats_dict):
    """生成單一場景的三演算法比較圖（1x2 子圖）"""
    
    algorithms = ['Baseline', 'LoHi', 'GRHR (K=4)']
    colors = ['coral', 'mediumpurple', '#228B22']
    
    # 創建 1x2 子圖
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(f'Algorithm Comparison: {SCENARIOS[scenario]["label"]}', 
                 fontsize=16, fontweight='bold')
    
    # === 子圖1：Total Control Signaling (MB) ===
    ax1 = axes[0]
    control_signaling_mb = [
        stats_dict['baseline']['control_signaling_bytes'] / (1024 * 1024),
        stats_dict['lohi']['control_signaling_bytes'] / (1024 * 1024),
        stats_dict['grhr']['control_signaling_bytes'] / (1024 * 1024)
    ]
    bars1 = ax1.bar(algorithms, control_signaling_mb, color=colors, alpha=0.85, 
                   edgecolor='black', linewidth=0.5, width=0.5)
    ax1.set_ylabel('Total Control Signaling (MB)', fontsize=13, fontweight='bold')
    ax1.set_title('Total Control Signaling (MB)', fontsize=15, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    
    for bar, value in zip(bars1, control_signaling_mb):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{value:.2f}',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # === 子圖2：事件類型分布（分組柱狀圖）===
    ax2 = axes[1]
    
    # 收集所有可能的事件類型
    all_event_types = set()
    for algo_key in ['baseline', 'lohi', 'grhr']:
        all_event_types.update(stats_dict[algo_key]['event_stats'].keys())
    all_event_types = sorted(list(all_event_types))
    
    # 映射事件類型到友好名稱
    event_name_map = {
        'gateway_update': 'Gateway\nUpdate',
        'topology_change': 'Topology\nChange',
        'gid_rebuild': 'GID\nRebuild',
        'pid_rebuild': 'PID\nRebuild',
        'routing_update': 'Routing\nUpdate'
    }
    
    x = np.arange(len(all_event_types))
    width = 0.25  # 三個算法，每個寬度 0.25
    
    # 為每個算法準備數據
    for idx, (algo_name, algo_key, color) in enumerate([
        ('Baseline', 'baseline', colors[0]),
        ('LoHi', 'lohi', colors[1]),
        ('GRHR (K=4)', 'grhr', colors[2])
    ]):
        counts = []
        has_data_flags = []
        
        for event_type in all_event_types:
            count = stats_dict[algo_key]['event_stats'].get(event_type, 0)
            counts.append(count)
            has_data_flags.append(event_type in stats_dict[algo_key]['event_stats'])
        
        offset = (idx - 1) * width  # -1, 0, 1
        bars = ax2.bar(x + offset, counts, width,
                      label=algo_name,
                      color=color,
                      alpha=0.85,
                      edgecolor='black',
                      linewidth=0.5)
        
        # 添加數值標籤
        for bar, count, has_data in zip(bars, counts, has_data_flags):
            if count > 0:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(count)}',
                        ha='center', va='bottom', fontsize=9, fontweight='bold')
            elif not has_data:
                # N/A
                y_max = ax2.get_ylim()[1] if ax2.get_ylim()[1] > 0 else 100
                ax2.text(bar.get_x() + bar.get_width()/2., y_max * 0.02,
                        'N/A',
                        ha='center', va='bottom', fontsize=8,
                        color='gray', style='italic')
    
    ax2.set_ylabel('Event Count', fontsize=13, fontweight='bold')
    ax2.set_title('Event Count Comparison by Type', fontsize=15, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels([event_name_map.get(et, et) for et in all_event_types], 
                        rotation=0, ha='center', fontsize=11)
    ax2.legend(fontsize=10, framealpha=0.9, loc='upper left')
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    
    # 保存圖表
    output_file = OUTPUT_DIR / f'multi_algorithm_comparison_{scenario}.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ Chart generated: {output_file}")
    
    return {
        'control_events': [stats_dict['baseline']['control_events'],
                          stats_dict['lohi']['control_events'],
                          stats_dict['grhr']['control_events']],
        'control_signaling_mb': control_signaling_mb
    }

def generate_timeline_chart(scenario, stats_dict):
    """生成單一場景的時間軸折線圖（已棄用，改用 generate_failure_rate_trend）"""
    pass

def generate_failure_rate_trend(results):
    """生成失效率趨勢圖：三個演算法在不同失效率下的控制信令開銷"""
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # 準備數據
    failure_rates = [1, 5, 10]  # 失效率百分比
    algorithms = [
        ('Baseline', 'coral'),
        ('LoHi', 'mediumpurple'),
        ('GRHR (K=4)', '#228B22')
    ]
    
    # 為每個演算法畫一條線
    for algo_idx, (algo_name, color) in enumerate(algorithms):
        signaling_values = []
        for scenario in ['p1', 'p5', 'p10']:
            signaling_mb = results[scenario]['control_signaling_mb'][algo_idx]
            signaling_values.append(signaling_mb)
        
        ax.plot(failure_rates, signaling_values, 
               marker='o', markersize=10, linewidth=2.5,
               label=algo_name, color=color, alpha=0.85)
        
        # 添加數值標籤，偏移避免重疊
        # Baseline 和 LoHi 標籤在上方，GRHR 標籤在下方
        if algo_idx == 0:  # Baseline
            offset = 12
            va = 'bottom'
        elif algo_idx == 1:  # LoHi
            offset = 12
            va = 'bottom'
        else:  # GRHR
            offset = -12
            va = 'top'
        
        for x, y in zip(failure_rates, signaling_values):
            ax.annotate(f'{y:.2f}', 
                       xy=(x, y),
                       xytext=(0, offset),
                       textcoords='offset points',
                       ha='center', va=va,
                       fontsize=9, fontweight='bold',
                       color=color,
                       bbox=dict(boxstyle='round,pad=0.3', 
                                facecolor='white', 
                                edgecolor=color, 
                                alpha=0.8))
    
    ax.set_title('Control Signaling Overhead', 
                fontsize=15, fontweight='bold')
    ax.set_xlabel('ISL Failure Rate (%)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Total Control Signaling (MB)', fontsize=13, fontweight='bold')
    ax.set_xticks(failure_rates)
    ax.set_xticklabels(['1%', '5%', '10%'])
    ax.legend(loc='upper left', fontsize=11, framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    
    output_file = OUTPUT_DIR / 'failure_rate_trend.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"\n✓ Failure rate trend chart generated: {output_file}")

def generate_summary_report(results):
    """生成摘要報告"""
    
    report_file = OUTPUT_DIR / "multi_algorithm_comparison_report.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("Random ISL Failure Scenarios - Algorithm Comparison Report\n")
        f.write("="*80 + "\n\n")
        
        f.write("Algorithms:\n")
        f.write("  - Baseline: Floyd-Warshall Global Routing\n")
        f.write("  - LoHi: Two-Layer Routing (p=6, s=10)\n")
        f.write("  - GRHR: Hierarchical Virtual GID Routing (K=4, 27° Grid)\n\n")
        
        f.write("Note:\n")
        f.write("  - GRHR control signaling excludes routing_update (computed locally)\n")
        f.write("  - LoHi and Baseline include all events\n\n")
        
        for scenario in ['p1', 'p5', 'p10']:
            data = results[scenario]
            f.write(f"\n{SCENARIOS[scenario]['label']}\n")
            f.write("-" * 70 + "\n")
            f.write(f"{'Algorithm':<15} {'Events':<12} {'Control Signaling (MB)':<25}\n")
            f.write("-" * 70 + "\n")
            
            for i, algo in enumerate(['Baseline', 'LoHi', 'GRHR (K=4)']):
                events = data['control_events'][i]
                signaling_mb = data['control_signaling_mb'][i]
                f.write(f"{algo:<15} {events:<12} {signaling_mb:<25.2f}\n")
        
        f.write("\n" + "="*80 + "\n")
    
    print(f"\n✓ Report saved: {report_file}")

def main():
    print("="*80)
    print("Multi-Algorithm Control Signaling Analysis - Random ISL Failures")
    print("="*80)
    
    results = {}
    
    for scenario in ['p1', 'p5', 'p10']:
        print(f"\nProcessing scenario: {scenario}")
        
        # 載入各演算法數據
        baseline_file = DATA_DIR / f"baseline_random_{scenario}_signaling_stats.json"
        lohi_file = DATA_DIR / f"lohi_random_{scenario}_signaling_stats.json"
        grhr_file = DATA_DIR / f"hierarchical_gid_27deg_random_{scenario}_k4_signaling_stats.json"
        
        if not all([baseline_file.exists(), lohi_file.exists(), grhr_file.exists()]):
            print(f"  ✗ Missing data files")
            continue
        
        stats_dict = {
            'baseline': load_stats(baseline_file, algorithm_type='baseline'),
            'lohi': load_stats(lohi_file, algorithm_type='lohi'),
            'grhr': load_stats(grhr_file, algorithm_type='grhr')
        }
        
        # 生成圖表
        results[scenario] = generate_comparison_chart(scenario, stats_dict)
    
    # 生成失效率趨勢圖
    generate_failure_rate_trend(results)
    
    # 生成報告
    print("\n" + "="*80)
    print("Generating summary report...")
    generate_summary_report(results)
    
    print("\n" + "="*80)
    print("✓ Analysis complete")
    print("="*80)
    print(f"\nOutput directory: {OUTPUT_DIR}/")
    print("  - multi_algorithm_comparison_p1.png")
    print("  - multi_algorithm_comparison_p5.png")
    print("  - multi_algorithm_comparison_p10.png")
    print("  - failure_rate_trend.png")
    print("  - multi_algorithm_comparison_report.txt")

if __name__ == "__main__":
    main()
