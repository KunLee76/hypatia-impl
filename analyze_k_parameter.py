#!/usr/bin/env python3
"""
K 參數實驗控制信令比較分析工具
專門用於比較不同 K_BEST_GATEWAYS 值的控制信令開銷
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np

# 設置中文字體
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")

# ===== 統一的控制信令字節模型（與 hypatia_multi_algorithm_analyzer 相同）=====
CTRL_HDR_BYTES = 32  # OSPFv3-like core (16B) + satellite extension (16B)
ROUTE_ENTRY_BYTES = 32
PHYS_TOPO_ENTRY_BYTES = 32
GROUP_TOPO_ENTRY_BYTES = 32
ID_ENTRY_BYTES = 32
GATEWAY_ENTRY_BYTES = 32
NORMALIZE_BYTES = True

class KParameterAnalyzer:
    def __init__(self, stats_dir="paper/satellite_networks_state/analytic_result"):
        self.stats_dir = Path(stats_dir)
        self.output_dir = Path("k_parameter_analysis")
        self.output_dir.mkdir(exist_ok=True)
        
    def find_k_stats_files(self):
        """查找所有 K 值的統計文件"""
        k_values = [1, 2, 4, 6, 8, 999]
        files = {}
        
        for k in k_values:
            file_path = self.stats_dir / f"hierarchical_gid_27deg_k{k}_signaling_stats.json"
            if file_path.exists():
                files[k] = str(file_path)
                print(f"✓ 找到 K={k}: {file_path.name}")
            else:
                print(f"✗ 缺少 K={k}: {file_path.name}")
        
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
            n_entries = 0
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
                # gateway_update 使用多訊息模型：每對 GID 一個訊息
                n_msgs = int(detail.get('num_messages', 0) or 0)
                n_entries = int(detail.get('num_entries', 0) or 0)
                
                # fallback：從 changed_pairs 和 k 推導
                if n_msgs == 0 and n_entries == 0:
                    changed_pairs = int(detail.get('changed_pairs', 0) or 0)
                    k = int(detail.get('k', 0) or detail.get('k_used', 0) or 0)
                    n_msgs = changed_pairs
                    n_entries = changed_pairs * max(k, 1)
                
                norm_bytes = n_msgs * CTRL_HDR_BYTES + n_entries * GATEWAY_ENTRY_BYTES
                
            else:
                # 未知事件：保留原始字節數
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
        }
        
        # 提取各類事件統計
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
        
        return metrics
    
    def analyze_all_k_values(self):
        """分析所有 K 值"""
        print("\n" + "="*60)
        print("K 參數實驗控制信令分析")
        print("="*60 + "\n")
        
        k_files = self.find_k_stats_files()
        
        if not k_files:
            print("❌ 未找到任何 K 值的統計文件！")
            return None
        
        print(f"\n找到 {len(k_files)} 個 K 值的統計數據\n")
        
        # 收集所有數據
        results = []
        for k in sorted(k_files.keys()):
            file_path = k_files[k]
            stats = self.load_stats(file_path)
            metrics = self.extract_metrics(stats)
            metrics['k'] = k
            results.append(metrics)
        
        df = pd.DataFrame(results)
        df = df.sort_values('k')
        
        return df
    
    def generate_report(self, df):
        """生成文字報告"""
        report_path = self.output_dir / "k_parameter_comparison_report.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("K_BEST_GATEWAYS 參數實驗比較報告\n")
            f.write("="*70 + "\n")
            f.write(f"實驗配置：Grid Degree = 27°, 模擬時長 = 20 秒\n")
            f.write(f"測試 K 值：{', '.join(map(str, df['k'].tolist()))}\n\n")
            
            f.write("總體統計：\n")
            f.write("-"*70 + "\n")
            f.write(f"{'K 值':<8} {'總事件數':<12} {'總字節數':<15} {'平均事件開銷':<15}\n")
            f.write("-"*70 + "\n")
            
            for _, row in df.iterrows():
                k = row['k']
                total_events = row['total_events']
                total_bytes = row['total_bytes']
                avg_bytes = total_bytes / total_events if total_events > 0 else 0
                
                k_str = "All" if k == 999 else str(k)
                f.write(f"{k_str:<8} {total_events:<12} {total_bytes:<15,} {avg_bytes:<15.1f}\n")
            
            f.write("\n\n按事件類型詳細統計：\n")
            f.write("="*70 + "\n")
            
            # Gateway Updates
            f.write("\nGateway 更新：\n")
            f.write("-"*70 + "\n")
            f.write(f"{'K 值':<8} {'次數':<12} {'總字節數':<15} {'平均大小':<15}\n")
            f.write("-"*70 + "\n")
            for _, row in df.iterrows():
                k_str = "All" if row['k'] == 999 else str(row['k'])
                count = row['gateway_updates']
                bytes_val = row['gateway_bytes']
                avg = bytes_val / count if count > 0 else 0
                f.write(f"{k_str:<8} {count:<12} {bytes_val:<15,} {avg:<15.1f}\n")
            
            # Routing Updates
            f.write("\nRouting 更新：\n")
            f.write("-"*70 + "\n")
            f.write(f"{'K 值':<8} {'次數':<12} {'總字節數':<15} {'平均大小':<15}\n")
            f.write("-"*70 + "\n")
            for _, row in df.iterrows():
                k_str = "All" if row['k'] == 999 else str(row['k'])
                count = row['routing_updates']
                bytes_val = row['routing_bytes']
                avg = bytes_val / count if count > 0 else 0
                f.write(f"{k_str:<8} {count:<12} {bytes_val:<15,} {avg:<15.1f}\n")
            
            # GID Rebuilds
            f.write("\nGID 重建：\n")
            f.write("-"*70 + "\n")
            f.write(f"{'K 值':<8} {'次數':<12} {'總字節數':<15} {'平均大小':<15}\n")
            f.write("-"*70 + "\n")
            for _, row in df.iterrows():
                k_str = "All" if row['k'] == 999 else str(row['k'])
                count = row['gid_rebuilds']
                bytes_val = row['gid_bytes']
                avg = bytes_val / count if count > 0 else 0
                f.write(f"{k_str:<8} {count:<12} {bytes_val:<15,} {avg:<15.1f}\n")
        
        print(f"✓ 報告已保存：{report_path}")
        return report_path
    
    def plot_comparisons(self, df):
        """繪製比較圖表（生成多個獨立圖表）"""
        # 準備 K 值標籤（999 顯示為 "All"）
        df_plot = df.copy()
        df_plot['k_label'] = df_plot['k'].apply(lambda x: 'All' if x == 999 else str(x))
        
        # === 圖表1：總控制信令開銷 ===
        self._chart1_total_overhead(df_plot)
        
        # === 圖表2：Gateway 更新開銷（K 參數實驗重點）===
        self._chart2_gateway_overhead(df_plot)
        
        # === 圖表3：事件類型分佈 ===
        self._chart3_event_distribution(df_plot)
        
        # === 圖表4：改善百分比 ===
        self._chart4_improvement(df_plot)
    
    def _chart1_total_overhead(self, df_plot):
        """圖表1：總控制信令開銷（字節數 + 事件數）"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # 左圖：總字節數
        bars1 = ax1.bar(df_plot['k_label'], df_plot['total_bytes'] / 1e6, 
                       color='steelblue', alpha=0.85, edgecolor='black', linewidth=0.5)
        ax1.set_xlabel('K Value', fontsize=13, fontweight='bold')
        ax1.set_ylabel('Total Signaling (MB)', fontsize=13, fontweight='bold')
        ax1.set_title('Total Control Signaling Bytes', fontsize=15, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 標註數值
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}',
                   ha='center', va='bottom', fontsize=10)
        
        # 右圖：總事件數
        bars2 = ax2.bar(df_plot['k_label'], df_plot['total_events'],
                       color='coral', alpha=0.85, edgecolor='black', linewidth=0.5)
        ax2.set_xlabel('K Value', fontsize=13, fontweight='bold')
        ax2.set_ylabel('Total Events', fontsize=13, fontweight='bold')
        ax2.set_title('Total Control Signaling Events', fontsize=15, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 標註數值
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height):,}',
                   ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        output_path = self.output_dir / "chart1_total_overhead_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  📊 圖表1已保存: {output_path.name}")
        plt.close()
    
    def _chart2_gateway_overhead(self, df_plot):
        """圖表2：Gateway 更新控制信令開銷（K 參數實驗重點）"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # 左圖：Gateway 更新總字節數
        bars1 = ax1.bar(df_plot['k_label'], df_plot['gateway_bytes'] / 1e6, 
                       color='darkorange', alpha=0.85, edgecolor='black', linewidth=0.5)
        ax1.set_xlabel('K Value', fontsize=13, fontweight='bold')
        ax1.set_ylabel('Gateway Update Signaling (MB)', fontsize=13, fontweight='bold')
        ax1.set_title('Gateway Update Control Signaling', fontsize=15, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 標註數值
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}',
                   ha='center', va='bottom', fontsize=10)
        
        # 右圖：Gateway 更新次數
        bars2 = ax2.bar(df_plot['k_label'], df_plot['gateway_updates'],
                       color='coral', alpha=0.85, edgecolor='black', linewidth=0.5)
        ax2.set_xlabel('K Value', fontsize=13, fontweight='bold')
        ax2.set_ylabel('Gateway Update Count', fontsize=13, fontweight='bold')
        ax2.set_title('Gateway Update Frequency', fontsize=15, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 標註數值
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        output_path = self.output_dir / "chart2_gateway_overhead_comparison.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  📊 圖表2已保存: {output_path.name}")
        plt.close()
    
    def _chart3_event_distribution(self, df_plot):
        """圖表3：事件類型分佈（分組柱狀圖）"""
        fig, ax = plt.subplots(figsize=(16, 9))
        
        # 準備數據
        event_types = ['gateway_updates', 'routing_updates', 'gid_rebuilds']
        event_labels = ['Gateway Updates', 'Routing Updates', 'GID Rebuilds']
        colors = ['orange', 'skyblue', 'lightgreen']
        
        x = np.arange(len(df_plot))
        width = 0.25
        
        for i, (event_type, label, color) in enumerate(zip(event_types, event_labels, colors)):
            offset = (i - 1) * width
            bars = ax.bar(x + offset, df_plot[event_type], width, 
                         label=label, color=color, alpha=0.85, edgecolor='black', linewidth=0.5)
            
            # 標註數值
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{int(height)}',
                           ha='center', va='bottom', fontsize=8)
        
        ax.set_xlabel('K Value', fontsize=13, fontweight='bold')
        ax.set_ylabel('Event Count', fontsize=13, fontweight='bold')
        ax.set_title('Control Signaling Event Type Distribution', fontsize=15, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(df_plot['k_label'])
        ax.legend(fontsize=11, framealpha=0.9)
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        plt.tight_layout()
        output_path = self.output_dir / "chart3_event_type_distribution.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  📊 圖表3已保存: {output_path.name}")
        plt.close()
    
    def _chart4_improvement(self, df_plot):
        """圖表4：相對於 K=1 的改善百分比"""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        baseline_bytes = df_plot.iloc[0]['total_bytes']
        df_plot['improvement'] = (1 - df_plot['total_bytes'] / baseline_bytes) * 100
        
        colors = ['red' if x < 0 else 'green' for x in df_plot['improvement']]
        bars = ax.bar(df_plot['k_label'], df_plot['improvement'], 
                     color=colors, alpha=0.85, edgecolor='black', linewidth=0.5)
        
        ax.set_xlabel('K Value', fontsize=13, fontweight='bold')
        ax.set_ylabel('Improvement vs K=1 (%)', fontsize=13, fontweight='bold')
        ax.set_title('Control Signaling Overhead Improvement (vs K=1)', fontsize=15, fontweight='bold')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}%',
                   ha='center', va='bottom' if height > 0 else 'top', fontsize=11)
        
        plt.tight_layout()
        output_path = self.output_dir / "chart4_improvement_percentage.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"  📊 圖表4已保存: {output_path.name}")
        plt.close()
    
    def run(self):
        """執行完整分析"""
        df = self.analyze_all_k_values()
        
        if df is None or df.empty:
            print("❌ 無法進行分析")
            return
        
        # 顯示基本統計
        print("\n" + "="*60)
        print("基本統計：")
        print("="*60)
        print(df[['k', 'total_events', 'total_bytes']].to_string(index=False))
        print()
        
        # 生成報告
        self.generate_report(df)
        
        # 繪製圖表
        self.plot_comparisons(df)
        
        print("\n" + "="*60)
        print("分析完成！")
        print(f"結果保存在：{self.output_dir}/")
        print("="*60)


if __name__ == "__main__":
    analyzer = KParameterAnalyzer()
    analyzer.run()
