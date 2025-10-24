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
import glob

class HypatiaSignalingAnalyzer:
    def __init__(self, stats_dir="paper/satellite_networks_state/analytic_result"):
        self.stats_dir = Path(stats_dir)
        # 支持自動發現不同網格大小和算法的文件
        self.baseline_file = self.stats_dir / "baseline_floyd_warshall_signaling_stats.json"
    
    def find_hierarchical_files(self):
        """查找所有 Hierarchical GID 統計文件（包括 Floyd-Warshall 和 Dijkstra 版本）"""
        patterns = [
            str(self.stats_dir / "hierarchical_gid_*deg_signaling_stats.json"),
            str(self.stats_dir / "hierarchical_gid_dijkstra_*deg_signaling_stats.json")
        ]
        files = []
        for pattern in patterns:
            files.extend(glob.glob(pattern))
        return sorted(files)
    
    def load_stats(self, file_path):
        """加載統計數據"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"找不到統計文件: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data
    
    def analyze_and_compare(self, hierarchical_file=None, output_dir="signaling_analysis_results"):
        """分析並比較兩個算法"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # 如果沒有指定文件，自動查找
        if hierarchical_file is None:
            hierarchical_files = self.find_hierarchical_files()
            if not hierarchical_files:
                print("❌ 找不到任何 Hierarchical GID 統計文件")
                print("   文件名格式應為: hierarchical_gid_*deg_signaling_stats.json")
                return None
            
            # 使用第一個找到的文件
            hierarchical_file = hierarchical_files[0]
            if len(hierarchical_files) > 1:
                print(f"ℹ️  找到 {len(hierarchical_files)} 個 Hierarchical GID 文件，使用: {Path(hierarchical_file).name}")
        
        # 加載數據
        print("正在加載統計數據...")
        hierarchical_data = self.load_stats(hierarchical_file)
        baseline_data = self.load_stats(self.baseline_file)
        
        # 獲取顯示名稱
        h_name = hierarchical_data.get('algorithm_display_name', 'Hierarchical GID')
        
        print(f"{h_name} 數據: {len(hierarchical_data.get('timeline', []))} 個事件")
        print(f"Floyd-Warshall 基線數據: {len(baseline_data.get('timeline', []))} 個事件")
        
        # 生成比較報告
        self.generate_comparison_report(hierarchical_data, baseline_data, output_path, h_name)
        
        # 生成單獨的可視化圖表
        self.generate_separate_charts(hierarchical_data, baseline_data, output_path, h_name)
        
        return output_path
    
    def generate_comparison_report(self, hierarchical_data, baseline_data, output_path, h_name):
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
            f.write(f"{h_name}:\n")
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
                    f.write(f"🎉 {h_name} 算法節省了 {improvement_pct:.1f}% 的控制開銷！\n")
                else:
                    f.write(f"⚠️ {h_name} 算法增加了 {abs(improvement_pct):.1f}% 的控制開銷\n")
            
            # 按事件類型分析
            f.write(f"\n按事件類型分析:\n")
            f.write("-" * 30 + "\n")
            
            for algo_name, data in [(h_name, hierarchical_data), ("Floyd-Warshall", baseline_data)]:
                f.write(f"\n{algo_name}:\n")
                if 'by_type' in data['summary']:
                    for event_type, stats in data['summary']['by_type'].items():
                        f.write(f"  {event_type}: {stats['count']} 事件, {stats['bytes']} 字節\n")
        
        print(f"比較報告已保存到: {report_file}")
    
    def generate_separate_charts(self, hierarchical_data, baseline_data, output_path, h_name):
        """生成分開的可視化圖表"""
        h_summary = hierarchical_data['summary']
        b_summary = baseline_data['summary']
        
        # Chart 1: Overall Comparison (總體比較)
        self._generate_chart1_overall(h_summary, b_summary, output_path, h_name)
        
        # Chart 2: Timeline Analysis (時間軸分析)
        self._generate_chart2_timeline(hierarchical_data, baseline_data, output_path, h_name)
        
        # Chart 3: Event Type Distribution (事件類型分佈)
        self._generate_chart3_event_types(h_summary, b_summary, output_path, h_name)
        
        # Chart 4: Improvement Percentage (改進百分比)
        self._generate_chart4_improvement(h_summary, b_summary, output_path, h_name)
        
        print(f"✅ 所有圖表已保存到: {output_path}/")
    
    def _generate_chart1_overall(self, h_summary, b_summary, output_path, h_name):
        """圖表1: 總體開銷比較"""
        fig, ax1 = plt.subplots(figsize=(10, 6))
        
        algorithms = [h_name, 'Floyd-Warshall']
        total_bytes = [h_summary['total_bytes'], b_summary['total_bytes']]
        total_events = [h_summary['total_events'], b_summary['total_events']]
        
        x = np.arange(len(algorithms))
        width = 0.35
        
        ax1_twin = ax1.twinx()
        bars1 = ax1.bar(x - width/2, total_bytes, width, label='Total Bytes', alpha=0.8, color='skyblue')
        bars2 = ax1_twin.bar(x + width/2, total_events, width, label='Total Events', alpha=0.8, color='lightcoral')
        
        ax1.set_xlabel('Algorithm', fontsize=12)
        ax1.set_ylabel('Total Bytes', color='blue', fontsize=12)
        ax1_twin.set_ylabel('Total Events', color='red', fontsize=12)
        ax1.set_title('Control Signaling Total Overhead Comparison', fontsize=14, fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(algorithms)
        
        # 合併圖例
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_twin.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        
        # 添加數值標籤
        for bar, value in zip(bars1, total_bytes):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(total_bytes)*0.01,
                    f'{value:,}', ha='center', va='bottom', fontsize=10)
        
        for bar, value in zip(bars2, total_events):
            ax1_twin.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(total_events)*0.01,
                         f'{value:,}', ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        chart_file = output_path / "chart1_overall_comparison.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  📊 圖表1已保存: {chart_file.name}")
    
    def _generate_chart2_timeline(self, hierarchical_data, baseline_data, output_path, h_name):
        """圖表2: 時間軸分析"""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        for algo_name, data, color in [
            (h_name, hierarchical_data, 'blue'),
            ('Floyd-Warshall', baseline_data, 'red')
        ]:
            timeline = data.get('timeline', [])
            if timeline:
                df = pd.DataFrame(timeline)
                if not df.empty and 'time_ms' in df.columns and 'bytes' in df.columns:
                    df_sorted = df.sort_values('time_ms')
                    cumulative_bytes = df_sorted['bytes'].cumsum()
                    ax.plot(df_sorted['time_ms']/1000, cumulative_bytes, 
                           label=algo_name, color=color, linewidth=2)
        
        ax.set_title('Cumulative Control Overhead Over Time', fontsize=14, fontweight='bold')
        ax.set_xlabel('Time (seconds)', fontsize=12)
        ax.set_ylabel('Cumulative Bytes', fontsize=12)
        ax.legend(loc='upper right', fontsize=11)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        chart_file = output_path / "chart2_timeline_analysis.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  📊 圖表2已保存: {chart_file.name}")
    
    def _generate_chart3_event_types(self, h_summary, b_summary, output_path, h_name):
        """圖表3: 事件類型分佈 (帶數值標籤)"""
        fig, ax = plt.subplots(figsize=(12, 7))
        
        h_by_type = h_summary.get('by_type', {})
        b_by_type = b_summary.get('by_type', {})
        
        all_event_types = set()
        all_event_types.update(h_by_type.keys())
        all_event_types.update(b_by_type.keys())
        all_event_types = sorted(list(all_event_types))
        
        if all_event_types:
            x = np.arange(len(all_event_types))
            width = 0.35
            
            h_counts = [h_by_type.get(et, {}).get('count', 0) for et in all_event_types]
            b_counts = [b_by_type.get(et, {}).get('count', 0) for et in all_event_types]
            
            bars1 = ax.bar(x - width/2, h_counts, width, label=h_name, alpha=0.8, color='steelblue')
            bars2 = ax.bar(x + width/2, b_counts, width, label='Floyd-Warshall', alpha=0.8, color='coral')
            
            # 為每個柱子添加數值標籤
            for bars, counts in [(bars1, h_counts), (bars2, b_counts)]:
                for bar, count in zip(bars, counts):
                    if count > 0:  # 只顯示非零值
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2., height,
                               f'{int(count)}',
                               ha='center', va='bottom', fontsize=9, fontweight='bold')
            
            ax.set_title('Event Count Comparison by Type', fontsize=14, fontweight='bold')
            ax.set_xlabel('Event Type', fontsize=12)
            ax.set_ylabel('Event Count', fontsize=12)
            ax.set_xticks(x)
            ax.set_xticklabels(all_event_types, rotation=45, ha='right')
            ax.legend(loc='upper right', fontsize=11)
            ax.grid(True, alpha=0.3, axis='y')
            
            # 調整 y 軸範圍以便看清標籤
            max_count = max(max(h_counts) if h_counts else 0, max(b_counts) if b_counts else 0)
            ax.set_ylim(0, max_count * 1.15)
        else:
            ax.text(0.5, 0.5, 'No Event Type Data', ha='center', va='center', 
                   transform=ax.transAxes, fontsize=14)
            ax.set_title('Event Count Comparison by Type', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        chart_file = output_path / "chart3_event_type_distribution.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  📊 圖表3已保存: {chart_file.name}")
    
    def _generate_chart4_improvement(self, h_summary, b_summary, output_path, h_name):
        """圖表4: 改進百分比"""
        fig, ax = plt.subplots(figsize=(8, 6))
        
        if b_summary['total_bytes'] > 0:
            improvement_pct = ((b_summary['total_bytes'] - h_summary['total_bytes']) / 
                             b_summary['total_bytes'] * 100)
            
            colors = ['green' if improvement_pct > 0 else 'red']
            bars = ax.bar([0], [improvement_pct], 
                         color=colors, alpha=0.7, width=0.3)
            
            ax.set_title(f'{h_name} Relative Improvement', fontsize=14, fontweight='bold')
            ax.set_ylabel('Improvement Percentage (%)', fontsize=12)
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            
            ax.set_xlim(-1, 1)
            ax.set_xticks([0])
            ax.set_xticklabels(['Control Overhead\nImprovement'])
            ax.set_ylim(0, 90)
            
            # 添加數值標籤
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                       f'{height:.1f}%', ha='center', va='bottom', 
                       fontsize=12, fontweight='bold')
        else:
            ax.text(0.5, 0.5, 'Cannot Calculate Improvement Ratio', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=14)
            ax.set_title(f'{h_name} Relative Improvement', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        chart_file = output_path / "chart4_improvement_percentage.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  📊 圖表4已保存: {chart_file.name}")

def main():
    analyzer = HypatiaSignalingAnalyzer()
    
    print("Hypatia 控制信令統計分析工具")
    print("=" * 40)
    
    try:
        # 檢查基線文件是否存在
        if not analyzer.baseline_file.exists():
            print(f"❌ 找不到 Floyd-Warshall 統計文件: {analyzer.baseline_file}")
            print("   請先運行: python main_25x25_fast.py algorithm_free_one_only_over_isls_with_stats")
            return
        
        # 查找 Hierarchical GID 文件
        hierarchical_files = analyzer.find_hierarchical_files()
        if not hierarchical_files:
            print("❌ 找不到任何 Hierarchical GID 統計文件")
            print("   文件名格式應為: hierarchical_gid_*deg_signaling_stats.json")
            print("   請先運行: python main_25x25_fast.py algorithm_hierarchical_virtual_pid")
            return
        
        # 顯示找到的文件
        print(f"\n✅ 找到 {len(hierarchical_files)} 個 Hierarchical GID 統計文件:")
        for idx, file_path in enumerate(hierarchical_files, 1):
            file_name = Path(file_path).name
            # 嘗試從文件中讀取顯示名稱
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                display_name = data.get('algorithm_display_name', file_name)
                print(f"  {idx}. {file_name} ({display_name})")
            except:
                print(f"  {idx}. {file_name}")
        
        # 詢問用戶選擇
        print("\n請選擇分析模式:")
        print("  [0] 分析所有文件（生成多個報告）")
        print("  [1-N] 分析指定的單個文件")
        print("  [Enter] 分析第一個文件（默認）")
        
        try:
            choice = input("\n您的選擇: ").strip()
            
            if choice == "0":
                # 分析所有文件
                print(f"\n開始分析所有 {len(hierarchical_files)} 個文件...")
                for idx, h_file in enumerate(hierarchical_files, 1):
                    file_name = Path(h_file).stem  # 不含擴展名的文件名
                    output_dir_name = f"signaling_analysis_{file_name}"
                    
                    print(f"\n{'='*60}")
                    print(f"正在分析 [{idx}/{len(hierarchical_files)}]: {Path(h_file).name}")
                    print(f"{'='*60}")
                    
                    output_dir = analyzer.analyze_and_compare(
                        hierarchical_file=h_file,
                        output_dir=output_dir_name
                    )
                    
                    if output_dir:
                        print(f"✅ 結果已保存到: {output_dir}/")
                
                print(f"\n🎉 所有分析完成！共生成 {len(hierarchical_files)} 個報告。")
                
            elif choice.isdigit() and 1 <= int(choice) <= len(hierarchical_files):
                # 分析指定的單個文件
                selected_idx = int(choice) - 1
                selected_file = hierarchical_files[selected_idx]
                
                print(f"\n開始分析: {Path(selected_file).name}")
                
                output_dir = analyzer.analyze_and_compare(
                    hierarchical_file=selected_file,
                    output_dir="signaling_analysis_results"
                )
                
                if output_dir:
                    print(f"\n🎉 分析完成！")
                    print(f"結果保存在: {output_dir}/")
                    print(f"  - signaling_comparison_report.txt (詳細比較報告)")
                    print(f"  - chart1_overall_comparison.png (總體比較)")
                    print(f"  - chart2_timeline_analysis.png (時間軸分析)")
                    print(f"  - chart3_event_type_distribution.png (事件類型分佈)")
                    print(f"  - chart4_improvement_percentage.png (改進百分比)")
            
            else:
                # 默認：分析第一個文件
                print(f"\n使用默認模式，分析第一個文件: {Path(hierarchical_files[0]).name}")
                
                output_dir = analyzer.analyze_and_compare()
                
                if output_dir:
                    print(f"\n🎉 分析完成！")
                    print(f"結果保存在: {output_dir}/")
                    print(f"  - signaling_comparison_report.txt (詳細比較報告)")
                    print(f"  - chart1_overall_comparison.png (總體比較)")
                    print(f"  - chart2_timeline_analysis.png (時間軸分析)")
                    print(f"  - chart3_event_type_distribution.png (事件類型分佈)")
                    print(f"  - chart4_improvement_percentage.png (改進百分比)")
        
        except KeyboardInterrupt:
            print("\n\n⚠️  用戶取消操作")
            return
        
    except Exception as e:
        print(f"❌ 分析過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()