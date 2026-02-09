#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
時間線事件分布分析

用途：
  1. 分析控制信令在時間軸上的分布
  2. 檢驗 GID 切換（~150s）是否會增加信令
  3. 比較前半段 vs 後半段的信令量

執行方式：
  python analyze_timeline_distribution.py
"""

import json
import os
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from collections import defaultdict
from datetime import datetime

matplotlib.use('Agg')
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

ANALYTIC_DIR = "paper/satellite_networks_state/analytic_result"
OUTPUT_DIR = "timeline_analysis"


def load_timeline(filepath):
    """載入統計檔案的 timeline"""
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data.get('timeline', [])


def analyze_time_distribution(timeline, time_step_ms=2000):
    """分析時間分布"""
    if not timeline:
        return None
    
    # 按時間分組統計事件數
    time_bins = defaultdict(lambda: {'events': 0, 'bytes': 0, 'gid_rebuilds': 0, 
                                      'routing_updates': 0, 'gateway_updates': 0})
    
    for event in timeline:
        time_ms = event.get('time_ms', 0)
        time_s = time_ms / 1000  # 轉為秒
        
        # 10秒一個區間
        bin_idx = int(time_s // 10) * 10
        
        time_bins[bin_idx]['events'] += 1
        time_bins[bin_idx]['bytes'] += event.get('bytes', 0)
        
        event_type = event.get('event', '')
        if 'gid_rebuild' in event_type.lower():
            time_bins[bin_idx]['gid_rebuilds'] += 1
        elif 'routing' in event_type.lower():
            time_bins[bin_idx]['routing_updates'] += 1
        elif 'gateway' in event_type.lower():
            time_bins[bin_idx]['gateway_updates'] += 1
    
    return dict(time_bins)


def plot_timeline_comparison():
    """繪製時間線比較圖"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 載入 GRHR K=4 的 P1 場景（作為代表）
    scenarios = {
        'GRHR K=4 (P1)': f'{ANALYTIC_DIR}/hierarchical_gid_27deg_dynamic_p1_k4_signaling_stats.json',
        'GRHR K=8 (P1)': f'{ANALYTIC_DIR}/hierarchical_gid_27deg_dynamic_p1_k8_signaling_stats.json',
    }
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle('Timeline Event Distribution Analysis\n'
                 '(Checking if GID switch at ~150s increases signaling)',
                 fontsize=14, fontweight='bold')
    
    colors = ['#2c7fb8', '#41b6c4', '#a1dab4', '#ffffcc']
    
    for idx, (label, filepath) in enumerate(scenarios.items()):
        print(f"分析 {label}...")
        
        timeline = load_timeline(filepath)
        if not timeline:
            print(f"  ⚠️ 無法載入: {filepath}")
            continue
        
        distribution = analyze_time_distribution(timeline)
        if not distribution:
            continue
        
        # 準備繪圖數據
        times = sorted(distribution.keys())
        events = [distribution[t]['events'] for t in times]
        gid_rebuilds = [distribution[t]['gid_rebuilds'] for t in times]
        routing = [distribution[t]['routing_updates'] for t in times]
        
        # 事件總數分布
        ax = axes[idx // 2, idx % 2]
        
        x = np.array(times)
        width = 8
        
        ax.bar(x, events, width=width, alpha=0.7, label='Total Events', color=colors[0])
        ax.bar(x, gid_rebuilds, width=width, alpha=0.9, label='GID Rebuilds', color=colors[1])
        
        # 標記 150s 位置（預期 GID 切換點）
        ax.axvline(x=150, color='red', linestyle='--', linewidth=2, label='Expected GID Switch (~150s)')
        
        ax.set_title(f'{label}', fontsize=12, fontweight='bold')
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Event Count')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 計算前半段 vs 後半段
        first_half = sum(distribution[t]['events'] for t in times if t < 100)
        second_half = sum(distribution[t]['events'] for t in times if t >= 100)
        
        ax.text(0.02, 0.98, f'0-100s: {first_half} events\n100-200s: {second_half} events',
                transform=ax.transAxes, fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        print(f"  0-100s: {first_half} 事件, 100-200s: {second_half} 事件")
    
    plt.tight_layout()
    
    output_file = os.path.join(OUTPUT_DIR, 'timeline_distribution_grhr.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\n✓ 已保存: {output_file}")


def detailed_gid_analysis():
    """詳細分析 GID 重建事件"""
    print("\n" + "=" * 70)
    print("GID 重建事件詳細分析")
    print("=" * 70)
    
    filepath = f'{ANALYTIC_DIR}/hierarchical_gid_27deg_dynamic_p1_k4_signaling_stats.json'
    
    if not os.path.exists(filepath):
        print(f"檔案不存在: {filepath}")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    timeline = data.get('timeline', [])
    
    print(f"\n總事件數: {len(timeline)}")
    print(f"GID 重建次數: {data.get('gid_rebuilds', 'N/A')}")
    print(f"路由更新次數: {data.get('routing_updates', 'N/A')}")
    print(f"網關更新次數: {data.get('gateway_updates', 'N/A')}")
    
    # 找出 GID rebuild 事件
    print("\n--- GID Rebuild 事件時間 ---")
    gid_events = [e for e in timeline if 'gid' in e.get('event', '').lower()]
    
    if gid_events:
        for e in gid_events[:20]:  # 只顯示前 20 個
            time_s = e.get('time_ms', 0) / 1000
            print(f"  t={time_s:6.1f}s: {e.get('event')} (count={e.get('count')}, bytes={e.get('bytes')})")
        
        if len(gid_events) > 20:
            print(f"  ... 還有 {len(gid_events) - 20} 個事件")
    else:
        print("  (無 GID rebuild 事件)")
    
    # 統計每個時間區間的事件類型
    print("\n--- 每 50 秒區間的事件統計 ---")
    print(f"{'時間區間':<15} {'總事件':>10} {'GID重建':>10} {'路由更新':>10} {'網關更新':>10}")
    print("-" * 60)
    
    for start in range(0, 200, 50):
        end = start + 50
        events_in_range = [e for e in timeline 
                          if start * 1000 <= e.get('time_ms', 0) < end * 1000]
        
        total = len(events_in_range)
        gid = len([e for e in events_in_range if 'gid' in e.get('event', '').lower()])
        routing = len([e for e in events_in_range if 'routing' in e.get('event', '').lower()])
        gateway = len([e for e in events_in_range if 'gateway' in e.get('event', '').lower()])
        
        print(f"{start:>3}-{end:<3}s        {total:>10} {gid:>10} {routing:>10} {gateway:>10}")


def compare_algorithms_timeline():
    """比較不同演算法的時間分布"""
    print("\n" + "=" * 70)
    print("跨演算法時間分布比較")
    print("=" * 70)
    
    # 檢查 LoHi 和 Baseline 的檔案是否存在
    files_to_check = {
        'GRHR K=4': f'{ANALYTIC_DIR}/hierarchical_gid_27deg_dynamic_p1_k4_signaling_stats.json',
        'GRHR K=8': f'{ANALYTIC_DIR}/hierarchical_gid_27deg_dynamic_p1_k8_signaling_stats.json',
        'LoHi': f'{ANALYTIC_DIR}/lohi_dynamic_p1_signaling_stats.json',
        'Baseline': f'{ANALYTIC_DIR}/baseline_dynamic_p1_signaling_stats.json',
    }
    
    print("\n檔案狀態:")
    for name, path in files_to_check.items():
        exists = "✓ 存在" if os.path.exists(path) else "✗ 不存在"
        print(f"  {name:<15}: {exists}")
    
    print("\n提示: 執行 LoHi/Baseline 模擬後，重新運行此腳本進行完整比較")


def main():
    print("*" * 70)
    print("*  時間線事件分布分析")
    print("*  檢驗 GID 切換是否增加控制信令")
    print("*" * 70)
    
    # 詳細 GID 分析
    detailed_gid_analysis()
    
    # 繪製時間分布圖
    plot_timeline_comparison()
    
    # 檢查其他演算法
    compare_algorithms_timeline()
    
    print("\n" + "=" * 70)
    print("分析完成！")
    print("=" * 70)
    print(f"\n輸出目錄: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
