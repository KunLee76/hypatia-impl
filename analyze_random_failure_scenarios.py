#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分析隨機 ISL 失效場景的控制信令統計

用途：
  1. 讀取所有隨機失效場景的統計數據
  2. 生成 K 值比較圖表（每個失效率一張圖）
  3. 生成報告文件
  4. 生成折線圖比較不同失效率

執行方式：
  python analyze_random_failure_scenarios.py
"""

import json
import os
import sys
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from collections import defaultdict
from datetime import datetime

# 使用非交互式後端
matplotlib.use('Agg')

# 支援中文顯示
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans']
plt.rcParams['axes.unicode_minus'] = False

# 工作目錄
WORK_DIR = "paper/satellite_networks_state"
ANALYTIC_DIR = os.path.join(WORK_DIR, "analytic_result")
OUTPUT_DIR = "random_failure_analysis"  # 動態失效場景專用目錄

# 場景定義
SCENARIOS = ["p1", "p5", "p10"]
SCENARIO_LABELS = {
    "p1": "Random 1% ISL Failure",
    "p5": "Random 5% ISL Failure",
    "p10": "Random 10% ISL Failure"
}
K_VALUES = [1, 2, 4, 6, 8, 999]


def load_stats(scenario, k):
    """載入指定場景和 K 值的統計數據"""
    filename = f"hierarchical_gid_27deg_random_{scenario}_k{k}_signaling_stats.json"
    filepath = os.path.join(ANALYTIC_DIR, filename)
    
    if not os.path.exists(filepath):
        print(f"  ⚠ 文件不存在: {filepath}")
        return None
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"  ✗ 讀取失敗 {filepath}: {e}")
        return None


def extract_metrics(stats_data):
    """從統計數據中提取關鍵指標"""
    if not stats_data:
        return None
    
    # 檢查是否為新格式（summary.by_type）
    if 'summary' in stats_data:
        summary = stats_data['summary']
        
        # 新格式：從 summary 中提取
        total_messages = summary.get('total_events', 0)
        total_bytes = summary.get('total_bytes', 0)
        
        # 從 by_type 提取各類事件
        by_type = summary.get('by_type', {})
        if by_type:
            # 新格式：使用 by_type 結構
            routing_updates = by_type.get('routing_update', {}).get('count', 0)
            gateway_updates = by_type.get('gateway_update', {}).get('count', 0)
            gid_rebuilds = by_type.get('gid_rebuild', {}).get('count', 0)
            topology_changes = by_type.get('topology_change', {}).get('count', 0)
        else:
            # event_counts 格式（過渡格式）
            event_counts = summary.get('event_counts', {})
            routing_updates = event_counts.get('routing_update', {}).get('count', 0)
            gateway_updates = event_counts.get('gateway_update', {}).get('count', 0)
            gid_rebuilds = event_counts.get('gid_rebuild', {}).get('count', 0)
            topology_changes = event_counts.get('topology_change', {}).get('count', 0)
    else:
        # 舊格式：從頂層提取
        routing_updates = stats_data.get('routing_updates', 0)
        gateway_updates = stats_data.get('gateway_updates', 0)
        gid_rebuilds = stats_data.get('gid_rebuilds', 0)
        topology_changes = stats_data.get('topology_changes', 0)
        total_messages = stats_data.get('total_messages', 0)
        total_bytes = stats_data.get('total_bytes', 0)
    
    # 從timeline重新計算字節數（使用統一的控制信令模型）
    CTRL_HDR_BYTES = 32
    ROUTE_ENTRY_BYTES = 32
    GATEWAY_ENTRY_BYTES = 32
    ID_ENTRY_BYTES = 32
    
    routing_bytes = 0
    gateway_bytes = 0
    gid_bytes = 0
    
    timeline = stats_data.get('timeline', [])
    for entry in timeline:
        event = entry.get('event') or entry.get('type', '')
        detail = entry.get('detail', {})
        
        if event == 'routing_update':
            changed_entries = detail.get('changed_entries', 0)
            routing_bytes += CTRL_HDR_BYTES + changed_entries * ROUTE_ENTRY_BYTES
        elif event == 'gateway_update':
            num_messages = detail.get('num_messages', 0)
            num_entries = detail.get('num_entries', 0)
            if num_messages == 0 and num_entries == 0:
                # 从changed_pairs和k计算
                changed_pairs = detail.get('changed_pairs', 0)
                k = detail.get('k', 0) or detail.get('k_used', 0)
                num_messages = changed_pairs
                num_entries = changed_pairs * max(k, 1)
            gateway_bytes += num_messages * CTRL_HDR_BYTES + num_entries * GATEWAY_ENTRY_BYTES
        elif event == 'gid_rebuild':
            changed_gids = detail.get('changed_gids', 0)
            gid_bytes += CTRL_HDR_BYTES + changed_gids * ID_ENTRY_BYTES
    
    # 如果total_bytes为0，使用计算值
    if total_bytes == 0:
        total_bytes = routing_bytes + gateway_bytes + gid_bytes
    
    return {
        'routing_updates': routing_updates,
        'gateway_updates': gateway_updates,
        'gid_rebuilds': gid_rebuilds,
        'topology_changes': topology_changes,
        'total_messages': total_messages,
        'total_bytes': total_bytes,
        'total_bytes_mb': total_bytes / (1024 * 1024),
        'routing_bytes': routing_bytes,
        'gateway_bytes': gateway_bytes,
        'gid_bytes': gid_bytes
    }


def plot_k_comparison(scenario, data_by_k, output_file):
    """生成 K 值比較圖表（參考 analyze_failure_scenarios.py 的格式）"""
    
    # 準備數據
    k_labels = [f"K={k}" if k != 999 else "K=All" for k in K_VALUES]
    
    # 創建 2x2 子圖
    fig = plt.figure(figsize=(18, 14))
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
    
    # 使用不同的顏色（參考之前的配色）
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(K_VALUES)))
    
    # === 子圖1：總控制信令開銷（字節） ===
    ax1 = fig.add_subplot(gs[0, 0])
    total_bytes = [data_by_k[k]['total_bytes'] / 1e6 if k in data_by_k else 0 for k in K_VALUES]
    bars1 = ax1.bar(k_labels, total_bytes, color=colors, alpha=0.85, edgecolor='black', linewidth=0.5)
    ax1.set_ylabel('Total Signaling (MB)', fontsize=12, fontweight='bold')
    ax1.set_title(f'Total Control Signaling\n({SCENARIO_LABELS[scenario]})', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax1.tick_params(axis='x', rotation=0, labelsize=10)
    
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.1f}',
               ha='center', va='bottom', fontsize=9)
    
    # === 子圖2：事件類型分佈 ===
    ax2 = fig.add_subplot(gs[0, 1])
    event_types = ['gateway_updates', 'routing_updates', 'gid_rebuilds']
    event_labels = ['Gateway', 'Routing', 'GID']
    event_colors = ['orange', 'skyblue', 'lightgreen']
    
    x = np.arange(len(k_labels))
    width = 0.25
    
    for i, (event_type, event_label, event_color) in enumerate(zip(event_types, event_labels, event_colors)):
        counts = [data_by_k[k][event_type] if k in data_by_k else 0 for k in K_VALUES]
        offset = (i - 1) * width
        bars = ax2.bar(x + offset, counts, width, label=event_label, 
                     color=event_color, alpha=0.85, edgecolor='black', linewidth=0.5)
        
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}',
                       ha='center', va='bottom', fontsize=7)
    
    ax2.set_ylabel('Event Count', fontsize=12, fontweight='bold')
    ax2.set_title(f'Event Type Distribution\n({SCENARIO_LABELS[scenario]})', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(k_labels, rotation=0, ha='center', fontsize=10)
    ax2.legend(fontsize=10, framealpha=0.9)
    ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
    
    # === 子圖3：Gateway 更新開銷 ===
    ax3 = fig.add_subplot(gs[1, 0])
    gateway_bytes = [data_by_k[k]['gateway_bytes'] / 1e6 if k in data_by_k else 0 for k in K_VALUES]
    bars3 = ax3.bar(k_labels, gateway_bytes, color='darkorange', alpha=0.85, edgecolor='black', linewidth=0.5)
    ax3.set_ylabel('Gateway Update Signaling (MB)', fontsize=12, fontweight='bold')
    ax3.set_title(f'Gateway Update Overhead\n({SCENARIO_LABELS[scenario]})', fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax3.tick_params(axis='x', rotation=0, labelsize=10)
    
    for bar in bars3:
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.2f}',
               ha='center', va='bottom', fontsize=9)
    
    # === 子圖4：相對於 K=1 的變化百分比 ===
    ax4 = fig.add_subplot(gs[1, 1])
    baseline_bytes = data_by_k[1]['total_bytes'] if 1 in data_by_k else 0
    if baseline_bytes > 0:
        increases = [((data_by_k[k]['total_bytes'] - baseline_bytes) / baseline_bytes) * 100 
                    if k in data_by_k else 0 for k in K_VALUES]
    else:
        increases = [0] * len(K_VALUES)
    
    bar_colors = ['green' if x <= 0 else 'skyblue' for x in increases]
    bars4 = ax4.bar(k_labels, increases, color=bar_colors, alpha=0.85, edgecolor='black', linewidth=0.5)
    ax4.set_ylabel('Change vs K=1 (%)', fontsize=12, fontweight='bold')
    ax4.set_title(f'Overhead Change Relative to K=1\n({SCENARIO_LABELS[scenario]})', fontsize=14, fontweight='bold')
    ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    ax4.grid(True, alpha=0.3, axis='y', linestyle='--')
    ax4.tick_params(axis='x', rotation=0, labelsize=10)
    
    for bar in bars4:
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.1f}%',
               ha='center', va='bottom' if height > 0 else 'top', fontsize=9)
    
    plt.suptitle(f'K Parameter Comparison: {SCENARIO_LABELS[scenario]}', 
                fontsize=16, fontweight='bold', y=0.995)
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ 圖表已生成: {output_file}")


def plot_failure_rate_comparison(all_data, output_file):
    """繪製折線圖：不同失效率在不同 K 值下的控制信令變化"""
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Control Signaling vs K Parameter (Different Failure Rates)', 
                 fontsize=16, fontweight='bold')
    
    k_labels = [f"K={k}" if k != 999 else "K=All" for k in K_VALUES]
    x_pos = np.arange(len(K_VALUES))
    
    # 線條樣式和顏色
    line_styles = ['-', '--', '-.']
    line_colors = ['#e74c3c', '#3498db', '#2ecc71']
    markers = ['o', 's', '^']
    
    metrics_to_plot = [
        ('total_messages', 'Total Messages', 'Count'),
        ('gateway_updates', 'Gateway Updates', 'Count'),
        ('routing_updates', 'Routing Updates', 'Count'),
        ('total_bytes_mb', 'Total Bytes', 'MB')
    ]
    
    axes = axes.flatten()
    
    for idx, (metric_key, metric_label, unit) in enumerate(metrics_to_plot):
        ax = axes[idx]
        
        for scenario_idx, scenario in enumerate(SCENARIOS):
            if scenario not in all_data:
                continue
            
            values = [all_data[scenario][k][metric_key] if k in all_data[scenario] else 0 
                     for k in K_VALUES]
            
            ax.plot(x_pos, values, 
                   label=SCENARIO_LABELS[scenario],
                   linestyle=line_styles[scenario_idx],
                   color=line_colors[scenario_idx],
                   marker=markers[scenario_idx],
                   markersize=8,
                   linewidth=2.5,
                   alpha=0.9)
            
            # 標記 K=1 和 K=All 的值
            if len(values) >= 2:
                ax.text(0, values[0], f'{values[0]:.0f}', 
                       fontsize=8, ha='right', va='center')
                ax.text(len(K_VALUES)-1, values[-1], f'{values[-1]:.0f}', 
                       fontsize=8, ha='left', va='center')
        
        ax.set_ylabel(f'{metric_label} ({unit})', fontsize=11, fontweight='bold')
        ax.set_xlabel('K Value', fontsize=11, fontweight='bold')
        ax.set_title(metric_label, fontsize=12, fontweight='bold')
        ax.set_xticks(x_pos)
        ax.set_xticklabels(k_labels, rotation=0, fontsize=9)
        ax.legend(fontsize=9, framealpha=0.9, loc='best')
        ax.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ 折線圖已生成: {output_file}")


def generate_report(all_data, report_path):
    """生成綜合報告文件"""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("隨機 ISL 失效場景控制信令比較報告\n")
        f.write("="*80 + "\n")
        f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"實驗配置：Grid Degree = 27°, 模擬時長 = 20 秒\n")
        f.write(f"測試場景：{', '.join(SCENARIOS)}\n")
        f.write(f"測試 K 值：{', '.join(map(str, K_VALUES))}\n\n")
        
        # 按 K 值分組報告
        for k in K_VALUES:
            k_str = "All" if k == 999 else str(k)
            f.write(f"\n{'='*80}\n")
            f.write(f"K = {k_str}\n")
            f.write(f"{'='*80}\n\n")
            
            # 總體統計
            f.write("總體控制信令開銷：\n")
            f.write("-"*80 + "\n")
            f.write(f"{'場景':<25} {'總事件數':<12} {'總字節數':<15} {'平均事件開銷':<15}\n")
            f.write("-"*80 + "\n")
            
            for scenario in SCENARIOS:
                if scenario in all_data and k in all_data[scenario]:
                    metrics = all_data[scenario][k]
                    total_events = metrics['total_messages']
                    total_bytes = metrics['total_bytes']
                    avg_bytes = total_bytes / total_events if total_events > 0 else 0
                    
                    scenario_label = SCENARIO_LABELS[scenario]
                    f.write(f"{scenario_label:<25} {total_events:<12} {total_bytes:<15,} {avg_bytes:<15.1f}\n")
            
            # 按事件類型詳細統計
            f.write("\n\n按事件類型統計：\n")
            f.write("-"*80 + "\n")
            
            # Gateway Updates
            f.write("\nGateway 更新：\n")
            f.write(f"{'場景':<25} {'次數':<12} {'總字節數':<15} {'平均大小':<15}\n")
            f.write("-"*80 + "\n")
            for scenario in SCENARIOS:
                if scenario in all_data and k in all_data[scenario]:
                    metrics = all_data[scenario][k]
                    count = metrics['gateway_updates']
                    bytes_val = metrics['gateway_bytes']
                    avg = bytes_val / count if count > 0 else 0
                    scenario_label = SCENARIO_LABELS[scenario]
                    f.write(f"{scenario_label:<25} {count:<12} {bytes_val:<15,} {avg:<15.1f}\n")
            
            # Routing Updates
            f.write("\nRouting 更新：\n")
            f.write(f"{'場景':<25} {'次數':<12} {'總字節數':<15} {'平均大小':<15}\n")
            f.write("-"*80 + "\n")
            for scenario in SCENARIOS:
                if scenario in all_data and k in all_data[scenario]:
                    metrics = all_data[scenario][k]
                    count = metrics['routing_updates']
                    bytes_val = metrics['routing_bytes']
                    avg = bytes_val / count if count > 0 else 0
                    scenario_label = SCENARIO_LABELS[scenario]
                    f.write(f"{scenario_label:<25} {count:<12} {bytes_val:<15,} {avg:<15.1f}\n")
            
            # GID Rebuilds
            f.write("\nGID 重建：\n")
            f.write(f"{'場景':<25} {'次數':<12} {'總字節數':<15} {'平均大小':<15}\n")
            f.write("-"*80 + "\n")
            for scenario in SCENARIOS:
                if scenario in all_data and k in all_data[scenario]:
                    metrics = all_data[scenario][k]
                    count = metrics['gid_rebuilds']
                    bytes_val = metrics['gid_bytes']
                    avg = bytes_val / count if count > 0 else 0
                    scenario_label = SCENARIO_LABELS[scenario]
                    f.write(f"{scenario_label:<25} {count:<12} {bytes_val:<15,} {avg:<15.1f}\n")
    
    print(f"✓ 報告已保存：{report_path}")


def generate_summary_table(all_data):
    """生成摘要表格"""
    print("\n" + "="*80)
    print("隨機 ISL 失效場景控制信令統計摘要")
    print("="*80)
    
    for scenario in SCENARIOS:
        print(f"\n{SCENARIO_LABELS[scenario]}:")
        print("-" * 80)
        print(f"{'K Value':<10} {'Routing':<12} {'Gateway':<12} {'Total Msg':<12} {'Total MB':<12} {'vs K=1':<10}")
        print("-" * 80)
        
        if scenario not in all_data:
            print("  無數據")
            continue
        
        k1_total = None
        for k in K_VALUES:
            if k not in all_data[scenario] or not all_data[scenario][k]:
                print(f"{'K=' + str(k):<10} {'N/A':<12} {'N/A':<12} {'N/A':<12} {'N/A':<12} {'N/A':<10}")
                continue
            
            data = all_data[scenario][k]
            
            k_label = f"K={k}" if k != 999 else "K=All"
            
            # 計算與 K=1 的差異
            if k == 1:
                k1_total = data['total_messages']
                vs_k1 = "-"
            elif k1_total and k1_total > 0:
                reduction = (k1_total - data['total_messages']) / k1_total * 100
                vs_k1 = f"{reduction:+.1f}%"
            else:
                vs_k1 = "N/A"
            
            print(f"{k_label:<10} "
                  f"{data['routing_updates']:<12} "
                  f"{data['gateway_updates']:<12} "
                  f"{data['total_messages']:<12} "
                  f"{data['total_bytes_mb']:<12.2f} "
                  f"{vs_k1:<10}")


def main():
    print("="*80)
    print("分析隨機 ISL 失效場景控制信令統計")
    print("="*80)
    print()
    
    # 創建輸出目錄
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 載入所有數據
    print("步驟 1: 載入統計數據")
    print("-" * 80)
    
    all_data = {}
    
    for scenario in SCENARIOS:
        print(f"\n載入場景: {scenario}")
        all_data[scenario] = {}
        
        for k in K_VALUES:
            print(f"  K={k}...", end=" ")
            stats = load_stats(scenario, k)
            if stats:
                metrics = extract_metrics(stats)
                all_data[scenario][k] = metrics
                print("✓")
            else:
                print("✗")
    
    # 生成 K 值比較圖表
    print("\n" + "="*80)
    print("步驟 2: 生成 K 值比較圖表")
    print("-" * 80)
    
    for scenario in SCENARIOS:
        print(f"\n生成場景 {scenario} 的圖表...")
        output_file = os.path.join(OUTPUT_DIR, f"k_comparison_random_{scenario}.png")
        
        if scenario in all_data and all_data[scenario]:
            plot_k_comparison(scenario, all_data[scenario], output_file)
        else:
            print(f"  ⚠ 場景 {scenario} 無數據，跳過")
    
    # 生成折線圖
    print("\n" + "="*80)
    print("步驟 3: 生成失效率比較折線圖")
    print("-" * 80)
    
    line_chart_file = os.path.join(OUTPUT_DIR, "failure_rate_comparison_line_chart.png")
    plot_failure_rate_comparison(all_data, line_chart_file)
    
    # 生成報告
    print("\n" + "="*80)
    print("步驟 4: 生成報告文件")
    print("-" * 80)
    
    report_file = os.path.join(OUTPUT_DIR, "random_failure_scenarios_comparison_report.txt")
    generate_report(all_data, report_file)
    
    # 生成摘要表格
    generate_summary_table(all_data)
    
    print("\n" + "="*80)
    print("✓ 分析完成")
    print("="*80)
    print("\n輸出文件:")
    print(f"  - 圖表目錄: {OUTPUT_DIR}/")
    for scenario in SCENARIOS:
        print(f"    - k_comparison_random_{scenario}.png")
    print(f"    - failure_rate_comparison_line_chart.png")
    print(f"    - random_failure_scenarios_comparison_report.txt")


if __name__ == "__main__":
    main()
