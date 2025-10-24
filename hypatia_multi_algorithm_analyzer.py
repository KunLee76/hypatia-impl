#!/usr/bin/env python3
"""
Hypatia 多算法控制信令統計分析工具
可以同時比較多個算法的控制信令開銷：
- Floyd-Warshall Baseline
- Hierarchical GID (Floyd-Warshall)
- Hierarchical GID Dijkstra

使用方法：
python hypatia_multi_algorithm_analyzer.py
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys
from datetime import datetime
import numpy as np
import glob

class MultiAlgorithmAnalyzer:
    def __init__(self, stats_dir="paper/satellite_networks_state/analytic_result"):
        self.stats_dir = Path(stats_dir)
    
    def find_all_stats_files(self):
        """查找所有算法的統計文件"""
        patterns = {
            "baseline": "baseline_floyd_warshall_signaling_stats.json",
            "hierarchical_floyd": "hierarchical_gid_*deg_signaling_stats.json",
            "hierarchical_dijkstra": "hierarchical_gid_dijkstra_*deg_signaling_stats.json"
        }
        
        found_files = {}
        
        # Baseline
        baseline_path = self.stats_dir / patterns["baseline"]
        if baseline_path.exists():
            found_files['baseline'] = [str(baseline_path)]
        
        # Hierarchical (Floyd-Warshall)
        h_floyd_files = glob.glob(str(self.stats_dir / patterns["hierarchical_floyd"]))
        # 排除 dijkstra 版本
        h_floyd_files = [f for f in h_floyd_files if 'dijkstra' not in f]
        if h_floyd_files:
            found_files['hierarchical_floyd'] = sorted(h_floyd_files)
        
        # Hierarchical (Dijkstra)
        h_dijkstra_files = glob.glob(str(self.stats_dir / patterns["hierarchical_dijkstra"]))
        if h_dijkstra_files:
            found_files['hierarchical_dijkstra'] = sorted(h_dijkstra_files)
        
        return found_files
    
    def load_stats(self, file_path):
        """加載統計數據"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def analyze_all(self, output_dir="multi_algorithm_analysis"):
        """分析所有算法"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        print("🔍 查找算法統計文件...")
        all_files = self.find_all_stats_files()
        
        if not all_files:
            print("❌ 找不到任何統計文件")
            return None
        
        # 統計找到的文件
        total_files = sum(len(files) for files in all_files.values())
        print(f"\n📊 找到 {total_files} 個統計文件:")
        for category, files in all_files.items():
            if files:
                print(f"  - {category}: {len(files)} 個文件")
        
        # 加載所有數據
        algorithms_data = []
        
        for category, files in all_files.items():
            for file_path in files:
                data = self.load_stats(file_path)
                display_name = data.get('algorithm_display_name', Path(file_path).stem)
                grid_deg = data.get('grid_deg', None)
                
                algorithms_data.append({
                    'category': category,
                    'file': file_path,
                    'name': display_name,
                    'grid_deg': grid_deg,
                    'data': data
                })
                print(f"  ✅ {display_name}: {len(data.get('timeline', []))} 事件, {data['summary']['total_bytes']:,} 字節")
        
        if len(algorithms_data) < 2:
            print("⚠️  至少需要 2 個算法進行比較")
            return None
        
        # 按類別和網格大小排序
        algorithms_data.sort(key=lambda x: (
            0 if x['category'] == 'baseline' else 1 if x['category'] == 'hierarchical_floyd' else 2,
            x['grid_deg'] if x['grid_deg'] else 0
        ))
        
        # 生成比較報告
        self.generate_multi_comparison_report(algorithms_data, output_path)
        
        # 生成可視化
        self.generate_multi_algorithm_charts(algorithms_data, output_path)
        
        return output_path
    
    def generate_multi_comparison_report(self, algorithms_data, output_path):
        """生成多算法比較報告"""
        report_file = output_path / "multi_algorithm_comparison_report.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("Hypatia 多算法控制信令比較報告\n")
            f.write("=" * 60 + "\n")
            f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"比較算法數: {len(algorithms_data)}\n\n")
            
            # 找到基線（baseline）作為參考
            baseline_data = None
            for algo in algorithms_data:
                if algo['category'] == 'baseline':
                    baseline_data = algo['data']
                    break
            
            # 按類別分組輸出
            f.write("算法總覽:\n")
            f.write("-" * 60 + "\n")
            
            summary_table = []
            for algo in algorithms_data:
                summary = algo['data']['summary']
                summary_table.append({
                    'name': algo['name'],
                    'events': summary['total_events'],
                    'bytes': summary['total_bytes']
                })
            
            # 按字節數排序
            summary_table.sort(key=lambda x: x['bytes'])
            
            for item in summary_table:
                f.write(f"\n{item['name']}:\n")
                f.write(f"  總事件數: {item['events']:,}\n")
                f.write(f"  總字節數: {item['bytes']:,}\n")
                
                if baseline_data and item['bytes'] != baseline_data['summary']['total_bytes']:
                    baseline_bytes = baseline_data['summary']['total_bytes']
                    improvement = ((baseline_bytes - item['bytes']) / baseline_bytes * 100)
                    if improvement > 0:
                        f.write(f"  ✅ 相比基線節省: {improvement:.2f}%\n")
                    else:
                        f.write(f"  ❌ 相比基線增加: {abs(improvement):.2f}%\n")
            
            # 按事件類型比較
            f.write(f"\n\n按事件類型詳細比較:\n")
            f.write("-" * 60 + "\n")
            
            # 收集所有事件類型
            all_event_types = set()
            for algo in algorithms_data:
                if 'by_type' in algo['data']['summary']:
                    all_event_types.update(algo['data']['summary']['by_type'].keys())
            
            for event_type in sorted(all_event_types):
                f.write(f"\n{event_type}:\n")
                for algo in algorithms_data:
                    summary = algo['data']['summary']
                    if 'by_type' in summary and event_type in summary['by_type']:
                        stats = summary['by_type'][event_type]
                        f.write(f"  {algo['name']:40s}: {stats['count']:6d} 次, {stats['bytes']:10,} 字節\n")
                    else:
                        f.write(f"  {algo['name']:40s}: N/A\n")
        
        print(f"📄 比較報告已保存: {report_file}")
    
    def generate_multi_algorithm_charts(self, algorithms_data, output_path):
        """生成多算法比較圖表"""
        
        # Chart 1: 總體比較
        self._chart1_overall_multi(algorithms_data, output_path)
        
        # Chart 2: 時間軸分析
        self._chart2_timeline_multi(algorithms_data, output_path)
        
        # Chart 3: 事件類型分佈
        self._chart3_event_types_multi(algorithms_data, output_path)
        
        # Chart 4: 相對改進百分比
        self._chart4_improvement_multi(algorithms_data, output_path)
        
        print(f"✅ 所有圖表已保存到: {output_path}/")
    
    def _chart1_overall_multi(self, algorithms_data, output_path):
        """圖表1: 多算法總體比較"""
        num_algos = len(algorithms_data)
        
        # 根據算法數量調整圖表大小
        fig_width = max(16, num_algos * 1.5)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(fig_width, 8))
        
        names = [algo['name'] for algo in algorithms_data]
        total_bytes = [algo['data']['summary']['total_bytes'] for algo in algorithms_data]
        total_events = [algo['data']['summary']['total_events'] for algo in algorithms_data]
        
        # 改進的顏色編碼：使用漸變色表示不同網格大小
        colors = []
        for algo in algorithms_data:
            if algo['category'] == 'baseline':
                colors.append('coral')
            elif algo['category'] == 'hierarchical_dijkstra':
                # Dijkstra 系列使用藍色系
                grid_deg = algo.get('grid_deg', 15)
                # 根據網格大小調整顏色深淺
                intensity = 0.4 + (grid_deg / 30.0) * 0.6  # 10°->darker, 25°->lighter
                colors.append(plt.cm.Blues(intensity))
            else:
                # Floyd-Warshall hierarchical 使用綠色系
                grid_deg = algo.get('grid_deg', 15)
                intensity = 0.4 + (grid_deg / 30.0) * 0.6
                colors.append(plt.cm.Greens(intensity))
        
        # 左圖：總字節數
        bars1 = ax1.bar(range(len(names)), total_bytes, color=colors, alpha=0.85, edgecolor='black', linewidth=0.5)
        ax1.set_xlabel('Algorithm', fontsize=13, fontweight='bold')
        ax1.set_ylabel('Total Bytes', fontsize=13, fontweight='bold')
        ax1.set_title('Total Control Signaling Bytes', fontsize=15, fontweight='bold')
        ax1.set_xticks(range(len(names)))
        
        # 優化 x 軸標籤顯示
        if num_algos > 6:
            ax1.set_xticklabels(names, rotation=60, ha='right', fontsize=8)
        else:
            ax1.set_xticklabels(names, rotation=45, ha='right', fontsize=10)
        
        ax1.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 添加數值標籤（只在算法數量不太多時顯示）
        if num_algos <= 10:
            for bar, value in zip(bars1, total_bytes):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2, height,
                        f'{value:,}', ha='center', va='bottom', fontsize=8, rotation=0)
        
        # 右圖：總事件數
        bars2 = ax2.bar(range(len(names)), total_events, color=colors, alpha=0.85, edgecolor='black', linewidth=0.5)
        ax2.set_xlabel('Algorithm', fontsize=13, fontweight='bold')
        ax2.set_ylabel('Total Events', fontsize=13, fontweight='bold')
        ax2.set_title('Total Control Signaling Events', fontsize=15, fontweight='bold')
        ax2.set_xticks(range(len(names)))
        
        if num_algos > 6:
            ax2.set_xticklabels(names, rotation=60, ha='right', fontsize=8)
        else:
            ax2.set_xticklabels(names, rotation=45, ha='right', fontsize=10)
        
        ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 添加數值標籤
        if num_algos <= 10:
            for bar, value in zip(bars2, total_events):
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2, height,
                        f'{value:,}', ha='center', va='bottom', fontsize=8, rotation=0)
        
        plt.tight_layout()
        chart_file = output_path / "multi_chart1_overall_comparison.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  📊 圖表1已保存: {chart_file.name}")
    
    def _chart2_timeline_multi(self, algorithms_data, output_path):
        """圖表2: 多算法時間軸分析"""
        num_algos = len(algorithms_data)
        fig_width = max(14, min(20, num_algos * 1.2))
        fig, ax = plt.subplots(figsize=(fig_width, 8))
        
        # 為每個算法分配顏色和線型
        line_styles = ['-', '--', '-.', ':']
        
        for idx, algo in enumerate(algorithms_data):
            timeline = algo['data'].get('timeline', [])
            if timeline:
                df = pd.DataFrame(timeline)
                if not df.empty and 'time_ms' in df.columns and 'bytes' in df.columns:
                    df_sorted = df.sort_values('time_ms')
                    cumulative_bytes = df_sorted['bytes'].cumsum()
                    
                    # 顏色選擇
                    if algo['category'] == 'baseline':
                        color = 'coral'
                    elif algo['category'] == 'hierarchical_dijkstra':
                        grid_deg = algo.get('grid_deg', 15)
                        intensity = 0.4 + (grid_deg / 30.0) * 0.6
                        color = plt.cm.Blues(intensity)
                    else:
                        grid_deg = algo.get('grid_deg', 15)
                        intensity = 0.4 + (grid_deg / 30.0) * 0.6
                        color = plt.cm.Greens(intensity)
                    
                    # 線型選擇
                    linestyle = line_styles[idx % len(line_styles)]
                    
                    ax.plot(df_sorted['time_ms']/1000, cumulative_bytes,
                           label=algo['name'], color=color, linewidth=2.5,
                           linestyle=linestyle, alpha=0.85)
        
        ax.set_title('Cumulative Control Overhead Over Time', fontsize=15, fontweight='bold')
        ax.set_xlabel('Time (seconds)', fontsize=13, fontweight='bold')
        ax.set_ylabel('Cumulative Bytes', fontsize=13, fontweight='bold')
        
        # 優化圖例顯示
        if num_algos > 8:
            ax.legend(loc='upper left', fontsize=8, framealpha=0.9, ncol=2)
        else:
            ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
        
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        chart_file = output_path / "multi_chart2_timeline_analysis.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  📊 圖表2已保存: {chart_file.name}")
    
    def _chart3_event_types_multi(self, algorithms_data, output_path):
        """圖表3: 多算法事件類型分佈"""
        # 收集所有事件類型
        all_event_types = set()
        for algo in algorithms_data:
            if 'by_type' in algo['data']['summary']:
                all_event_types.update(algo['data']['summary']['by_type'].keys())
        
        all_event_types = sorted(list(all_event_types))
        
        if not all_event_types:
            print("  ⚠️  沒有事件類型數據，跳過圖表3")
            return
        
        num_algos = len(algorithms_data)
        fig_width = max(14, len(all_event_types) * 2 + num_algos)
        fig, ax = plt.subplots(figsize=(fig_width, 9))
        
        x = np.arange(len(all_event_types))
        num_algorithms = len(algorithms_data)
        width = 0.75 / num_algorithms
        
        for idx, algo in enumerate(algorithms_data):
            summary = algo['data']['summary']
            counts = []
            for event_type in all_event_types:
                if 'by_type' in summary and event_type in summary['by_type']:
                    counts.append(summary['by_type'][event_type]['count'])
                else:
                    counts.append(0)
            
            offset = (idx - num_algorithms/2) * width + width/2
            
            # 顏色選擇
            if algo['category'] == 'baseline':
                color = 'coral'
            elif algo['category'] == 'hierarchical_dijkstra':
                grid_deg = algo.get('grid_deg', 15)
                intensity = 0.4 + (grid_deg / 30.0) * 0.6
                color = plt.cm.Blues(intensity)
            else:
                grid_deg = algo.get('grid_deg', 15)
                intensity = 0.4 + (grid_deg / 30.0) * 0.6
                color = plt.cm.Greens(intensity)
            
            bars = ax.bar(x + offset, counts, width,
                         label=algo['name'],
                         color=color,
                         alpha=0.85,
                         edgecolor='black',
                         linewidth=0.5)
            
            # 添加數值標籤（只在算法數量較少時）
            if num_algos <= 6:
                for bar, count in zip(bars, counts):
                    if count > 0:
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2., height,
                               f'{int(count)}',
                               ha='center', va='bottom', fontsize=7, fontweight='bold')
        
        ax.set_title('Event Count Comparison by Type', fontsize=15, fontweight='bold')
        ax.set_xlabel('Event Type', fontsize=13, fontweight='bold')
        ax.set_ylabel('Event Count', fontsize=13, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(all_event_types, rotation=45, ha='right', fontsize=11)
        
        # 優化圖例
        if num_algos > 8:
            ax.legend(loc='upper right', fontsize=8, ncol=2, framealpha=0.9)
        else:
            ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
        
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        plt.tight_layout()
        chart_file = output_path / "multi_chart3_event_type_distribution.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  📊 圖表3已保存: {chart_file.name}")
    
    def _chart4_improvement_multi(self, algorithms_data, output_path):
        """圖表4: 相對基線的改進百分比"""
        # 找基線
        baseline_bytes = None
        for algo in algorithms_data:
            if algo['category'] == 'baseline':
                baseline_bytes = algo['data']['summary']['total_bytes']
                break
        
        if baseline_bytes is None or baseline_bytes == 0:
            print("  ⚠️  找不到基線數據，跳過圖表4")
            return
        
        names = []
        improvements = []
        colors_list = []
        grid_degs = []
        
        for algo in algorithms_data:
            if algo['category'] == 'baseline':
                continue  # 跳過基線本身
            
            algo_bytes = algo['data']['summary']['total_bytes']
            improvement = ((baseline_bytes - algo_bytes) / baseline_bytes * 100)
            
            names.append(algo['name'])
            improvements.append(improvement)
            grid_degs.append(algo.get('grid_deg', None))
            
            # 顏色根據改進程度
            if improvement > 0:
                colors_list.append('green')
            else:
                colors_list.append('red')
        
        if not names:
            print("  ⚠️  沒有可比較的算法，跳過圖表4")
            return
        
        num_algos = len(names)
        fig_width = max(12, num_algos * 0.8)
        fig, ax = plt.subplots(figsize=(fig_width, 8))
        
        bars = ax.bar(range(len(names)), improvements, color=colors_list, alpha=0.75, 
                     edgecolor='black', linewidth=0.8)
        
        ax.set_title('Improvement Relative to Floyd-Warshall Baseline', fontsize=15, fontweight='bold')
        ax.set_ylabel('Improvement Percentage (%)', fontsize=13, fontweight='bold')
        ax.set_xlabel('Algorithm', fontsize=13, fontweight='bold')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
        ax.set_xticks(range(len(names)))
        
        # 優化 x 軸標籤
        if num_algos > 6:
            ax.set_xticklabels(names, rotation=60, ha='right', fontsize=9)
        else:
            ax.set_xticklabels(names, rotation=45, ha='right', fontsize=10)
        
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 添加數值標籤
        for bar, improvement, grid_deg in zip(bars, improvements, grid_degs):
            height = bar.get_height()
            va = 'bottom' if height >= 0 else 'top'
            offset = 1 if height >= 0 else -1
            
            label_text = f'{height:.1f}%'
            
            ax.text(bar.get_x() + bar.get_width()/2., height + offset,
                   label_text, ha='center', va=va,
                   fontsize=9, fontweight='bold')
        
        plt.tight_layout()
        chart_file = output_path / "multi_chart4_improvement_percentage.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  📊 圖表4已保存: {chart_file.name}")

def main():
    analyzer = MultiAlgorithmAnalyzer()
    
    print("\n" + "="*60)
    print("Hypatia 多算法控制信令統計分析工具")
    print("="*60 + "\n")
    
    try:
        output_dir = analyzer.analyze_all()
        
        if output_dir:
            print(f"\n🎉 分析完成！")
            print(f"結果保存在: {output_dir}/")
            print(f"  - multi_algorithm_comparison_report.txt (詳細比較報告)")
            print(f"  - multi_chart1_overall_comparison.png (總體比較)")
            print(f"  - multi_chart2_timeline_analysis.png (時間軸分析)")
            print(f"  - multi_chart3_event_type_distribution.png (事件類型分佈)")
            print(f"  - multi_chart4_improvement_percentage.png (相對改進)")
        
    except Exception as e:
        print(f"❌ 分析過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
