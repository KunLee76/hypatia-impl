#!/usr/bin/env python3
"""
Hypatia 控制信令統計分析工具
專門用於分析 algorithm_hierarchical_virtual_pid 和 algorithm_free_one_only_over_isls_with_stats 的控制信令開銷

使用方法：
1. 運行兩個算法生成統計文件
2. 使用此腳本進行分析和比較

作者：基於原有的分析腳本整合而成
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys
from datetime import datetime
import numpy as np

class HypatiaSignalingAnalyzer:
    def __init__(self, stats_dir="paper/satellite_networks_state"):
        self.stats_dir = Path(stats_dir)
        self.hierarchical_file = self.stats_dir / "hierarchical_pid_signaling_stats.json"
        self.baseline_file = self.stats_dir / "baseline_floyd_warshall_signaling_stats.json"
    
    def load_stats(self, file_path):
        """加載統計數據"""
        if not file_path.exists():
            raise FileNotFoundError(f"找不到統計文件: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data
    
    def analyze_and_compare(self, output_dir="signaling_analysis_results"):
        """分析並比較兩個算法"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # 加載數據
        print("正在加載統計數據...")
        hierarchical_data = self.load_stats(self.hierarchical_file)
        baseline_data = self.load_stats(self.baseline_file)
        
        print(f"Hierarchical PID 數據: {len(hierarchical_data.get('timeline', []))} 個事件")
        print(f"Floyd-Warshall 基線數據: {len(baseline_data.get('timeline', []))} 個事件")
        
        # 生成比較報告
        self.generate_comparison_report(hierarchical_data, baseline_data, output_path)
        
        # 生成可視化圖表
        self.generate_visualization(hierarchical_data, baseline_data, output_path)
        
        return output_path
    
    def generate_comparison_report(self, hierarchical_data, baseline_data, output_path):
        """生成詳細比較報告"""
        h_summary = hierarchical_data['summary']
        b_summary = baseline_data['summary']
        
        report_file = output_path / "signaling_comparison_report.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("Hypatia 控制信令算法比較報告\n")
            f.write("=" * 50 + "\n")
            f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("算法概況:\n")
            f.write("-" * 30 + "\n")
            f.write(f"Hierarchical Virtual PID:\n")
            f.write(f"  總事件數: {h_summary['total_events']:,}\n")
            f.write(f"  總字節數: {h_summary['total_bytes']:,}\n")
            
            f.write(f"\nFloyd-Warshall 基線:\n")
            f.write(f"  總事件數: {b_summary['total_events']:,}\n")
            f.write(f"  總字節數: {b_summary['total_bytes']:,}\n")
            
            # 計算改進
            if b_summary['total_bytes'] > 0:
                bytes_saved = b_summary['total_bytes'] - h_summary['total_bytes']
                improvement_pct = (bytes_saved / b_summary['total_bytes']) * 100
                
                f.write(f"\n性能改進:\n")
                f.write("-" * 30 + "\n")
                f.write(f"字節數節省: {bytes_saved:,} ({improvement_pct:.1f}%)\n")
                
                if improvement_pct > 0:
                    f.write(f"🎉 Hierarchical PID 算法節省了 {improvement_pct:.1f}% 的控制開銷！\n")
                else:
                    f.write(f"⚠️ Hierarchical PID 算法增加了 {abs(improvement_pct):.1f}% 的控制開銷\n")
            
            # 按事件類型分析
            f.write(f"\n按事件類型分析:\n")
            f.write("-" * 30 + "\n")
            
            for algo_name, data in [("Hierarchical PID", hierarchical_data), ("Floyd-Warshall", baseline_data)]:
                f.write(f"\n{algo_name}:\n")
                if 'by_type' in data['summary']:
                    for event_type, stats in data['summary']['by_type'].items():
                        f.write(f"  {event_type}: {stats['count']} 事件, {stats['bytes']} 字節\n")
        
        print(f"比較報告已保存到: {report_file}")
    
    def generate_visualization(self, hierarchical_data, baseline_data, output_path):
        """生成可視化圖表"""
        # Use default font (no need for Chinese font configuration)
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Hypatia Control Signaling Overhead Analysis', fontsize=16)
        
        h_summary = hierarchical_data['summary']
        b_summary = baseline_data['summary']
        
        # Chart 1: Overall Comparison
        ax1 = axes[0, 0]
        algorithms = ['Hierarchical PID', 'Floyd-Warshall']
        total_bytes = [h_summary['total_bytes'], b_summary['total_bytes']]
        total_events = [h_summary['total_events'], b_summary['total_events']]
        
        x = np.arange(len(algorithms))
        width = 0.35
        
        ax1_twin = ax1.twinx()
        bars1 = ax1.bar(x - width/2, total_bytes, width, label='Total Bytes', alpha=0.8, color='skyblue')
        bars2 = ax1_twin.bar(x + width/2, total_events, width, label='Total Events', alpha=0.8, color='lightcoral')
        
        ax1.set_xlabel('Algorithm')
        ax1.set_ylabel('Total Bytes', color='blue')
        ax1_twin.set_ylabel('Total Events', color='red')
        ax1.set_title('Control Signaling Total Overhead Comparison')
        ax1.set_xticks(x)
        ax1.set_xticklabels(algorithms)
        
        # Combine legends from both axes and display on the right
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_twin.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        
        # 添加數值標籤
        for bar, value in zip(bars1, total_bytes):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(total_bytes)*0.01,
                    f'{value:,}', ha='center', va='bottom')
        
        for bar, value in zip(bars2, total_events):
            ax1_twin.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(total_events)*0.01,
                         f'{value:,}', ha='center', va='bottom')
        
        # Chart 2: Timeline Analysis
        ax2 = axes[0, 1]
        
        # 轉換時間軸數據
        for algo_name, data, color in [
            ('Hierarchical PID', hierarchical_data, 'blue'),
            ('Floyd-Warshall', baseline_data, 'red')
        ]:
            timeline = data.get('timeline', [])
            if timeline:
                df = pd.DataFrame(timeline)
                if not df.empty and 'time_ms' in df.columns and 'bytes' in df.columns:
                    df_sorted = df.sort_values('time_ms')
                    cumulative_bytes = df_sorted['bytes'].cumsum()
                    ax2.plot(df_sorted['time_ms']/1000, cumulative_bytes, 
                            label=algo_name, color=color, linewidth=2)
        
        ax2.set_title('Cumulative Control Overhead Over Time')
        ax2.set_xlabel('Time (seconds)')
        ax2.set_ylabel('Cumulative Bytes')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Chart 3: Event Type Distribution
        ax3 = axes[1, 0]
        
        # 收集所有事件類型
        all_event_types = set()
        h_by_type = h_summary.get('by_type', {})
        b_by_type = b_summary.get('by_type', {})
        
        all_event_types.update(h_by_type.keys())
        all_event_types.update(b_by_type.keys())
        all_event_types = sorted(list(all_event_types))
        
        if all_event_types:
            x = np.arange(len(all_event_types))
            width = 0.35
            
            h_counts = [h_by_type.get(et, {}).get('count', 0) for et in all_event_types]
            b_counts = [b_by_type.get(et, {}).get('count', 0) for et in all_event_types]
            
            ax3.bar(x - width/2, h_counts, width, label='Hierarchical PID', alpha=0.8)
            ax3.bar(x + width/2, b_counts, width, label='Floyd-Warshall', alpha=0.8)
            
            ax3.set_title('Event Count Comparison by Type')
            ax3.set_xlabel('Event Type')
            ax3.set_ylabel('Event Count')
            ax3.set_xticks(x)
            ax3.set_xticklabels(all_event_types, rotation=45, ha='right')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, 'No Event Type Data', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Event Count Comparison by Type')
        
        # Chart 4: Improvement Percentage
        ax4 = axes[1, 1]
        
        if b_summary['total_bytes'] > 0:
            improvement_pct = ((b_summary['total_bytes'] - h_summary['total_bytes']) / 
                             b_summary['total_bytes'] * 100)
            
            colors = ['green' if improvement_pct > 0 else 'red']
            # Make the bar narrower by setting width parameter and positioning
            bars = ax4.bar([0], [improvement_pct], 
                          color=colors, alpha=0.7, width=0.3)
            
            ax4.set_title('Hierarchical PID Relative Improvement')
            ax4.set_ylabel('Improvement Percentage (%)')
            ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            
            # Set x-axis limits to make the bar appear narrower
            ax4.set_xlim(-1, 1)
            ax4.set_xticks([0])
            ax4.set_xticklabels(['Control Overhead\nImprovement'])
            
            # Set y-axis limit to 90% to make the bar appear shorter
            ax4.set_ylim(0, 90)
            
            # 添加數值標籤
            for bar in bars:
                height = bar.get_height()
                ax4.text(bar.get_x() + bar.get_width()/2., height + 2,
                        f'{height:.1f}%', ha='center', va='bottom')
        else:
            ax4.text(0.5, 0.5, 'Cannot Calculate Improvement Ratio', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('Hierarchical PID Relative Improvement')
        
        plt.tight_layout()
        
        # 保存圖表
        chart_file = output_path / "signaling_analysis_charts.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"可視化圖表已保存到: {chart_file}")

def main():
    analyzer = HypatiaSignalingAnalyzer()
    
    print("Hypatia 控制信令統計分析工具")
    print("=" * 40)
    
    try:
        # 檢查統計文件是否存在
        if not analyzer.hierarchical_file.exists():
            print(f"❌ 找不到 Hierarchical PID 統計文件: {analyzer.hierarchical_file}")
            print("   請先運行: python main_starlink_550.py 10 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_pid 10")
            return
        
        if not analyzer.baseline_file.exists():
            print(f"❌ 找不到 Floyd-Warshall 統計文件: {analyzer.baseline_file}")
            print("   請先運行: python main_starlink_550.py 10 100 isls_plus_grid ground_stations_top_100 algorithm_free_one_only_over_isls_with_stats 10")
            return
        
        print("✅ 找到所需的統計文件，開始分析...")
        
        # 執行分析
        output_dir = analyzer.analyze_and_compare()
        
        print(f"\n🎉 分析完成！")
        print(f"結果保存在: {output_dir}/")
        print(f"  - signaling_comparison_report.txt (詳細比較報告)")
        print(f"  - signaling_analysis_charts.png (可視化圖表)")
        
    except Exception as e:
        print(f"❌ 分析過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()