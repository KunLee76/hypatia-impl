#!/usr/bin/env python3
"""
ISL 失效場景控制信令比較分析工具
專門用於比較不同失效等級下的控制信令開銷

使用方法：
python analyze_failure_scenarios.py
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np
from datetime import datetime

# 設置中文字體
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")

# ===== 統一的控制信令字節模型（與其他分析腳本相同）=====
CTRL_HDR_BYTES = 32
ROUTE_ENTRY_BYTES = 32
PHYS_TOPO_ENTRY_BYTES = 32
GROUP_TOPO_ENTRY_BYTES = 32
ID_ENTRY_BYTES = 32
GATEWAY_ENTRY_BYTES = 32
NORMALIZE_BYTES = True


class FailureScenarioAnalyzer:
    def __init__(self, stats_dir="paper/satellite_networks_state/analytic_result"):
        self.stats_dir = Path(stats_dir)
        self.output_dir = Path("k_parameter_analysis")
        self.output_dir.mkdir(exist_ok=True)
        
        # 定義場景和 K 值
        self.scenarios = ['baseline', 'l1', 'l2', 'l3', 'l4']
        self.k_values = [1, 2, 4, 6, 8, 999]
        
        # 場景描述
        self.scenario_labels = {
            'baseline': 'Baseline (No Failure)',
            'l1': 'L1 (1 ISL Failed)',
            'l2': 'L2 (2 ISLs Failed)',
            'l3': 'L3 (3 ISLs Failed)',
            'l4': 'L4 (4 ISLs Failed)'
        }
        
    def find_all_stats_files(self):
        """查找所有失效場景的統計文件"""
        files = {}
        
        for k in self.k_values:
            files[k] = {}
            for scenario in self.scenarios:
                if scenario == 'baseline':
                    # baseline 使用原本的文件名格式
                    file_path = self.stats_dir / f"hierarchical_gid_27deg_k{k}_signaling_stats.json"
                else:
                    # 失效場景使用新的文件名格式
                    file_path = self.stats_dir / f"hierarchical_gid_27deg_failure_{scenario}_k{k}_signaling_stats.json"
                
                if file_path.exists():
                    files[k][scenario] = str(file_path)
                    print(f"✓ 找到 K={k}, {scenario}: {file_path.name}")
                else:
                    print(f"✗ 缺少 K={k}, {scenario}: {file_path.name}")
        
        return files
    
    def load_stats(self, file_path):
        """加載統計數據並重新計算字節數"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if NORMALIZE_BYTES:
            self._normalize_control_bytes(data)
        
        return data
    
    def _normalize_control_bytes(self, data: dict):
        """重新計算字節數（使用統一的 header+entry 模型）"""
        summary = data.get('summary', {})
        timeline = data.get('timeline', [])
        
        # 備份原始值
        if 'raw_total_bytes' not in summary:
            summary['raw_total_bytes'] = summary.get('total_bytes', 0)
        
        # 重新計算
        norm_total_bytes = 0
        norm_by_type = {k: {'count': v.get('count', 0), 'bytes': 0} 
                       for k, v in summary.get('by_type', {}).items()}
        
        for row in timeline:
            ev = row.get('event') or row.get('type')
            if not ev:
                continue
            
            detail = row.get('detail') or {}
            msg_count = int(row.get('count', 1) or 1)
            
            # 根據事件類型計算字節數
            if ev == 'routing_update':
                n_entries = int(detail.get('changed_entries', 0) or 0)
                entry_bytes = ROUTE_ENTRY_BYTES
                norm_bytes = CTRL_HDR_BYTES + n_entries * entry_bytes
                
            elif ev == 'topology_change':
                n_entries = abs(int(detail.get('delta_isl', 0) or 0)) + abs(int(detail.get('delta_gsl', 0) or 0))
                entry_bytes = PHYS_TOPO_ENTRY_BYTES
                norm_bytes = CTRL_HDR_BYTES + n_entries * entry_bytes
                
            elif ev == 'gid_rebuild':
                n_entries = int(detail.get('changed_gids', 0) or 0)
                entry_bytes = ID_ENTRY_BYTES
                norm_bytes = CTRL_HDR_BYTES + n_entries * entry_bytes
                
            elif ev == 'gateway_update':
                n_msgs = int(detail.get('num_messages', 0) or 0)
                n_entries = int(detail.get('num_entries', 0) or 0)
                
                if n_msgs == 0 and n_entries == 0:
                    changed_pairs = int(detail.get('changed_pairs', 0) or 0)
                    k = int(detail.get('k', 0) or detail.get('k_used', 0) or 0)
                    n_msgs = changed_pairs
                    n_entries = changed_pairs * max(k, 1)
                
                norm_bytes = n_msgs * CTRL_HDR_BYTES + n_entries * GATEWAY_ENTRY_BYTES
                
            else:
                norm_bytes = int(row.get('bytes', 0) or 0)
            
            # 更新
            row['bytes'] = norm_bytes
            norm_total_bytes += norm_bytes
            
            if ev in norm_by_type:
                norm_by_type[ev]['bytes'] += norm_bytes
            else:
                norm_by_type[ev] = {'count': msg_count, 'bytes': norm_bytes}
        
        # 更新 summary
        summary['total_bytes'] = norm_total_bytes
        summary['by_type'] = norm_by_type
    
    def extract_metrics(self, stats_data):
        """提取關鍵指標"""
        summary = stats_data.get('summary', {})
        by_type = summary.get('by_type', {})
        
        metrics = {
            'total_events': summary.get('total_events', 0),
            'total_bytes': summary.get('total_bytes', 0),
            'routing_updates': 0,
            'routing_bytes': 0,
            'gateway_updates': 0,
            'gateway_bytes': 0,
            'gid_rebuilds': 0,
            'gid_bytes': 0,
            'topology_changes': 0,
            'topology_bytes': 0,
        }
        
        for event_type, event_data in by_type.items():
            count = event_data.get('count', 0)
            bytes_val = event_data.get('bytes', 0)
            
            if event_type == 'routing_update':
                metrics['routing_updates'] = count
                metrics['routing_bytes'] = bytes_val
            elif event_type == 'gateway_update':
                metrics['gateway_updates'] = count
                metrics['gateway_bytes'] = bytes_val
            elif event_type == 'gid_rebuild':
                metrics['gid_rebuilds'] = count
                metrics['gid_bytes'] = bytes_val
            elif event_type == 'topology_change':
                metrics['topology_changes'] = count
                metrics['topology_bytes'] = bytes_val
        
        return metrics
    
    def analyze_all(self):
        """分析所有場景"""
        print("\n" + "="*70)
        print("ISL 失效場景控制信令分析")
        print("="*70 + "\n")
        
        all_files = self.find_all_stats_files()
        
        # 收集所有數據
        all_data = {}
        
        for k in self.k_values:
            all_data[k] = {}
            for scenario in self.scenarios:
                if scenario in all_files[k]:
                    file_path = all_files[k][scenario]
                    stats = self.load_stats(file_path)
                    metrics = self.extract_metrics(stats)
                    metrics['k'] = k
                    metrics['scenario'] = scenario
                    all_data[k][scenario] = metrics
        
        return all_data
    
    def generate_report(self, all_data):
        """生成綜合報告"""
        report_path = self.output_dir / "failure_scenarios_comparison_report.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("ISL 失效場景控制信令比較報告\n")
            f.write("="*80 + "\n")
            f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"實驗配置：Grid Degree = 27°, 模擬時長 = 100 秒\n")
            f.write(f"測試場景：{', '.join(self.scenarios)}\n")
            f.write(f"測試 K 值：{', '.join(map(str, self.k_values))}\n\n")
            
            # 按 K 值分組報告
            for k in self.k_values:
                k_str = "All" if k == 999 else str(k)
                f.write(f"\n{'='*80}\n")
                f.write(f"K = {k_str}\n")
                f.write(f"{'='*80}\n\n")
                
                if k not in all_data or not all_data[k]:
                    f.write("無數據\n")
                    continue
                
                # 總體統計
                f.write("總體控制信令開銷：\n")
                f.write("-"*80 + "\n")
                f.write(f"{'場景':<20} {'總事件數':<12} {'總字節數':<15} {'平均事件開銷':<15}\n")
                f.write("-"*80 + "\n")
                
                baseline_bytes = None
                for scenario in self.scenarios:
                    if scenario in all_data[k]:
                        metrics = all_data[k][scenario]
                        total_events = metrics['total_events']
                        total_bytes = metrics['total_bytes']
                        avg_bytes = total_bytes / total_events if total_events > 0 else 0
                        
                        if scenario == 'baseline':
                            baseline_bytes = total_bytes
                        
                        scenario_label = self.scenario_labels[scenario]
                        f.write(f"{scenario_label:<20} {total_events:<12} {total_bytes:<15,} {avg_bytes:<15.1f}\n")
                
                # 按事件類型詳細統計
                f.write("\n\n按事件類型統計：\n")
                f.write("-"*80 + "\n")
                
                # Gateway Updates
                f.write("\nGateway 更新：\n")
                f.write(f"{'場景':<20} {'次數':<12} {'總字節數':<15} {'平均大小':<15}\n")
                f.write("-"*80 + "\n")
                for scenario in self.scenarios:
                    if scenario in all_data[k]:
                        metrics = all_data[k][scenario]
                        count = metrics['gateway_updates']
                        bytes_val = metrics['gateway_bytes']
                        avg = bytes_val / count if count > 0 else 0
                        scenario_label = self.scenario_labels[scenario]
                        f.write(f"{scenario_label:<20} {count:<12} {bytes_val:<15,} {avg:<15.1f}\n")
                
                # Routing Updates
                f.write("\nRouting 更新：\n")
                f.write(f"{'場景':<20} {'次數':<12} {'總字節數':<15} {'平均大小':<15}\n")
                f.write("-"*80 + "\n")
                for scenario in self.scenarios:
                    if scenario in all_data[k]:
                        metrics = all_data[k][scenario]
                        count = metrics['routing_updates']
                        bytes_val = metrics['routing_bytes']
                        avg = bytes_val / count if count > 0 else 0
                        scenario_label = self.scenario_labels[scenario]
                        f.write(f"{scenario_label:<20} {count:<12} {bytes_val:<15,} {avg:<15.1f}\n")
                
                # GID Rebuilds
                f.write("\nGID 重建：\n")
                f.write(f"{'場景':<20} {'次數':<12} {'總字節數':<15} {'平均大小':<15}\n")
                f.write("-"*80 + "\n")
                for scenario in self.scenarios:
                    if scenario in all_data[k]:
                        metrics = all_data[k][scenario]
                        count = metrics['gid_rebuilds']
                        bytes_val = metrics['gid_bytes']
                        avg = bytes_val / count if count > 0 else 0
                        scenario_label = self.scenario_labels[scenario]
                        f.write(f"{scenario_label:<20} {count:<12} {bytes_val:<15,} {avg:<15.1f}\n")
                
                # 相對於 baseline 的增長百分比
                if baseline_bytes and baseline_bytes > 0:
                    f.write("\n\n相對於 Baseline 的控制信令增長：\n")
                    f.write("-"*80 + "\n")
                    f.write(f"{'場景':<20} {'增長百分比':<15}\n")
                    f.write("-"*80 + "\n")
                    for scenario in self.scenarios:
                        if scenario in all_data[k]:
                            metrics = all_data[k][scenario]
                            increase = ((metrics['total_bytes'] - baseline_bytes) / baseline_bytes) * 100
                            scenario_label = self.scenario_labels[scenario]
                            f.write(f"{scenario_label:<20} {increase:>14.2f}%\n")
        
        print(f"✓ 報告已保存：{report_path}")
        return report_path
    
    def plot_comparisons(self, all_data):
        """繪製比較圖表（為每個失效場景生成一張圖，比較不同 K 值）"""
        for scenario in self.scenarios:
            scenario_label = self.scenario_labels[scenario]
            print(f"\n生成 {scenario_label} 的 K 值比較圖表...")
            
            # 準備數據：收集所有 K 值在此場景下的數據
            k_values_present = []
            metrics_list = []
            
            for k in self.k_values:
                if k in all_data and scenario in all_data[k]:
                    k_values_present.append(k)
                    metrics_list.append(all_data[k][scenario])
            
            if not metrics_list:
                print(f"  ⚠️  {scenario_label} 沒有有效數據")
                continue
            
            # 生成 4 張子圖
            self._generate_scenario_comparison_charts(scenario, scenario_label, k_values_present, metrics_list)
    
    def _generate_scenario_comparison_charts(self, scenario, scenario_label, k_values, metrics_list):
        """為特定失效場景生成比較圖表（比較不同 K 值，4 個子圖）"""
        fig = plt.figure(figsize=(18, 14))
        gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
        
        # 準備標籤和顏色（K 值）
        labels = [f'K={k}' if k != 999 else 'K=All' for k in k_values]
        colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(k_values)))
        
        # === 子圖1：總控制信令開銷（字節） ===
        ax1 = fig.add_subplot(gs[0, 0])
        total_bytes = [m['total_bytes'] / 1e6 for m in metrics_list]
        bars1 = ax1.bar(labels, total_bytes, color=colors, alpha=0.85, edgecolor='black', linewidth=0.5)
        ax1.set_ylabel('Total Signaling (MB)', fontsize=12, fontweight='bold')
        ax1.set_title(f'Total Control Signaling\n({scenario_label})', fontsize=14, fontweight='bold')
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
        
        x = np.arange(len(labels))
        width = 0.25
        
        for i, (event_type, event_label, event_color) in enumerate(zip(event_types, event_labels, event_colors)):
            counts = [m[event_type] for m in metrics_list]
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
        ax2.set_title(f'Event Type Distribution\n({scenario_label})', fontsize=14, fontweight='bold')
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=0, ha='center', fontsize=10)
        ax2.legend(fontsize=10, framealpha=0.9)
        ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # === 子圖3：Gateway 更新開銷 ===
        ax3 = fig.add_subplot(gs[1, 0])
        gateway_bytes = [m['gateway_bytes'] / 1e6 for m in metrics_list]
        bars3 = ax3.bar(labels, gateway_bytes, color='darkorange', alpha=0.85, edgecolor='black', linewidth=0.5)
        ax3.set_ylabel('Gateway Update Signaling (MB)', fontsize=12, fontweight='bold')
        ax3.set_title(f'Gateway Update Overhead\n({scenario_label})', fontsize=14, fontweight='bold')
        ax3.grid(True, alpha=0.3, axis='y', linestyle='--')
        ax3.tick_params(axis='x', rotation=0, labelsize=10)
        
        for bar in bars3:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}',
                   ha='center', va='bottom', fontsize=9)
        
        # === 子圖4：相對於 K=1 的變化百分比 ===
        ax4 = fig.add_subplot(gs[1, 1])
        baseline_bytes = metrics_list[0]['total_bytes']  # K=1 作為基準
        increases = [((m['total_bytes'] - baseline_bytes) / baseline_bytes) * 100 for m in metrics_list]
        bar_colors = ['green' if x <= 0 else 'skyblue' for x in increases]
        bars4 = ax4.bar(labels, increases, color=bar_colors, alpha=0.85, edgecolor='black', linewidth=0.5)
        ax4.set_ylabel('Change vs K=1 (%)', fontsize=12, fontweight='bold')
        ax4.set_title(f'Overhead Change Relative to K=1\n({scenario_label})', fontsize=14, fontweight='bold')
        ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax4.grid(True, alpha=0.3, axis='y', linestyle='--')
        ax4.tick_params(axis='x', rotation=0, labelsize=10)
        
        for bar in bars4:
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}%',
                   ha='center', va='bottom' if height > 0 else 'top', fontsize=9)
        
        plt.suptitle(f'K Parameter Comparison: {scenario_label}', 
                    fontsize=16, fontweight='bold', y=0.995)
        
        # 保存圖表（修改文件名格式）
        scenario_name = scenario.replace('_', '')  # baseline, l1, l2, l3, l4
        output_path = self.output_dir / f"k_comparison_{scenario_name}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  📊 圖表已保存: {output_path.name}")
        plt.close()
    
    def run(self):
        """執行完整分析"""
        all_data = self.analyze_all()
        
        if not all_data:
            print("❌ 無法進行分析")
            return
        
        # 生成報告
        self.generate_report(all_data)
        
        # 繪製圖表
        self.plot_comparisons(all_data)
        
        print("\n" + "="*70)
        print("分析完成！")
        print(f"結果保存在：{self.output_dir}/")
        print("="*70)


if __name__ == "__main__":
    analyzer = FailureScenarioAnalyzer()
    analyzer.run()
