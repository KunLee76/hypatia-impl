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


# ===== Normalized (Unified) Control-Plane Byte Model =====
# We keep the original event types emitted by each algorithm, but recompute bytes with a unified model:
#   bytes(event) = CTRL_HDR_BYTES + N_entries(event) * ENTRY_BYTES(event_type)
# This makes cross-algorithm comparison apples-to-apples.
CTRL_HDR_BYTES = 32  # OSPFv3-like core (16B) + satellite extension (16B)
ROUTE_ENTRY_BYTES = 32
PHYS_TOPO_ENTRY_BYTES = 32      # physical ISL/GSL edge state entry
GROUP_TOPO_ENTRY_BYTES = 32     # group-level / logical edge entry (LoHi topology_change)
ID_ENTRY_BYTES = 32             # PID/GID mapping / identifier maintenance entry
GATEWAY_ENTRY_BYTES = 32        # gateway publication entry (k-best edges)

# If True, analyzer will recompute/overwrite summary bytes using the unified model above.
NORMALIZE_BYTES = True
class MultiAlgorithmAnalyzer:
    def __init__(self, stats_dir="paper/satellite_networks_state/analytic_result"):
        self.stats_dir = Path(stats_dir)
    
    def find_all_stats_files(self):
        """查找所有算法的統計文件"""
        patterns = {
            "baseline": "baseline_floyd_warshall_signaling_stats.json",
            "hierarchical_floyd": "hierarchical_gid_*deg_k*_signaling_stats.json",  # 修改為匹配 k4 和 k999
            "hierarchical_dijkstra": "hierarchical_gid_dijkstra_*deg_signaling_stats.json",
            "lohi": "lohi_signaling_stats*.json"  # 新增 LoHi 模式
        }
        
        found_files = {}
        
        # Baseline
        baseline_path = self.stats_dir / patterns["baseline"]
        if baseline_path.exists():
            found_files['baseline'] = [str(baseline_path)]
        
        # Hierarchical (Floyd-Warshall) - 只包含 k=4 和 k=999
        h_floyd_files = glob.glob(str(self.stats_dir / patterns["hierarchical_floyd"]))
        # 排除 dijkstra 版本和 BACKUP 文件，只保留 k4 和 k999
        h_floyd_files = [f for f in h_floyd_files 
                        if 'dijkstra' not in f 
                        and 'BACKUP' not in f
                        and ('k4_' in f or 'k999_' in f)]
        if h_floyd_files:
            found_files['hierarchical_floyd'] = sorted(h_floyd_files)
        
        # Hierarchical (Dijkstra)
        h_dijkstra_files = glob.glob(str(self.stats_dir / patterns["hierarchical_dijkstra"]))
        if h_dijkstra_files:
            found_files['hierarchical_dijkstra'] = sorted(h_dijkstra_files)
        
        # LoHi
        lohi_files = glob.glob(str(self.stats_dir / patterns["lohi"]))
        # 排除 dynamic 場景（ISL 失效場景）
        lohi_files = [f for f in lohi_files if 'dynamic' not in f]
        if lohi_files:
            found_files['lohi'] = sorted(lohi_files)
        
        return found_files
    
    def load_stats(self, file_path):
        """加載統計數據（期望所有算法使用統一的 by_type 格式）

        若 NORMALIZE_BYTES=True，會以統一的 header+entry 模型重新計算 bytes，
        並覆寫 summary.total_bytes / summary.by_type[*].bytes（保留 raw_* 備份）。
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 檢查並補充舊格式（針對 k=999）
        if 'summary' not in data or 'by_type' not in data.get('summary', {}):
            # 嘗試從 timeline 構建 by_type
            if 'timeline' in data:
                from collections import defaultdict
                by_type = defaultdict(list)
                for event in data['timeline']:
                    event_type = event.get('event')
                    if event_type:
                        by_type[event_type].append(event)
                
                # 構建或補充 summary
                if 'summary' not in data:
                    data['summary'] = {}
                
                data['summary']['by_type'] = {}
                for event_type, events in by_type.items():
                    data['summary']['by_type'][event_type] = {
                        'count': len(events),
                        'bytes': 0,  # 將由 NORMALIZE_BYTES 重新計算
                        'events': events
                    }
                
                # 添加基本統計
                if 'total_events' not in data['summary']:
                    data['summary']['total_events'] = len(data['timeline'])
                
                # 更新 algorithm_display_name（針對 k=999）
                if 'k_best_gateways' in data and data.get('k_best_gateways') == 999:
                    data['algorithm_display_name'] = 'GRHR (27°, k=all)'
            else:
                raise ValueError(
                    f"❌ 格式錯誤: {Path(file_path).name}\n"
                    f"   期望 summary.by_type 結構，但未找到。\n"
                    f"   請確保所有算法輸出統一格式的統計數據。"
                )

        if NORMALIZE_BYTES:
            self._normalize_control_bytes(data, file_path)

        return data
 
    def _normalize_control_bytes(self, data: dict, file_path: str):
        """Recompute bytes using unified header+entry model, without changing event types.

        Assumptions (true for the three algorithms in this project):
        - timeline is a list of dicts; each dict contains: event (str), count (messages, usually 1), bytes (raw),
          and detail (dict) which carries the *entry count* such as changed_entries, delta_isl, delta_gsl, etc.
        - summary.by_type[*].count counts *messages*, not entries.

        We keep counts as-is and only recompute bytes.
        """
        summary = data.get('summary', {})
        algo_name = (
            summary.get('algorithm_display_name')
            or summary.get('algorithm')
            or str(file_path)
        ).lower()

        is_lohi = 'lohi' in algo_name

        # backup raw values once
        if 'raw_total_bytes' not in summary:
            summary['raw_total_bytes'] = summary.get('total_bytes', 0)
        if 'raw_by_type' not in summary:
            # deep copy minimal
            summary['raw_by_type'] = {k: dict(v) for k, v in summary.get('by_type', {}).items()}

        # normalize timeline rows
        timeline = data.get('timeline', [])
        norm_total_bytes = 0
        norm_by_type = {k: {'count': v.get('count', 0), 'bytes': 0} for k, v in summary.get('by_type', {}).items()}
        norm_total_msgs = 0

        for row in timeline:
            ev = row.get('event') or row.get('type')  # tolerate older key
            if not ev:
                continue
            ev = str(ev)
            detail = row.get('detail') or {}
            # messages count (kept as-is)
            msg_count = int(row.get('count', 1) or 1)
            norm_total_msgs += msg_count

            # infer number of entries carried by this message
            n_entries = 0
            if ev == 'routing_update':
                n_entries = int(detail.get('changed_entries', 0) or 0)
                entry_bytes = ROUTE_ENTRY_BYTES
            elif ev == 'topology_change':
                if 'delta_group_edges' in detail:
                    n_entries = abs(int(detail.get('delta_group_edges', 0) or 0))
                    entry_bytes = GROUP_TOPO_ENTRY_BYTES if is_lohi else PHYS_TOPO_ENTRY_BYTES
                else:
                    n_entries = abs(int(detail.get('delta_isl', 0) or 0)) + abs(int(detail.get('delta_gsl', 0) or 0))
                    # fall back if someone used a generic delta_edges field
                    if n_entries == 0 and 'delta_edges' in detail:
                        n_entries = abs(int(detail.get('delta_edges', 0) or 0))
                    entry_bytes = PHYS_TOPO_ENTRY_BYTES
            elif ev == 'gid_rebuild':
                n_entries = int(detail.get('changed_gids', 0) or 0)
                entry_bytes = ID_ENTRY_BYTES
            elif ev == 'pid_rebuild':
                n_entries = int(detail.get('changed_pids', 0) or 0)
                entry_bytes = ID_ENTRY_BYTES
            elif ev == 'gateway_update':
                # 特殊處理：每對 GID 一個訊息，使用通用公式 n_msgs*HDR + n_entries*ENTRY
                # 優先使用 detail 中提供的 num_messages/num_entries，避免推導
                n_msgs = int(detail.get('num_messages', 0) or 0)
                n_entries = int(detail.get('num_entries', 0) or 0)
                
                # fallback：若沒有提供，從 changed_pairs 和 k 推導
                if n_msgs == 0 and n_entries == 0:
                    changed_pairs = int(detail.get('changed_pairs', 0) or 0)
                    k = int(detail.get('k', 0) or detail.get('k_used', 0) or 0)
                    n_msgs = changed_pairs
                    n_entries = changed_pairs * max(k, 1)
                
                # gateway_update 使用多訊息模型：每對 GID 一個訊息
                norm_bytes = n_msgs * CTRL_HDR_BYTES + n_entries * GATEWAY_ENTRY_BYTES
                row['bytes_normalized'] = norm_bytes
                if 'bytes_raw' not in row:
                    row['bytes_raw'] = row.get('bytes', 0)
                row['bytes'] = norm_bytes
                
                norm_total_bytes += norm_bytes
                if ev in norm_by_type:
                    norm_by_type[ev]['bytes'] += norm_bytes
                else:
                    norm_by_type[ev] = {'count': msg_count, 'bytes': norm_bytes}
                continue
            else:
                # Unknown event: keep raw bytes to avoid under/over-estimation silently.
                norm_bytes = int(row.get('bytes', 0) or 0)
                row['bytes_normalized'] = norm_bytes
                norm_total_bytes += norm_bytes
                if ev in norm_by_type:
                    norm_by_type[ev]['bytes'] += norm_bytes
                else:
                    norm_by_type[ev] = {'count': msg_count, 'bytes': norm_bytes}
                continue

            # unified bytes model
            norm_bytes = int(CTRL_HDR_BYTES + n_entries * entry_bytes)
            row['bytes_normalized'] = norm_bytes
            # also overwrite row bytes for downstream plots (but keep raw in bytes_raw)
            if 'bytes_raw' not in row:
                row['bytes_raw'] = row.get('bytes', 0)
            row['bytes'] = norm_bytes

            norm_total_bytes += norm_bytes
            if ev in norm_by_type:
                norm_by_type[ev]['bytes'] += norm_bytes
            else:
                # if a type exists in timeline but not in summary.by_type, add it
                norm_by_type[ev] = {'count': msg_count, 'bytes': norm_bytes}

        # overwrite summary with normalized bytes (keep original counts)
        summary['total_bytes'] = norm_total_bytes
        # total_events in this project = total messages (because EventRow.count is always 1 in recorders)
        summary['total_events'] = norm_total_msgs
        summary['by_type'] = norm_by_type
        summary['normalization'] = {
            'enabled': True,
            'CTRL_HDR_BYTES': CTRL_HDR_BYTES,
            'ROUTE_ENTRY_BYTES': ROUTE_ENTRY_BYTES,
            'PHYS_TOPO_ENTRY_BYTES': PHYS_TOPO_ENTRY_BYTES,
            'GROUP_TOPO_ENTRY_BYTES': GROUP_TOPO_ENTRY_BYTES,
            'ID_ENTRY_BYTES': ID_ENTRY_BYTES,
            'GATEWAY_ENTRY_BYTES': GATEWAY_ENTRY_BYTES,
            'notes': 'Bytes recomputed as HDR + N_entries*ENTRY_BYTES using timeline.detail fields. Raw values preserved in summary.raw_* and row.bytes_raw.'
        }

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
                # 對於 hierarchical_floyd，只保留 k=4 和 k=999
                if category == 'hierarchical_floyd':
                    filename = Path(file_path).name
                    if not ('k4_' in filename or 'k999_' in filename):
                        continue
                
                data = self.load_stats(file_path)
                display_name = data.get('algorithm_display_name', Path(file_path).stem)
                grid_deg = data.get('grid_deg', None)
                
                # 為 GRHR 計算排除 routing_update 的控制信令（用於 Chart 1, 2）
                control_signaling_bytes = data['summary']['total_bytes']
                control_events = data['summary']['total_events']
                
                if category == 'hierarchical_floyd':
                    # GRHR: 排除 routing_update（衛星自行計算，無需傳輸）
                    by_type = data['summary'].get('by_type', {})
                    routing_bytes = by_type.get('routing_update', {}).get('bytes', 0)
                    routing_events = by_type.get('routing_update', {}).get('count', 0)  # 修正：使用 'count' 而非 'events'
                    control_signaling_bytes = data['summary']['total_bytes'] - routing_bytes
                    control_events = data['summary']['total_events'] - routing_events
                
                algorithms_data.append({
                    'category': category,
                    'file': file_path,
                    'name': display_name,
                    'grid_deg': grid_deg,
                    'data': data,
                    'control_signaling_bytes': control_signaling_bytes,  # 控制信令字節數（排除 routing_update）
                    'control_events': control_events  # 控制事件數（排除 routing_update）
                })
                print(f"  ✅ {display_name}: {len(data.get('timeline', []))} 事件, {data['summary']['total_bytes']:,} 字節")
        
        if len(algorithms_data) < 2:
            print("⚠️  至少需要 2 個算法進行比較")
            return None
        
        # 按類別和網格大小排序
        # 排序順序：baseline -> hierarchical_floyd -> hierarchical_dijkstra -> lohi
        algorithms_data.sort(key=lambda x: (
            0 if x['category'] == 'baseline' 
            else 1 if x['category'] == 'hierarchical_floyd' 
            else 2 if x['category'] == 'hierarchical_dijkstra'
            else 3,  # lohi
            x['grid_deg'] if x['grid_deg'] else 0
        ))
        
        # 生成比較報告
        self.generate_multi_comparison_report(algorithms_data, output_path)

        # 生成 entries 對照報告（解釋每種事件如何換算 bytes）
        self.generate_entries_reference_report(algorithms_data, output_path)
        
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
                # 使用 control_signaling_bytes 和 control_events（GRHR 已排除 routing_update）
                summary_table.append({
                    'name': algo['name'],
                    'events': algo['control_events'],  # 修改為使用控制事件數
                    'bytes': algo['control_signaling_bytes'],  # 修改為使用控制信令字節數
                    'category': algo['category']
                })
            
            # 按字節數排序
            summary_table.sort(key=lambda x: x['bytes'])
            
            for item in summary_table:
                f.write(f"\n{item['name']}:\n")
                f.write(f"  控制事件數: {item['events']:,}\n")  # 改為「控制事件數」
                f.write(f"  控制信令字節數: {item['bytes']:,}\n")
                # GRHR 額外說明已排除 routing_update
                if item['category'] == 'hierarchical_floyd':
                    f.write(f"  (註: GRHR 已排除 routing_update，衛星自行計算)\n")
                
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

    def _collect_entry_stats(self, algo):
        """依照 normalize 規則統計各事件的 entry 數量與公式 bytes。"""
        data = algo.get('data', {})
        summary = data.get('summary', {})
        by_type = summary.get('by_type', {})
        timeline = data.get('timeline', [])

        is_lohi = algo.get('category') == 'lohi'
        stats = {}

        def _ensure(ev):
            if ev not in stats:
                stats[ev] = {
                    'events': int(by_type.get(ev, {}).get('count', 0) or 0),
                    'entries_total': 0,
                    'header_units': 0,
                    'entry_bytes': 0,
                    'calc_bytes': 0,
                    'summary_bytes': int(by_type.get(ev, {}).get('bytes', 0) or 0),
                }

        for row in timeline:
            ev = row.get('event') or row.get('type')
            if not ev:
                continue
            ev = str(ev)
            detail = row.get('detail') or {}

            n_entries = 0
            hdr_units = 1
            entry_bytes = 0

            if ev == 'routing_update':
                n_entries = int(detail.get('changed_entries', 0) or 0)
                entry_bytes = ROUTE_ENTRY_BYTES
            elif ev == 'topology_change':
                if 'delta_group_edges' in detail:
                    n_entries = abs(int(detail.get('delta_group_edges', 0) or 0))
                    entry_bytes = GROUP_TOPO_ENTRY_BYTES if is_lohi else PHYS_TOPO_ENTRY_BYTES
                else:
                    n_entries = abs(int(detail.get('delta_isl', 0) or 0)) + abs(int(detail.get('delta_gsl', 0) or 0))
                    if n_entries == 0 and 'delta_edges' in detail:
                        n_entries = abs(int(detail.get('delta_edges', 0) or 0))
                    entry_bytes = PHYS_TOPO_ENTRY_BYTES
            elif ev == 'gid_rebuild':
                n_entries = int(detail.get('changed_gids', 0) or 0)
                entry_bytes = ID_ENTRY_BYTES
            elif ev == 'pid_rebuild':
                n_entries = int(detail.get('changed_pids', 0) or 0)
                entry_bytes = ID_ENTRY_BYTES
            elif ev == 'gateway_update':
                n_msgs = int(detail.get('num_messages', 0) or 0)
                n_entries = int(detail.get('num_entries', 0) or 0)
                if n_msgs == 0 and n_entries == 0:
                    changed_pairs = int(detail.get('changed_pairs', 0) or 0)
                    k = int(detail.get('k', 0) or detail.get('k_used', 0) or 0)
                    n_msgs = changed_pairs
                    n_entries = changed_pairs * max(k, 1)
                hdr_units = n_msgs
                entry_bytes = GATEWAY_ENTRY_BYTES
            else:
                # 其他未知事件，不納入 entries 對照
                continue

            calc_bytes = hdr_units * CTRL_HDR_BYTES + n_entries * entry_bytes
            _ensure(ev)
            stats[ev]['entries_total'] += n_entries
            stats[ev]['header_units'] += hdr_units
            stats[ev]['entry_bytes'] = entry_bytes
            stats[ev]['calc_bytes'] += calc_bytes

        # 若某事件在 summary 出現但 timeline 未累積到，仍保留列（方便對照）
        for ev in by_type.keys():
            _ensure(ev)

        return stats

    def generate_entries_reference_report(self, algorithms_data, output_path):
        """輸出每演算法、每事件類型對應的 entries 對照報告。"""
        report_file = output_path / "multi_algorithm_entries_reference.txt"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("Hypatia 控制信令 Entries 對照報告\n")
            f.write("=" * 90 + "\n")
            f.write(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("統一位元組模型（normalize）:\n")
            f.write(f"  - CTRL_HDR_BYTES = {CTRL_HDR_BYTES}\n")
            f.write(f"  - ROUTE_ENTRY_BYTES = {ROUTE_ENTRY_BYTES}\n")
            f.write(f"  - PHYS_TOPO_ENTRY_BYTES = {PHYS_TOPO_ENTRY_BYTES}\n")
            f.write(f"  - GROUP_TOPO_ENTRY_BYTES = {GROUP_TOPO_ENTRY_BYTES}\n")
            f.write(f"  - ID_ENTRY_BYTES = {ID_ENTRY_BYTES}\n")
            f.write(f"  - GATEWAY_ENTRY_BYTES = {GATEWAY_ENTRY_BYTES}\n\n")

            f.write("事件 -> entries 推導規則:\n")
            f.write("  - routing_update: entries = changed_entries\n")
            f.write("  - topology_change: entries = |delta_group_edges| (LoHi) 或 |delta_isl|+|delta_gsl|\n")
            f.write("  - gid_rebuild: entries = changed_gids\n")
            f.write("  - pid_rebuild: entries = changed_pids\n")
            f.write("  - gateway_update: entries = num_entries (或 changed_pairs * k_used), headers = num_messages\n")
            f.write("\n")
            f.write("備註: Chart1/Chart2 的 GRHR 會排除 routing_update（視為衛星本地計算）。\n")
            f.write("=" * 90 + "\n")

            ordered_events = [
                'gateway_update',
                'gid_rebuild',
                'pid_rebuild',
                'routing_update',
                'topology_change',
            ]

            for algo in algorithms_data:
                f.write(f"\n【{algo['name']}】\n")
                f.write("-" * 90 + "\n")
                f.write(f"{'Event':<18} {'Events':>8} {'Entries':>12} {'AvgEntry/Event':>15} {'Headers':>10} {'EntryB':>8} {'CalcBytes':>14} {'SummaryBytes':>14}\n")
                f.write("-" * 90 + "\n")

                stats = self._collect_entry_stats(algo)
                all_events = ordered_events + [e for e in stats.keys() if e not in ordered_events]

                total_entries_all = 0
                for ev in all_events:
                    if ev not in stats:
                        continue

                    item = stats[ev]
                    events = int(item.get('events', 0) or 0)
                    entries = int(item.get('entries_total', 0) or 0)
                    avg = (entries / events) if events > 0 else 0.0
                    headers = int(item.get('header_units', 0) or 0)
                    entry_b = int(item.get('entry_bytes', 0) or 0)
                    calc_b = int(item.get('calc_bytes', 0) or 0)
                    sum_b = int(item.get('summary_bytes', 0) or 0)

                    total_entries_all += entries
                    f.write(f"{ev:<18} {events:>8,d} {entries:>12,d} {avg:>15.2f} {headers:>10,d} {entry_b:>8,d} {calc_b:>14,d} {sum_b:>14,d}\n")

                f.write("-" * 90 + "\n")
                f.write(f"{'TOTAL':<18} {'':>8} {total_entries_all:>12,d}\n")

        print(f"📄 Entries 對照報告已保存: {report_file}")
    
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

    def _chart1_metrics(self, algo):
        """Chart1 metrics with GRHR routing_update excluded."""
        summary = algo['data'].get('summary', {})
        by_type = summary.get('by_type', {})
        total_bytes = int(summary.get('total_bytes', 0) or 0)
        total_events = int(summary.get('total_events', 0) or 0)

        if algo.get('category') == 'hierarchical_floyd':
            routing_bytes = int(by_type.get('routing_update', {}).get('bytes', 0) or 0)
            routing_events = int(by_type.get('routing_update', {}).get('count', 0) or 0)
            return max(total_bytes - routing_bytes, 0), max(total_events - routing_events, 0)

        return total_bytes, total_events
    
    def _chart1_overall_multi(self, algorithms_data, output_path):
        """圖表1: 多算法總體比較"""
        num_algos = len(algorithms_data)
        
        # 根據算法數量調整圖表大小
        fig_width = max(20, num_algos * 1.5)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(fig_width, 9))
        
        names = [algo['name'] for algo in algorithms_data]
        labels_for_plot = [name.replace(' (', '\n(') for name in names]
        # Chart 1 明確以「GRHR 排除 routing_update」規則計算
        metrics = [self._chart1_metrics(algo) for algo in algorithms_data]
        total_bytes = [m[0] for m in metrics]
        total_bytes_mb = [b / (1024 * 1024) for b in total_bytes]  # 轉換為 MB
        control_events = [m[1] for m in metrics]
        
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
            elif algo['category'] == 'lohi':
                # LoHi 使用紫色系
                colors.append('mediumpurple')
            elif algo['category'] == 'hierarchical_floyd':
                # GRHR: k=4 用深綠色，k=all 用淺綠色
                name = algo['name']
                if 'k=4' in name or 'k4' in name.lower():
                    colors.append('#228B22')  # 深綠色 (ForestGreen)
                elif 'k=all' in name.lower() or 'k=999' in name.lower():
                    colors.append('#90C695')  # 淺綠色
                else:
                    # 預設綠色系
                    grid_deg = algo.get('grid_deg', 15)
                    intensity = 0.4 + (grid_deg / 30.0) * 0.6
                    colors.append(plt.cm.Greens(intensity))
            else:
                # 其他使用綠色系
                grid_deg = algo.get('grid_deg', 15)
                intensity = 0.4 + (grid_deg / 30.0) * 0.6
                colors.append(plt.cm.Greens(intensity))
        
        # 左圖：總字節數
        bars1 = ax1.bar(range(len(names)), total_bytes_mb, color=colors, alpha=0.85, edgecolor='black', linewidth=0.5, width=0.5)
        ax1.set_xlabel('Algorithm', fontsize=13, fontweight='bold')
        ax1.set_ylabel('Total Signaling (MB)', fontsize=13, fontweight='bold')
        ax1.set_title('Total Control Signaling (MB)', fontsize=15, fontweight='bold')
        ax1.set_xticks(range(len(names)))
        
        # 優化 x 軸標籤顯示
        if num_algos > 6:
            ax1.set_xticklabels(labels_for_plot, rotation=45, ha='right', fontsize=8, multialignment='center')
        else:
            ax1.set_xticklabels(labels_for_plot, rotation=0, ha='center', fontsize=10, multialignment='center')
        
        ax1.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 添加數值標籤（只在算法數量不太多時顯示）
        if num_algos <= 10:
            for bar, value in zip(bars1, total_bytes_mb):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2, height,
                        f'{value:.2f}', ha='center', va='bottom', fontsize=10, rotation=0)
        
        # 右圖：控制事件數
        bars2 = ax2.bar(range(len(names)), control_events, color=colors, alpha=0.85, edgecolor='black', linewidth=0.5, width=0.5)
        ax2.set_xlabel('Algorithm', fontsize=13, fontweight='bold')
        ax2.set_ylabel('Control Events Count', fontsize=13, fontweight='bold')  # 改為 Control Events Count
        ax2.set_title('Total Control Events', fontsize=15, fontweight='bold')  # 改為 Total Control Events
        ax2.set_xticks(range(len(names)))
        
        if num_algos > 6:
            ax2.set_xticklabels(labels_for_plot, rotation=45, ha='right', fontsize=8, multialignment='center')
        else:
            ax2.set_xticklabels(labels_for_plot, rotation=0, ha='center', fontsize=10, multialignment='center')
        
        ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 添加數值標籤
        if num_algos <= 10:
            for bar, value in zip(bars2, control_events):  # 改為 control_events
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2, height,
                        f'{value:,}', ha='center', va='bottom', fontsize=8, rotation=0)
        
        plt.tight_layout()
        chart_file = output_path / "multi_chart1_overall_comparison.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close(fig)
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
                    # GRHR: 排除 routing_update 事件
                    if algo['category'] == 'hierarchical_floyd':
                        df = df[df['event'] != 'routing_update'].copy()
                    
                    df_sorted = df.sort_values('time_ms')
                    cumulative_bytes = df_sorted['bytes'].cumsum()
                    cumulative_mb = cumulative_bytes / (1024 * 1024)  # 轉換為 MB
                    
                    # 顏色選擇
                    if algo['category'] == 'baseline':
                        color = 'coral'
                    elif algo['category'] == 'hierarchical_dijkstra':
                        grid_deg = algo.get('grid_deg', 15)
                        intensity = 0.4 + (grid_deg / 30.0) * 0.6
                        color = plt.cm.Blues(intensity)
                    elif algo['category'] == 'lohi':
                        color = 'mediumpurple'
                    elif algo['category'] == 'hierarchical_floyd':
                        # GRHR: k=4 用深綠色，k=all 用淺綠色
                        name = algo['name']
                        if 'k=4' in name or 'k4' in name.lower():
                            color = '#228B22'  # 深綠色 (ForestGreen)
                        elif 'k=all' in name.lower() or 'k=999' in name.lower():
                            color = '#90C695'  # 淺綠色
                        else:
                            grid_deg = algo.get('grid_deg', 15)
                            intensity = 0.4 + (grid_deg / 30.0) * 0.6
                            color = plt.cm.Greens(intensity)
                    else:
                        grid_deg = algo.get('grid_deg', 15)
                        intensity = 0.4 + (grid_deg / 30.0) * 0.6
                        color = plt.cm.Greens(intensity)
                    
                    # 線型選擇
                    linestyle = line_styles[idx % len(line_styles)]
                    
                    ax.plot(df_sorted['time_ms']/1000, cumulative_mb,
                           label=algo['name'], color=color, linewidth=2.5,
                           linestyle=linestyle, alpha=0.85)
        
        ax.set_title('Cumulative Control Overhead Over Time', fontsize=15, fontweight='bold')
        ax.set_xlabel('Time (seconds)', fontsize=13, fontweight='bold')
        ax.set_ylabel('Cumulative MB', fontsize=13, fontweight='bold')
        
        # 優化圖例顯示
        if num_algos > 8:
            ax.legend(loc='upper left', fontsize=8, framealpha=0.9, ncol=2)
        else:
            ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
        
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        chart_file = output_path / "multi_chart2_timeline_analysis.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close(fig)
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
        width = 0.8 / num_algorithms  # 統一使用固定基準寬度 0.5（與圖表1一致）
        
        # 預處理算法名稱：將括號部分移到下一行（統一命名）
        names = [algo['name'] for algo in algorithms_data]
        labels_for_plot = [name.replace(' (', '\n(') for name in names]
        
        # 改進的顏色編碼：與圖表1完全一致
        colors = []
        for algo in algorithms_data:
            if algo['category'] == 'baseline':
                colors.append('coral')
            elif algo['category'] == 'hierarchical_dijkstra':
                # Dijkstra 系列使用藍色系
                grid_deg = algo.get('grid_deg', 15)
                intensity = 0.4 + (grid_deg / 30.0) * 0.6
                colors.append(plt.cm.Blues(intensity))
            elif algo['category'] == 'lohi':
                # LoHi 使用紫色系
                colors.append('mediumpurple')
            elif algo['category'] == 'hierarchical_floyd':
                # GRHR: k=4 用深綠色，k=all 用淺綠色
                name = algo['name']
                if 'k=4' in name or 'k4' in name.lower():
                    colors.append('#228B22')  # 深綠色 (ForestGreen)
                elif 'k=all' in name.lower() or 'k=999' in name.lower():
                    colors.append('#90C695')  # 淺綠色
                else:
                    grid_deg = algo.get('grid_deg', 15)
                    intensity = 0.4 + (grid_deg / 30.0) * 0.6
                    colors.append(plt.cm.Greens(intensity))
            else:
                # 其他使用綠色系
                grid_deg = algo.get('grid_deg', 15)
                intensity = 0.4 + (grid_deg / 30.0) * 0.6
                colors.append(plt.cm.Greens(intensity))
        
        for idx, algo in enumerate(algorithms_data):
            summary = algo['data']['summary']
            counts = []
            has_data_flags = []  # 記錄是否有數據
            
            for event_type in all_event_types:
                # GRHR 的 routing_update 在圖表3視為 N/A（衛星本地計算，不視為控制信令）
                if algo.get('category') == 'hierarchical_floyd' and event_type == 'routing_update':
                    counts.append(0)
                    has_data_flags.append(False)
                    continue

                if 'by_type' in summary and event_type in summary['by_type']:
                    counts.append(summary['by_type'][event_type]['count'])
                    has_data_flags.append(True)
                else:
                    counts.append(0)
                    has_data_flags.append(False)
            
            offset = (idx - num_algorithms/2) * width + width/2
            
            bars = ax.bar(x + offset, counts, width,
                         label=labels_for_plot[idx],  # 使用預處理後的標籤
                         color=colors[idx],
                         alpha=0.85,
                         edgecolor='black',
                         linewidth=0.5)
            
            # 添加數值標籤或 N/A 標記
            if num_algos <= 6:
                for bar_idx, (bar, count, has_data) in enumerate(zip(bars, counts, has_data_flags)):
                    if count > 0:
                        # 有數值：顯示數字
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2., height,
                               f'{int(count)}',
                               ha='center', va='bottom', fontsize=10, fontweight='bold')
                    elif not has_data and count == 0:
                        # N/A：在柱子位置上方顯示 "N/A"
                        # 獲取當前 y 軸的範圍，將 N/A 放在適當高度
                        y_max = ax.get_ylim()[1]
                        ax.text(bar.get_x() + bar.get_width()/2., y_max * 0.02,
                               'N/A',
                               ha='center', va='bottom', fontsize=10, 
                               color='black', style='italic')
        
        ax.set_title('Event Count Comparison by Type', fontsize=15, fontweight='bold')
        ax.set_xlabel('Event Type', fontsize=13, fontweight='bold')
        ax.set_ylabel('Event Count', fontsize=13, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(all_event_types, rotation=0, ha='center', fontsize=11)
        
        # 優化圖例：根據算法數量調整圖例標籤顯示
        if num_algos > 8:
            ax.legend(loc='upper right', fontsize=8, ncol=2, framealpha=0.9)
        else:
            ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
        
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        plt.tight_layout()
        chart_file = output_path / "multi_chart3_event_type_distribution.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close(fig)
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
        colors = []  # 統一使用 colors 而非 colors_list
        grid_degs = []
        
        for algo in algorithms_data:
            if algo['category'] == 'baseline':
                continue  # 跳過基線本身
            
            algo_bytes = algo['data']['summary']['total_bytes']
            improvement = ((baseline_bytes - algo_bytes) / baseline_bytes * 100)
            
            names.append(algo['name'])
            improvements.append(improvement)
            grid_degs.append(algo.get('grid_deg', None))
            
            # 使用與圖表1相同的顏色邏輯：根據算法類別和網格大小
            if algo['category'] == 'hierarchical_dijkstra':
                # Dijkstra 系列使用藍色系
                grid_deg = algo.get('grid_deg', 15)
                intensity = 0.4 + (grid_deg / 30.0) * 0.6
                colors.append(plt.cm.Blues(intensity))
            elif algo['category'] == 'lohi':
                # LoHi 使用紫色系
                colors.append('mediumpurple')
            elif algo['category'] == 'hierarchical_floyd':
                # GRHR: k=4 用深綠色，k=all 用淺綠色
                name = algo['name']
                if 'k=4' in name or 'k4' in name.lower():
                    colors.append('#228B22')  # 深綠色 (ForestGreen)
                elif 'k=all' in name.lower() or 'k=999' in name.lower():
                    colors.append('#90C695')  # 淺綠色
                else:
                    grid_deg = algo.get('grid_deg', 15)
                    intensity = 0.4 + (grid_deg / 30.0) * 0.6
                    colors.append(plt.cm.Greens(intensity))
            else:
                # 其他使用綠色系
                grid_deg = algo.get('grid_deg', 15)
                intensity = 0.4 + (grid_deg / 30.0) * 0.6
                colors.append(plt.cm.Greens(intensity))
        
        if not names:
            print("  ⚠️  沒有可比較的算法，跳過圖表4")
            return
        
        # 預處理名稱：將括號部分移到下一行
        labels_for_plot = [name.replace(' (', '\n(') for name in names]
        
        num_algos = len(names)
        # 根據算法數量動態調整圖表寬度，與圖表1保持一致的比例
        fig_width = max(16, num_algos * 1.5)  # 每個算法 1.5 英寸，最小 16 英寸
        fig, ax = plt.subplots(figsize=(fig_width, 8))
        
        bars = ax.bar(range(len(names)), improvements, color=colors, alpha=0.85, 
                     edgecolor='black', linewidth=0.5, width=0.2)  # 縮小寬度至 0.35
        
        ax.set_title('Improvement Relative to Floyd-Warshall Baseline', fontsize=15, fontweight='bold')
        ax.set_ylabel('Improvement Percentage (%)', fontsize=13, fontweight='bold')
        ax.set_xlabel('Algorithm', fontsize=13, fontweight='bold')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
        ax.set_xticks(range(len(names)))
        
        # 優化 x 軸標籤顯示：統一使用與圖表1相同的邏輯
        if num_algos > 6:
            ax.set_xticklabels(labels_for_plot, rotation=45, ha='right', fontsize=8, multialignment='center')
        else:
            ax.set_xticklabels(labels_for_plot, rotation=0, ha='center', fontsize=10, multialignment='center')
        
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
        plt.close(fig)
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
