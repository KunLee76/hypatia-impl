#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分析動態失效場景（Chaos Monkey）的控制信令統計

用途：
  1. 讀取所有動態失效場景的統計數據
  2. 生成 K 值比較圖表（每個失效率一張圖）
  3. 與靜態失效場景（Failure）比較
  4. 生成報告文件

執行方式：
  python analyze_dynamic_scenarios.py
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
WORK_DIR = "paper/satellite_networks_state"
ANALYTIC_DIR = os.path.join(WORK_DIR, "analytic_result")
OUTPUT_DIR = "dynamic_scenario_analysis"

# 場景定義
SCENARIOS = ["p1", "p5", "p10"]
SCENARIO_LABELS = {
    "p1": "Dynamic 1% ISL Failure (Chaos Monkey)",
    "p5": "Dynamic 5% ISL Failure (Chaos Monkey)",
    "p10": "Dynamic 10% ISL Failure (Chaos Monkey)"
}
SCENARIO_COLORS = {
    "p1": "#3498db",   # 藍色
    "p5": "#e74c3c",   # 紅色
    "p10": "#9b59b6"   # 紫色
}
K_VALUES = [1, 2, 4, 6, 8, 999]


def load_stats(scenario, k):
    """載入指定場景和 K 值的統計數據"""
    filename = f"hierarchical_gid_27deg_dynamic_{scenario}_k{k}_signaling_stats.json"
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


def extract_signaling_stats(data):
    """提取控制信令統計數據"""
    if not data:
        return None
    
    return {
        'routing_updates': data.get('routing_updates', 0),
        'gateway_updates': data.get('gateway_updates', 0),
        'gid_rebuilds': data.get('gid_rebuilds', 0),
        'topology_changes': data.get('topology_changes', 0),
        'total_messages': data.get('total_messages', 0),
        'total_bytes': data.get('total_bytes', 0),
        'timeline_events': len(data.get('timeline', []))
    }


def load_all_scenarios():
    """載入所有場景的統計數據"""
    print("=" * 70)
    print("載入動態失效場景統計數據")
    print("=" * 70)
    
    results = {}
    
    for scenario in SCENARIOS:
        print(f"\n場景：{SCENARIO_LABELS[scenario]}")
        results[scenario] = {}
        
        for k in K_VALUES:
            print(f"  K={k:3d} ... ", end='')
            data = load_stats(scenario, k)
            
            if data:
                stats = extract_signaling_stats(data)
                results[scenario][k] = stats
                print(f"✓ (事件數: {stats['timeline_events']}, 總訊息: {stats['total_messages']})")
            else:
                results[scenario][k] = None
                print("✗ 失敗")
    
    print("\n" + "=" * 70)
    return results


def plot_k_comparison_by_scenario(results):
    """為每個場景生成 K 值比較圖"""
    print("\n生成 K 值比較圖表...")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for scenario in SCENARIOS:
        print(f"  繪製場景：{scenario.upper()} ... ", end='')
        
        # 提取數據
        k_list = []
        routing_updates = []
        gateway_updates = []
        gid_rebuilds = []
        total_messages = []
        
        for k in K_VALUES:
            if results[scenario][k]:
                k_list.append(k if k != 999 else 'All')
                stats = results[scenario][k]
                routing_updates.append(stats['routing_updates'])
                gateway_updates.append(stats['gateway_updates'])
                gid_rebuilds.append(stats['gid_rebuilds'])
                total_messages.append(stats['total_messages'])
        
        if not k_list:
            print("無數據")
            continue
        
        # 創建圖表
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'{SCENARIO_LABELS[scenario]} - K Parameter Impact', 
                     fontsize=14, fontweight='bold')
        
        # 使用 viridis 配色
        colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(k_list)))
        
        # 路由更新
        bars1 = axes[0, 0].bar(range(len(k_list)), routing_updates, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[0, 0].set_title('Routing Updates', fontsize=12, fontweight='bold')
        axes[0, 0].set_xlabel('K Value')
        axes[0, 0].set_ylabel('Count')
        axes[0, 0].set_xticks(range(len(k_list)))
        axes[0, 0].set_xticklabels(k_list)
        axes[0, 0].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars1:
            height = bar.get_height()
            axes[0, 0].text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        # 網關更新
        bars2 = axes[0, 1].bar(range(len(k_list)), gateway_updates, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[0, 1].set_title('Gateway Updates', fontsize=12, fontweight='bold')
        axes[0, 1].set_xlabel('K Value')
        axes[0, 1].set_ylabel('Count')
        axes[0, 1].set_xticks(range(len(k_list)))
        axes[0, 1].set_xticklabels(k_list)
        axes[0, 1].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars2:
            height = bar.get_height()
            axes[0, 1].text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        # GID 重建
        bars3 = axes[1, 0].bar(range(len(k_list)), gid_rebuilds, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[1, 0].set_title('GID Rebuilds', fontsize=12, fontweight='bold')
        axes[1, 0].set_xlabel('K Value')
        axes[1, 0].set_ylabel('Count')
        axes[1, 0].set_xticks(range(len(k_list)))
        axes[1, 0].set_xticklabels(k_list)
        axes[1, 0].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars3:
            height = bar.get_height()
            axes[1, 0].text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        # 總訊息數
        bars4 = axes[1, 1].bar(range(len(k_list)), total_messages, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[1, 1].set_title('Total Messages', fontsize=12, fontweight='bold')
        axes[1, 1].set_xlabel('K Value')
        axes[1, 1].set_ylabel('Count')
        axes[1, 1].set_xticks(range(len(k_list)))
        axes[1, 1].set_xticklabels(k_list)
        axes[1, 1].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars4:
            height = bar.get_height()
            axes[1, 1].text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        
        # 保存圖表
        output_file = os.path.join(OUTPUT_DIR, f'dynamic_{scenario}_k_comparison.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✓ 已保存：{output_file}")


def plot_scenario_comparison(results):
    """比較不同失效率場景（固定 K 值）"""
    print("\n生成失效率比較圖表...")
    
    # 為每個 K 值生成一張比較圖
    for k in K_VALUES:
        print(f"  K={k} ... ", end='')
        
        # 提取數據
        scenario_labels = []
        routing_updates = []
        gateway_updates = []
        gid_rebuilds = []
        total_messages = []
        
        for scenario in SCENARIOS:
            if results[scenario][k]:
                scenario_labels.append(scenario.upper())
                stats = results[scenario][k]
                routing_updates.append(stats['routing_updates'])
                gateway_updates.append(stats['gateway_updates'])
                gid_rebuilds.append(stats['gid_rebuilds'])
                total_messages.append(stats['total_messages'])
        
        if not scenario_labels:
            print("無數據")
            continue
        
        # 創建圖表
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        k_label = k if k != 999 else 'All'
        fig.suptitle(f'Dynamic Failure Scenarios Comparison (K={k_label})', 
                     fontsize=14, fontweight='bold')
        
        x_pos = range(len(scenario_labels))
        colors = [SCENARIO_COLORS[s.lower()] for s in scenario_labels]
        
        # 路由更新
        bars1 = axes[0, 0].bar(x_pos, routing_updates, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[0, 0].set_title('Routing Updates', fontsize=12, fontweight='bold')
        axes[0, 0].set_xlabel('Failure Rate')
        axes[0, 0].set_ylabel('Count')
        axes[0, 0].set_xticks(x_pos)
        axes[0, 0].set_xticklabels(scenario_labels)
        axes[0, 0].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars1:
            height = bar.get_height()
            axes[0, 0].text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        # 網關更新
        bars2 = axes[0, 1].bar(x_pos, gateway_updates, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[0, 1].set_title('Gateway Updates', fontsize=12, fontweight='bold')
        axes[0, 1].set_xlabel('Failure Rate')
        axes[0, 1].set_ylabel('Count')
        axes[0, 1].set_xticks(x_pos)
        axes[0, 1].set_xticklabels(scenario_labels)
        axes[0, 1].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars2:
            height = bar.get_height()
            axes[0, 1].text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        # GID 重建
        bars3 = axes[1, 0].bar(x_pos, gid_rebuilds, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[1, 0].set_title('GID Rebuilds', fontsize=12, fontweight='bold')
        axes[1, 0].set_xlabel('Failure Rate')
        axes[1, 0].set_ylabel('Count')
        axes[1, 0].set_xticks(x_pos)
        axes[1, 0].set_xticklabels(scenario_labels)
        axes[1, 0].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars3:
            height = bar.get_height()
            axes[1, 0].text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        # 總訊息數
        bars4 = axes[1, 1].bar(x_pos, total_messages, color=colors, 
                              alpha=0.85, edgecolor='black', linewidth=0.5, width=0.6)
        axes[1, 1].set_title('Total Messages', fontsize=12, fontweight='bold')
        axes[1, 1].set_xlabel('Failure Rate')
        axes[1, 1].set_ylabel('Count')
        axes[1, 1].set_xticks(x_pos)
        axes[1, 1].set_xticklabels(scenario_labels)
        axes[1, 1].grid(True, alpha=0.3, axis='y', linestyle='--')
        # 標註數值
        for bar in bars4:
            height = bar.get_height()
            axes[1, 1].text(bar.get_x() + bar.get_width()/2., height,
                          f'{int(height)}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        
        # 保存圖表
        k_suffix = k if k != 999 else 'all'
        output_file = os.path.join(OUTPUT_DIR, f'dynamic_scenarios_comparison_k{k_suffix}.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✓")
    
    print(f"  已保存於：{OUTPUT_DIR}/")


def plot_comprehensive_comparison(results):
    """生成綜合比較圖：所有場景 × 所有 K 值"""
    print("\n生成綜合比較圖表...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Dynamic Failure Scenarios - Comprehensive Comparison', 
                 fontsize=16, fontweight='bold')
    
    # 準備數據
    metrics = ['routing_updates', 'gateway_updates', 'gid_rebuilds', 'total_messages']
    titles = ['Routing Updates', 'Gateway Updates', 'GID Rebuilds', 'Total Messages']
    
    for idx, (metric, title) in enumerate(zip(metrics, titles)):
        ax = axes[idx // 2, idx % 2]
        
        for scenario in SCENARIOS:
            k_list = []
            values = []
            
            for k in K_VALUES:
                if results[scenario][k]:
                    k_list.append(k if k != 999 else 100)  # 999 用 100 表示在圖上
                    values.append(results[scenario][k][metric])
            
            if k_list:
                ax.plot(k_list, values, marker='o', linewidth=2, 
                       label=scenario.upper(), color=SCENARIO_COLORS[scenario])
        
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlabel('K Value', fontsize=11)
        ax.set_ylabel('Count', fontsize=11)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_xscale('log')
        
        # 設定 x 軸刻度
        ax.set_xticks([1, 2, 4, 6, 8, 100])
        ax.set_xticklabels(['1', '2', '4', '6', '8', 'All'])
    
    plt.tight_layout()
    
    output_file = os.path.join(OUTPUT_DIR, 'dynamic_comprehensive_comparison.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✓ 已保存：{output_file}")


def generate_report(results):
    """生成分析報告"""
    print("\n生成分析報告...")
    
    report_file = os.path.join(OUTPUT_DIR, f'dynamic_analysis_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("動態失效場景（Chaos Monkey）控制信令分析報告\n")
        f.write("=" * 70 + "\n")
        f.write(f"生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"模擬時長：200 秒\n")
        f.write(f"失效機制：Chaos Monkey（每 2 秒動態注入失效）\n")
        f.write("\n")
        
        for scenario in SCENARIOS:
            f.write(f"\n{SCENARIO_LABELS[scenario]}\n")
            f.write("-" * 70 + "\n")
            f.write(f"{'K值':>6} {'路由更新':>10} {'網關更新':>10} {'GID重建':>10} {'總訊息數':>10}\n")
            f.write("-" * 70 + "\n")
            
            for k in K_VALUES:
                if results[scenario][k]:
                    stats = results[scenario][k]
                    k_label = str(k) if k != 999 else 'All'
                    f.write(f"{k_label:>6} {stats['routing_updates']:>10} "
                           f"{stats['gateway_updates']:>10} {stats['gid_rebuilds']:>10} "
                           f"{stats['total_messages']:>10}\n")
            
            f.write("\n")
        
        # K 值影響分析
        f.write("\n" + "=" * 70 + "\n")
        f.write("K 值影響分析\n")
        f.write("=" * 70 + "\n")
        
        for scenario in SCENARIOS:
            f.write(f"\n{scenario.upper()}:\n")
            
            k1_stats = results[scenario][1]
            k_all_stats = results[scenario][999]
            
            if k1_stats and k_all_stats:
                reduction = {
                    'routing': (1 - k1_stats['routing_updates'] / k_all_stats['routing_updates']) * 100,
                    'gateway': (1 - k1_stats['gateway_updates'] / k_all_stats['gateway_updates']) * 100,
                    'gid': (1 - k1_stats['gid_rebuilds'] / k_all_stats['gid_rebuilds']) * 100,
                    'total': (1 - k1_stats['total_messages'] / k_all_stats['total_messages']) * 100
                }
                
                f.write(f"  K=1 vs K=All:\n")
                f.write(f"    路由更新減少：{reduction['routing']:.1f}%\n")
                f.write(f"    網關更新減少：{reduction['gateway']:.1f}%\n")
                f.write(f"    GID 重建減少：{reduction['gid']:.1f}%\n")
                f.write(f"    總訊息減少：{reduction['total']:.1f}%\n")
        
        f.write("\n" + "=" * 70 + "\n")
        f.write("報告結束\n")
        f.write("=" * 70 + "\n")
    
    print(f"  ✓ 已保存：{report_file}")


def main():
    print("\n" + "=" * 70)
    print("動態失效場景（Chaos Monkey）控制信令分析工具")
    print("=" * 70)
    print()
    
    # 載入數據
    results = load_all_scenarios()
    
    # 檢查是否有數據
    has_data = any(
        any(results[s][k] for k in K_VALUES)
        for s in SCENARIOS
    )
    
    if not has_data:
        print("\n✗ 錯誤：未找到任何統計數據")
        return 1
    
    # 生成圖表
    plot_k_comparison_by_scenario(results)
    plot_scenario_comparison(results)
    plot_comprehensive_comparison(results)
    
    # 生成報告
    generate_report(results)
    
    print("\n" + "=" * 70)
    print("✓ 分析完成！")
    print("=" * 70)
    print(f"\n輸出目錄：{OUTPUT_DIR}/")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
