#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
演算法比較分析：GRHR (K=4, K=8) vs LoHi vs Baseline

用途：
  1. 讀取 GRHR (K=4, K=8)、LoHi、Baseline 的動態失效場景統計數據
  2. 生成演算法性能比較圖表（每個失效率 P1/P5/P10 一張圖）
  3. 生成報告文件

執行方式：
  python analyze_algorithm_comparison_dynamic.py
"""

import json
import os
import sys
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# 使用非交互式後端
matplotlib.use('Agg')

# 支援中文顯示
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans']
plt.rcParams['axes.unicode_minus'] = False

# 工作目錄
ANALYTIC_DIR = "paper/satellite_networks_state/analytic_result"
OUTPUT_DIR = "algorithm_comparison_analysis"

# 場景定義
SCENARIOS = ["p1", "p5", "p10"]
SCENARIO_LABELS = {
    "p1": "Dynamic 1% ISL Failure (Chaos Monkey)",
    "p5": "Dynamic 5% ISL Failure (Chaos Monkey)",
    "p10": "Dynamic 10% ISL Failure (Chaos Monkey)"
}

# 演算法定義（比較對象）
ALGORITHMS = ["grhr_k4", "lohi", "baseline"]
ALGORITHM_LABELS = {
    "grhr_k4": "GRHR (K=4)",
    "lohi": "LoHi (p=6, s=10)",
    "baseline": "Baseline (F-W)"
}
# 使用 viridis 配色
ALGORITHM_COLORS = {
    "grhr_k4": "#2c7fb8",   # 藍色
    "lohi": "#a1dab4",      # 綠色
    "baseline": "#ffffcc"   # 黃色
}

# TLV 控制訊息格式常數
CTRL_HDR_BYTES = 32          # 控制訊息標頭
ROUTE_ENTRY_BYTES = 32       # 路由表項
PHYS_TOPO_ENTRY_BYTES = 32   # 物理拓撲項
GROUP_TOPO_ENTRY_BYTES = 32  # 群組拓撲項
ID_ENTRY_BYTES = 32          # ID 映射項
GATEWAY_ENTRY_BYTES = 32     # 閘道項


def calculate_event_bytes(event, is_lohi=False):
    """根據事件類型和detail計算字節數"""
    ev_type = event.get('event') or event.get('type')
    if not ev_type:
        return 0
    
    detail = event.get('detail') or {}
    msg_count = int(event.get('count', 1) or 1)
    
    # 推斷條目數
    n_entries = 0
    
    if ev_type == 'routing_update':
        n_entries = int(detail.get('changed_entries', 0) or 0)
        entry_bytes = ROUTE_ENTRY_BYTES
        return CTRL_HDR_BYTES + n_entries * entry_bytes
        
    elif ev_type == 'topology_change':
        if 'delta_group_edges' in detail:
            n_entries = abs(int(detail.get('delta_group_edges', 0) or 0))
            entry_bytes = GROUP_TOPO_ENTRY_BYTES if is_lohi else PHYS_TOPO_ENTRY_BYTES
        else:
            n_entries = abs(int(detail.get('delta_isl', 0) or 0)) + abs(int(detail.get('delta_gsl', 0) or 0))
            if n_entries == 0 and 'delta_edges' in detail:
                n_entries = abs(int(detail.get('delta_edges', 0) or 0))
            entry_bytes = PHYS_TOPO_ENTRY_BYTES
        return CTRL_HDR_BYTES + n_entries * entry_bytes
        
    elif ev_type == 'gid_rebuild':
        n_entries = int(detail.get('changed_gids', 0) or 0)
        return CTRL_HDR_BYTES + n_entries * ID_ENTRY_BYTES
        
    elif ev_type == 'pid_rebuild':
        n_entries = int(detail.get('changed_pids', 0) or 0)
        return CTRL_HDR_BYTES + n_entries * ID_ENTRY_BYTES
        
    elif ev_type == 'gateway_update':
        # 特殊處理：每對 GID 一個訊息
        n_msgs = int(detail.get('num_messages', 0) or 0)
        n_entries = int(detail.get('num_entries', 0) or 0)
        
        if n_msgs == 0 and n_entries == 0:
            changed_pairs = int(detail.get('changed_pairs', 0) or 0)
            k = int(detail.get('k', 0) or detail.get('k_used', 0) or 0)
            n_msgs = changed_pairs
            n_entries = changed_pairs * max(k, 1)
        
        return n_msgs * CTRL_HDR_BYTES + n_entries * GATEWAY_ENTRY_BYTES
    
    # 未知事件類型：返回原始bytes
    return int(event.get('bytes', 0) or 0)


def calculate_total_bytes(data, algo):
    """重新計算所有事件的總字節數"""
    timeline = data.get('timeline', [])
    if not timeline:
        return 0
    
    is_lohi = 'lohi' in algo.lower()
    total = 0
    
    for event in timeline:
        total += calculate_event_bytes(event, is_lohi)
    
    return total


def load_stats(algo, scenario):
    """載入指定演算法和場景的統計數據"""
    
    # 根據演算法類型決定檔案名
    if algo == "grhr_k4":
        filename = f"hierarchical_gid_27deg_dynamic_{scenario}_k4_signaling_stats.json"
    elif algo == "grhr_k8":
        filename = f"hierarchical_gid_27deg_dynamic_{scenario}_k8_signaling_stats.json"
    elif algo == "lohi":
        filename = f"lohi_dynamic_{scenario}_signaling_stats.json"
    elif algo == "baseline":
        filename = f"baseline_dynamic_{scenario}_signaling_stats.json"
    else:
        print(f"  ⚠️  未知演算法：{algo}")
        return None
    
    filepath = os.path.join(ANALYTIC_DIR, filename)
    
    if not os.path.exists(filepath):
        print(f"  ⚠️  警告：統計文件不存在 - {filename}")
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"  ✗ 讀取失敗：{filename} - {e}")
        return None


def extract_signaling_stats(data, algo):
    """提取控制信令統計數據（不同演算法可能有不同欄位名）"""
    if not data:
        return None
    
    # 統一欄位名對應
    stats = {}
    
    # 檢查數據格式：GRHR有頂層統計欄位，LoHi/Baseline使用summary.by_type
    has_top_level_stats = 'routing_updates' in data or 'total_messages' in data
    has_summary = 'summary' in data and 'by_type' in data.get('summary', {})
    
    if has_top_level_stats:
        # GRHR 格式：頂層統計欄位
        stats['routing_updates'] = data.get('routing_updates', 0)
        stats['gateway_updates'] = data.get('gateway_updates', 0)
        stats['gid_rebuilds'] = data.get('gid_rebuilds', 0)
        stats['topology_changes'] = data.get('topology_changes', 0)
        stats['total_messages'] = data.get('total_messages', 0)
        # 不使用原始bytes，重新計算
        stats['total_bytes'] = calculate_total_bytes(data, algo)
    elif has_summary:
        # LoHi/Baseline 格式：summary.by_type
        by_type = data['summary']['by_type']
        stats['routing_updates'] = by_type.get('routing_update', {}).get('count', 0)
        stats['gateway_updates'] = by_type.get('gateway_update', {}).get('count', 0)
        stats['gid_rebuilds'] = by_type.get('gid_rebuild', {}).get('count', 0)
        stats['topology_changes'] = by_type.get('topology_change', {}).get('count', 0)
        stats['total_messages'] = data['summary'].get('total_events', 0)
        # 不使用原始bytes，重新計算
        stats['total_bytes'] = calculate_total_bytes(data, algo)
    else:
        # 降級處理：嘗試從任何可用欄位中提取
        stats['routing_updates'] = data.get('total_routing_updates', 0)
        stats['gateway_updates'] = 0
        stats['gid_rebuilds'] = 0
        stats['topology_changes'] = data.get('total_topology_changes', 0)
        stats['total_messages'] = data.get('total_events', 0)
        stats['total_bytes'] = calculate_total_bytes(data, algo)
    
    # 時間軸事件數
    stats['timeline_events'] = len(data.get('timeline', []))
    
    return stats


def load_all_data():
    """載入所有演算法和場景的統計數據"""
    print("=" * 70)
    print("載入演算法比較數據")
    print("=" * 70)
    
    results = {}
    
    for scenario in SCENARIOS:
        print(f"\n場景：{SCENARIO_LABELS[scenario]}")
        results[scenario] = {}
        
        for algo in ALGORITHMS:
            print(f"  {ALGORITHM_LABELS[algo]:20s} ... ", end='')
            data = load_stats(algo, scenario)
            
            if data:
                stats = extract_signaling_stats(data, algo)
                results[scenario][algo] = stats
                print(f"✓ (訊息: {stats['total_messages']}, 字節: {stats['total_bytes']})")
            else:
                results[scenario][algo] = None
                print("✗ 無數據")
    
    print("\n" + "=" * 70)
    return results


def plot_algorithm_comparison_by_scenario(results):
    """為每個失效率場景生成演算法比較圖"""
    print("\n生成演算法比較圖表...")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for scenario in SCENARIOS:
        print(f"  繪製場景：{scenario.upper()} ... ", end='')
        
        # 提取數據
        algo_list = []
        algo_labels = []
        routing_updates = []
        gateway_updates = []
        total_messages = []
        total_bytes = []
        
        for algo in ALGORITHMS:
            if results[scenario][algo]:
                algo_list.append(algo)
                algo_labels.append(ALGORITHM_LABELS[algo])
                stats = results[scenario][algo]
                routing_updates.append(stats['routing_updates'])
                gateway_updates.append(stats['gateway_updates'])
                total_messages.append(stats['total_messages'])
                total_bytes.append(stats['total_bytes'])
        
        if not algo_list:
            print("無數據")
            continue
        
        # 創建圖表（2x3 布局）
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        fig.suptitle(f'{SCENARIO_LABELS[scenario]}\nAlgorithm Comparison', 
                     fontsize=14, fontweight='bold')
        
        x_pos = range(len(algo_list))
        colors = [ALGORITHM_COLORS[a] for a in algo_list]
        
        # 路由更新
        bars1 = axes[0, 0].bar(x_pos, routing_updates, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[0, 0].set_title('Routing Updates', fontsize=12, fontweight='bold')
        axes[0, 0].set_xlabel('Algorithm')
        axes[0, 0].set_ylabel('Count')
        axes[0, 0].set_xticks(x_pos)
        axes[0, 0].set_xticklabels(algo_labels, rotation=15, ha='right')
        axes[0, 0].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars1:
            height = bar.get_height()
            axes[0, 0].text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height):,}', ha='center', va='bottom', fontsize=9)
        
        # 網關更新（只有 GRHR 有值）
        bars2 = axes[0, 1].bar(x_pos, gateway_updates, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[0, 1].set_title('Gateway Updates (GRHR only)', fontsize=12, fontweight='bold')
        axes[0, 1].set_xlabel('Algorithm')
        axes[0, 1].set_ylabel('Count')
        axes[0, 1].set_xticks(x_pos)
        axes[0, 1].set_xticklabels(algo_labels, rotation=15, ha='right')
        axes[0, 1].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars2:
            height = bar.get_height()
            if height > 0:
                axes[0, 1].text(bar.get_x() + bar.get_width()/2., height,
                              f'{int(height):,}', ha='center', va='bottom', fontsize=9)
        
        # 總訊息數（Count）
        bars3 = axes[0, 2].bar(x_pos, total_messages, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[0, 2].set_title('Total Messages (Count)', fontsize=12, fontweight='bold')
        axes[0, 2].set_xlabel('Algorithm')
        axes[0, 2].set_ylabel('Count')
        axes[0, 2].set_xticks(x_pos)
        axes[0, 2].set_xticklabels(algo_labels, rotation=15, ha='right')
        axes[0, 2].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars3:
            height = bar.get_height()
            axes[0, 2].text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height):,}', ha='center', va='bottom', fontsize=9)
        
        # 總流量（Bytes）- 自動選擇單位
        max_bytes = max(total_bytes) if total_bytes else 0
        if max_bytes > 1024 * 1024:  # > 1MB
            total_bytes_display = [b / (1024 * 1024) for b in total_bytes]
            unit = 'MB'
            decimal_places = 2
        elif max_bytes > 1024:  # > 1KB
            total_bytes_display = [b / 1024 for b in total_bytes]
            unit = 'KB'
            decimal_places = 1
        else:
            total_bytes_display = total_bytes
            unit = 'Bytes'
            decimal_places = 0
        
        bars4 = axes[1, 0].bar(x_pos, total_bytes_display, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[1, 0].set_title(f'Total Signaling Traffic ({unit})', fontsize=12, fontweight='bold')
        axes[1, 0].set_xlabel('Algorithm')
        axes[1, 0].set_ylabel(unit)
        axes[1, 0].set_xticks(x_pos)
        axes[1, 0].set_xticklabels(algo_labels, rotation=15, ha='right')
        axes[1, 0].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars4:
            height = bar.get_height()
            if decimal_places == 0:
                axes[1, 0].text(bar.get_x() + bar.get_width()/2., height,
                              f'{int(height):,}', ha='center', va='bottom', fontsize=9)
            else:
                axes[1, 0].text(bar.get_x() + bar.get_width()/2., height,
                              f'{height:,.{decimal_places}f}', ha='center', va='bottom', fontsize=9)
        
        # 隱藏未使用的子圖
        axes[1, 1].axis('off')
        axes[1, 2].axis('off')
        
        plt.tight_layout()
        
        # 保存圖表
        output_file = os.path.join(OUTPUT_DIR, f'algorithm_comparison_dynamic_{scenario}.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 已保存：{output_file}")


def plot_cross_scenario_comparison(results):
    """跨失效率場景比較（固定演算法，比較不同失效率）"""
    print("\n生成跨場景比較圖表...")
    
    # 為每個演算法生成一張圖
    for algo in ALGORITHMS:
        print(f"  {ALGORITHM_LABELS[algo]} ... ", end='')
        
        # 提取數據
        scenario_labels = []
        routing_updates = []
        total_messages = []
        total_bytes = []
        
        for scenario in SCENARIOS:
            if results[scenario][algo]:
                scenario_labels.append(scenario.upper())
                stats = results[scenario][algo]
                routing_updates.append(stats['routing_updates'])
                total_messages.append(stats['total_messages'])
                total_bytes.append(stats['total_bytes'])
        
        if not scenario_labels:
            print("無數據")
            continue
        
        # 創建圖表
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        fig.suptitle(f'{ALGORITHM_LABELS[algo]} - Cross Scenario Comparison', 
                     fontsize=14, fontweight='bold')
        
        x_pos = range(len(scenario_labels))
        
        # 使用漸變色
        colors = ['#3498db', '#e74c3c', '#9b59b6']  # P1=藍, P5=紅, P10=紫
        
        # 路由更新
        bars1 = axes[0].bar(x_pos, routing_updates, color=colors, 
                           alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[0].set_title('Routing Updates', fontsize=12, fontweight='bold')
        axes[0].set_xlabel('Failure Rate')
        axes[0].set_ylabel('Count')
        axes[0].set_xticks(x_pos)
        axes[0].set_xticklabels(scenario_labels)
        axes[0].grid(True, alpha=0.3, axis='y', linestyle='--')
        for bar in bars1:
            height = bar.get_height()
            axes[0].text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height):,}', ha='center', va='bottom', fontsize=9)
        
        # 總訊息數
        bars2 = axes[1].bar(x_pos, total_messages, color=colors, 
                           alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[1].set_title('Total Messages', fontsize=12, fontweight='bold')
        axes[1].set_xlabel('Failure Rate')
        axes[1].set_ylabel('Count')
        axes[1].set_xticks(x_pos)
        axes[1].set_xticklabels(scenario_labels)
        axes[1].grid(True, alpha=0.3, axis='y', linestyle='--')
        for bar in bars2:
            height = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height):,}', ha='center', va='bottom', fontsize=9)
        
        # 總字節數（KB）
        total_bytes_kb = [b / 1024 for b in total_bytes]
        bars3 = axes[2].bar(x_pos, total_bytes_kb, color=colors, 
                           alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[2].set_title('Total Signaling Traffic (KB)', fontsize=12, fontweight='bold')
        axes[2].set_xlabel('Failure Rate')
        axes[2].set_ylabel('KB')
        axes[2].set_xticks(x_pos)
        axes[2].set_xticklabels(scenario_labels)
        axes[2].grid(True, alpha=0.3, axis='y', linestyle='--')
        for bar in bars3:
            height = bar.get_height()
            axes[2].text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:,.1f}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        
        # 保存圖表
        algo_filename = algo.replace("_", "")
        output_file = os.path.join(OUTPUT_DIR, f'{algo_filename}_cross_scenario.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 已保存：{output_file}")


def plot_combined_comparison(results):
    """組合圖：所有演算法、所有場景"""
    print("\n生成組合比較圖表...")
    
    # 創建大型圖表
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Algorithm Comparison under Dynamic ISL Failures (Chaos Monkey)\n'
                 'GRHR (K=4) vs LoHi vs Baseline', 
                 fontsize=16, fontweight='bold')
    
    metrics = ['routing_updates', 'total_messages', 'total_bytes']
    metric_labels = ['Routing Updates', 'Total Messages', 'Total Traffic (KB)']
    
    for row, scenario in enumerate(SCENARIOS[:2]):  # 只顯示 P1, P5
        for col, (metric, label) in enumerate(zip(metrics, metric_labels)):
            ax = axes[row, col]
            
            # 提取數據
            algo_list = []
            values = []
            
            for algo in ALGORITHMS:
                if results[scenario][algo]:
                    algo_list.append(ALGORITHM_LABELS[algo])
                    val = results[scenario][algo][metric]
                    if metric == 'total_bytes':
                        val = val / 1024  # 轉換為 KB
                    values.append(val)
            
            if algo_list:
                x_pos = range(len(algo_list))
                colors = [ALGORITHM_COLORS[a] for a in ALGORITHMS if results[scenario][a]]
                
                bars = ax.bar(x_pos, values, color=colors, 
                             alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
                ax.set_title(f'{label}\n({scenario.upper()})', fontsize=11, fontweight='bold')
                ax.set_xlabel('Algorithm')
                ax.set_ylabel('KB' if metric == 'total_bytes' else 'Count')
                ax.set_xticks(x_pos)
                ax.set_xticklabels(algo_list, rotation=20, ha='right', fontsize=9)
                ax.grid(True, alpha=0.3, axis='y', linestyle='--')
                
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:,.0f}' if height >= 1 else f'{height:.2f}',
                           ha='center', va='bottom', fontsize=8)
    
    # P10 放在第三行
    for col, (metric, label) in enumerate(zip(metrics, metric_labels)):
        ax = axes[1, col]  # 使用第二行
        scenario = 'p10'
        
        # 更新標題為 P10
        algo_list = []
        values = []
        
        for algo in ALGORITHMS:
            if results[scenario][algo]:
                algo_list.append(ALGORITHM_LABELS[algo])
                val = results[scenario][algo][metric]
                if metric == 'total_bytes':
                    val = val / 1024
                values.append(val)
        
        if algo_list:
            x_pos = range(len(algo_list))
            colors = [ALGORITHM_COLORS[a] for a in ALGORITHMS if results[scenario][a]]
            
            ax.clear()
            bars = ax.bar(x_pos, values, color=colors, 
                         alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
            ax.set_title(f'{label}\n({scenario.upper()})', fontsize=11, fontweight='bold')
            ax.set_xlabel('Algorithm')
            ax.set_ylabel('KB' if metric == 'total_bytes' else 'Count')
            ax.set_xticks(x_pos)
            ax.set_xticklabels(algo_list, rotation=20, ha='right', fontsize=9)
            ax.grid(True, alpha=0.3, axis='y', linestyle='--')
            
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:,.0f}' if height >= 1 else f'{height:.2f}',
                       ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    
    output_file = os.path.join(OUTPUT_DIR, 'algorithm_comparison_all_scenarios.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ 已保存組合圖：{output_file}")


def generate_report(results):
    """生成文字報告"""
    print("\n生成分析報告...")
    
    report_file = os.path.join(OUTPUT_DIR, "algorithm_comparison_report.txt")
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("演算法比較分析報告\n")
        f.write("GRHR (K=4) vs LoHi vs Baseline\n")
        f.write("動態 ISL 失效場景 (Chaos Monkey)\n")
        f.write("=" * 70 + "\n")
        f.write(f"生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # 每個場景的統計
        for scenario in SCENARIOS:
            f.write("-" * 70 + "\n")
            f.write(f"場景：{SCENARIO_LABELS[scenario]}\n")
            f.write("-" * 70 + "\n\n")
            
            # 表頭
            f.write(f"{'演算法':<25} {'路由更新':>12} {'網關更新':>12} {'總訊息':>12} {'總流量(KB)':>15}\n")
            f.write("-" * 70 + "\n")
            
            for algo in ALGORITHMS:
                if results[scenario][algo]:
                    stats = results[scenario][algo]
                    f.write(f"{ALGORITHM_LABELS[algo]:<25} "
                           f"{stats['routing_updates']:>12,} "
                           f"{stats['gateway_updates']:>12,} "
                           f"{stats['total_messages']:>12,} "
                           f"{stats['total_bytes']/1024:>15,.2f}\n")
                else:
                    f.write(f"{ALGORITHM_LABELS[algo]:<25} {'N/A':>12} {'N/A':>12} {'N/A':>12} {'N/A':>15}\n")
            
            f.write("\n")
        
        # 總結
        f.write("=" * 70 + "\n")
        f.write("分析總結\n")
        f.write("=" * 70 + "\n\n")
        
        # 找出每個指標的最佳演算法
        for scenario in SCENARIOS:
            f.write(f"\n{SCENARIO_LABELS[scenario]}:\n")
            
            # 計算最小路由更新
            valid_algos = [(a, results[scenario][a]['routing_updates']) 
                          for a in ALGORITHMS if results[scenario][a]]
            if valid_algos:
                best = min(valid_algos, key=lambda x: x[1])
                f.write(f"  - 最少路由更新：{ALGORITHM_LABELS[best[0]]} ({best[1]:,} 次)\n")
            
            # 計算最小總流量
            valid_algos = [(a, results[scenario][a]['total_bytes']) 
                          for a in ALGORITHMS if results[scenario][a]]
            if valid_algos:
                best = min(valid_algos, key=lambda x: x[1])
                f.write(f"  - 最少信令流量：{ALGORITHM_LABELS[best[0]]} ({best[1]/1024:,.2f} KB)\n")
        
        f.write("\n")
    
    print(f"  ✓ 已保存報告：{report_file}")


def main():
    """主程式"""
    print("")
    print("*" * 70)
    print("*  演算法比較分析：GRHR (K=4) vs LoHi vs Baseline")
    print("*  動態 ISL 失效場景 (Chaos Monkey P1/P5/P10)")
    print("*" * 70)
    print("")
    
    # 載入數據
    results = load_all_data()
    
    # 檢查是否有足夠數據
    has_data = False
    for scenario in SCENARIOS:
        for algo in ALGORITHMS:
            if results[scenario][algo]:
                has_data = True
                break
    
    if not has_data:
        print("\n⚠️ 錯誤：沒有找到任何統計數據！")
        print("請先執行以下步驟：")
        print("  1. bash run_algorithm_comparison_dynamic.sh  # 執行模擬")
        print("  2. bash merge_algorithm_comparison_dynamic.sh  # 合併統計")
        sys.exit(1)
    
    # 生成圖表
    plot_algorithm_comparison_by_scenario(results)
    plot_cross_scenario_comparison(results)
    plot_combined_comparison(results)
    
    # 生成報告
    generate_report(results)
    
    print("\n" + "=" * 70)
    print("分析完成！")
    print("=" * 70)
    print(f"\n輸出目錄：{OUTPUT_DIR}/")
    print("\n生成的檔案：")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        filepath = os.path.join(OUTPUT_DIR, f)
        size = os.path.getsize(filepath)
        print(f"  - {f} ({size:,} bytes)")


if __name__ == "__main__":
    main()
