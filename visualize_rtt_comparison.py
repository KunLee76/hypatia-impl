#!/usr/bin/env python3
"""
RTT 比較視覺化腳本
讀取 RTT 分析結果並生成比較圖表
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# 配置
DATA_FILE = Path("paper/satgenpy_analysis/rtt_analysis_results/rtt_analysis_data.json")
OUTPUT_DIR = Path("paper/satgenpy_analysis/rtt_analysis_results")

# 設定中文字體
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial Unicode MS', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 顏色配置
COLORS = {
    'Baseline': '#FF6B6B',      # 珊瑚紅
    'GID': '#4ECDC4',           # 青綠色
    'LoHi': '#95A5A6',          # 灰色
}

# 路由中文名稱映射
ROUTE_LABELS = {
    'Tokyo_to_Shanghai': 'Tokyo → Shanghai',
    'Tokyo_to_Delhi': 'Tokyo → Delhi',
    'Tokyo_to_New_York': 'Tokyo → New York'
}

def load_data():
    """載入 RTT 分析數據"""
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def extract_stats(data):
    """提取統計數據供繪圖使用"""
    stats = {}
    
    # Baseline
    if 'default' in data.get('Baseline', {}):
        stats['Baseline'] = data['Baseline']['default']['routes']
    
    # GID
    gid_data = data.get('GID', {})
    if '27' in gid_data:
        stats['GID'] = gid_data['27']['routes']
    
    # LoHi
    if 'default' in data.get('LoHi', {}):
        stats['LoHi'] = data['LoHi']['default']['routes']
    
    return stats

def plot_overall_comparison(stats, output_file):
    """
    圖表 1: 整體平均 RTT 比較（柱狀圖）
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    algorithms = []
    avg_rtts = []
    colors = []
    
    for algo in ['Baseline', 'GID', 'LoHi']:
        if algo in stats:
            routes = stats[algo]
            avg_rtt = np.mean([route['mean'] for route in routes.values()])
            algorithms.append(algo if algo != 'GID' else 'GID (27°)')
            avg_rtts.append(avg_rtt)
            colors.append(COLORS[algo])
    
    bars = ax.bar(algorithms, avg_rtts, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
    
    # 添加數值標籤
    for bar, value in zip(bars, avg_rtts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{value:.2f} ms',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.set_ylabel('Average RTT (ms)', fontsize=14, fontweight='bold')
    ax.set_title('Overall Average RTT Comparison', fontsize=16, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, max(avg_rtts) * 1.15)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 圖表 1 已保存: {output_file}")

def plot_route_comparison(stats, output_file):
    """
    圖表 2: 各路由的 RTT 比較（分組柱狀圖）
    """
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # 收集所有路由
    all_routes = set()
    for algo_stats in stats.values():
        all_routes.update(algo_stats.keys())
    routes = sorted(all_routes)
    
    x = np.arange(len(routes))
    width = 0.25
    
    algorithms = ['Baseline', 'GID', 'LoHi']
    offsets = [-width, 0, width]
    
    for algo, offset in zip(algorithms, offsets):
        if algo in stats:
            rtts = []
            for route in routes:
                if route in stats[algo]:
                    rtts.append(stats[algo][route]['mean'])
                else:
                    rtts.append(0)
            
            label = algo if algo != 'GID' else 'GID (27°)'
            bars = ax.bar(x + offset, rtts, width, label=label, 
                         color=COLORS[algo], alpha=0.8, edgecolor='black', linewidth=1.2)
            
            # 添加數值標籤
            for bar, value in zip(bars, rtts):
                if value > 0:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                            f'{value:.1f}',
                            ha='center', va='bottom', fontsize=9, rotation=0)
    
    # 設定 x 軸標籤
    route_labels = [ROUTE_LABELS.get(r, r) for r in routes]
    ax.set_xticks(x)
    ax.set_xticklabels(route_labels, fontsize=12)
    
    ax.set_ylabel('Average RTT (ms)', fontsize=14, fontweight='bold')
    ax.set_title('RTT Comparison by Route', fontsize=16, fontweight='bold', pad=20)
    ax.legend(fontsize=12, loc='upper left', framealpha=0.9)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 圖表 2 已保存: {output_file}")

def plot_rtt_distribution(stats, output_file):
    """
    圖表 3: RTT 分佈比較（箱型圖）
    """
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # 收集所有路由的數據
    all_routes = set()
    for algo_stats in stats.values():
        all_routes.update(algo_stats.keys())
    routes = sorted(all_routes)
    
    # 為每個演算法準備數據
    data_to_plot = []
    labels = []
    positions = []
    colors_list = []
    
    pos = 1
    for route in routes:
        route_label = ROUTE_LABELS.get(route, route)
        
        for algo in ['Baseline', 'GID', 'LoHi']:
            if algo in stats and route in stats[algo]:
                route_stats = stats[algo][route]
                # 使用最小值、平均值、最大值來模擬分佈
                values = [route_stats['min'], route_stats['mean'], route_stats['max']]
                data_to_plot.append(values)
                
                algo_label = algo if algo != 'GID' else 'GID (27°)'
                labels.append(f"{route_label}\n{algo_label}")
                positions.append(pos)
                colors_list.append(COLORS[algo])
                pos += 1
        
        pos += 0.5  # 路由之間的間隔
    
    # 繪製箱型圖
    bp = ax.boxplot(data_to_plot, positions=positions, widths=0.6,
                    patch_artist=True, showfliers=False)
    
    # 設定顏色
    for patch, color in zip(bp['boxes'], colors_list):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('RTT (ms)', fontsize=14, fontweight='bold')
    ax.set_title('RTT Distribution (Min, Mean, Max)', fontsize=16, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 圖表 3 已保存: {output_file}")

def plot_improvement_percentage(stats, output_file):
    """
    圖表 4: 相對於 LoHi 的 RTT 改善百分比
    """
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # 收集所有路由
    all_routes = set()
    for algo_stats in stats.values():
        all_routes.update(algo_stats.keys())
    routes = sorted(all_routes)
    
    x = np.arange(len(routes))
    width = 0.35
    
    baseline_improvements = []
    gid_improvements = []
    
    for route in routes:
        if 'LoHi' in stats and route in stats['LoHi']:
            lohi_rtt = stats['LoHi'][route]['mean']
            
            # Baseline 改善
            if 'Baseline' in stats and route in stats['Baseline']:
                baseline_rtt = stats['Baseline'][route]['mean']
                improvement = ((lohi_rtt - baseline_rtt) / lohi_rtt) * 100
                baseline_improvements.append(improvement)
            else:
                baseline_improvements.append(0)
            
            # GID 改善
            if 'GID' in stats and route in stats['GID']:
                gid_rtt = stats['GID'][route]['mean']
                improvement = ((lohi_rtt - gid_rtt) / lohi_rtt) * 100
                gid_improvements.append(improvement)
            else:
                gid_improvements.append(0)
        else:
            baseline_improvements.append(0)
            gid_improvements.append(0)
    
    bars1 = ax.bar(x - width/2, baseline_improvements, width, label='Baseline',
                   color=COLORS['Baseline'], alpha=0.8, edgecolor='black', linewidth=1.2)
    bars2 = ax.bar(x + width/2, gid_improvements, width, label='GID (27°)',
                   color=COLORS['GID'], alpha=0.8, edgecolor='black', linewidth=1.2)
    
    # 添加數值標籤
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}%',
                        ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 設定 x 軸標籤
    route_labels = [ROUTE_LABELS.get(r, r) for r in routes]
    ax.set_xticks(x)
    ax.set_xticklabels(route_labels, fontsize=12)
    
    ax.set_ylabel('RTT Improvement (%)', fontsize=14, fontweight='bold')
    ax.set_title('RTT Improvement vs LoHi', fontsize=16, fontweight='bold', pad=20)
    ax.legend(fontsize=12, loc='upper left', framealpha=0.9)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 圖表 4 已保存: {output_file}")

def plot_combined_metrics(stats, output_file):
    """
    圖表 5: 綜合指標比較（平均、最小、最大 RTT）
    """
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
    
    algorithms = ['Baseline', 'GID', 'LoHi']
    metrics = ['mean', 'min', 'max']
    titles = ['Average RTT', 'Minimum RTT', 'Maximum RTT']
    axes = [ax1, ax2, ax3]
    
    for ax, metric, title in zip(axes, metrics, titles):
        algo_names = []
        values = []
        colors = []
        
        for algo in algorithms:
            if algo in stats:
                routes = stats[algo]
                value = np.mean([route[metric] for route in routes.values()])
                algo_names.append(algo if algo != 'GID' else 'GID (27°)')
                values.append(value)
                colors.append(COLORS[algo])
        
        bars = ax.bar(algo_names, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        
        # 添加數值標籤
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{value:.2f}',
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        ax.set_ylabel('RTT (ms)', fontsize=12, fontweight='bold')
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_ylim(0, max(values) * 1.15)
    
    plt.suptitle('RTT Metrics Comparison', fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 圖表 5 已保存: {output_file}")

def main():
    print("=" * 80)
    print("RTT 比較視覺化工具")
    print("=" * 80)
    print()
    
    # 載入數據
    print("📊 載入 RTT 分析數據...")
    data = load_data()
    stats = extract_stats(data)
    
    print(f"✅ 找到 {len(stats)} 個演算法的數據")
    for algo, routes in stats.items():
        print(f"   - {algo}: {len(routes)} 條路由")
    print()
    
    # 生成圖表
    print("🎨 生成視覺化圖表...")
    print()
    
    plot_overall_comparison(stats, OUTPUT_DIR / "rtt_chart_1_overall.png")
    plot_route_comparison(stats, OUTPUT_DIR / "rtt_chart_2_by_route.png")
    plot_rtt_distribution(stats, OUTPUT_DIR / "rtt_chart_3_distribution.png")
    plot_improvement_percentage(stats, OUTPUT_DIR / "rtt_chart_4_improvement.png")
    plot_combined_metrics(stats, OUTPUT_DIR / "rtt_chart_5_metrics.png")
    
    print()
    print("=" * 80)
    print("🎉 所有圖表生成完成！")
    print("=" * 80)
    print()
    print(f"圖表保存位置: {OUTPUT_DIR}")
    print("生成的圖表:")
    print("  1. rtt_chart_1_overall.png       - 整體平均 RTT 比較")
    print("  2. rtt_chart_2_by_route.png      - 各路由 RTT 比較")
    print("  3. rtt_chart_3_distribution.png  - RTT 分佈比較")
    print("  4. rtt_chart_4_improvement.png   - 相對 LoHi 的改善")
    print("  5. rtt_chart_5_metrics.png       - 綜合指標比較")

if __name__ == "__main__":
    main()
