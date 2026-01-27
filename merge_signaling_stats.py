#!/usr/bin/env python3
"""
合併 Process-Local 統計文件工具

用途：
    將模擬過程中各個進程生成的臨時統計文件合併成最終的統計文件

特點：
    - 自動去重：基於 (snapshot, time_ms, event) 的唯一性
    - 保留所有時間軸事件
    - 重新計算摘要統計
    - 自動清理臨時文件

使用方法：
    python merge_signaling_stats.py -d analytic_result

參數：
    -d, --directory: 統計文件目錄（默認：analytic_result）
    --keep-temp: 保留臨時文件（默認：刪除）
    -v, --verbose: 顯示詳細信息
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class StatsMerger:
    """統計文件合併器"""
    
    def __init__(self, directory: str, keep_temp: bool = False, verbose: bool = False):
        self.directory = Path(directory)
        self.keep_temp = keep_temp
        self.verbose = verbose
        
        # 算法配置：(temp_dir_name, output_filename, display_name)
        self.algorithms = {
            'baseline': ('temp_baseline', 'baseline_floyd_warshall_signaling_stats.json', 'Floyd-Warshall Baseline'),
            'grhr': ('temp_grhr', 'hierarchical_gid_15deg_signaling_stats.json', 'Hierarchical GID (15°)'),
            'lohi': ('temp_lohi', 'lohi_signaling_stats_pure_p6_s10.json', 'LoHi (p=6, s=10)')
        }
    
    def log(self, message: str, force: bool = False):
        """日誌輸出"""
        if self.verbose or force:
            print(message)
    
    def collect_temp_files(self, temp_dir: Path) -> List[Path]:
        """收集臨時文件"""
        if not temp_dir.exists():
            return []
        
        return list(temp_dir.glob('*_stats_pid*_tid*.json'))
    
    def merge_timeline_events(self, files: List[Path]) -> Tuple[List[Dict], Dict]:
        """合併時間軸事件並去重
        
        Returns:
            (merged_timeline, stats_by_type)
        """
        # 使用 set 去重：(snapshot, time_ms, event, detail_json) 作為唯一鍵
        # detail 必須序列化為 JSON 字串才能作為 set 的鍵
        seen_events = set()
        all_events = []
        
        # 統計各類型事件
        stats_by_type = defaultdict(lambda: {'count': 0, 'bytes': 0})
        
        for filepath in files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                timeline = data.get('timeline', [])
                for event in timeline:
                    snapshot = event['snapshot']
                    time_ms = event['time_ms']
                    event_type = event['event']
                    count = event['count']
                    bytes_val = event['bytes']
                    detail = event.get('detail', {})
                    
                    # 創建唯一鍵：將 detail 序列化為 JSON 字串
                    # 使用 sort_keys=True 確保相同內容的 dict 生成相同的字串
                    detail_json = json.dumps(detail, sort_keys=True) if detail else ''
                    key = (snapshot, time_ms, event_type, detail_json)
                    
                    if key not in seen_events:
                        seen_events.add(key)
                        all_events.append(event)
                        
                        # 累加統計
                        stats_by_type[event_type]['count'] += count
                        stats_by_type[event_type]['bytes'] += bytes_val
                        
            except Exception as e:
                self.log(f"  警告：無法讀取 {filepath.name}: {e}")
                continue
        
        # 按時間排序
        all_events.sort(key=lambda x: (x['snapshot'], x['time_ms'], x['event']))
        
        return all_events, dict(stats_by_type)
    
    def calculate_summary(self, stats_by_type: Dict) -> Dict:
        """計算摘要統計"""
        total_events = sum(s['count'] for s in stats_by_type.values())
        total_bytes = sum(s['bytes'] for s in stats_by_type.values())
        
        return {
            'total_events': total_events,
            'total_bytes': total_bytes,
            'by_type': stats_by_type
        }
    
    def merge_algorithm(self, algo_name: str, temp_dir_name: str, 
                       output_filename: str, display_name: str) -> bool:
        """合併單個算法的統計文件
        
        Returns:
            True if successful, False otherwise
        """
        temp_dir = self.directory / temp_dir_name
        
        # 檢查臨時目錄是否存在
        if not temp_dir.exists():
            self.log(f"[{algo_name.upper()}] 跳過：臨時目錄 {temp_dir_name} 不存在")
            return False
        
        # 收集臨時文件
        temp_files = self.collect_temp_files(temp_dir)
        
        if not temp_files:
            self.log(f"[{algo_name.upper()}] 跳過：沒有找到臨時文件")
            return False
        
        self.log(f"[{algo_name.upper()}] 找到 {len(temp_files)} 個臨時文件", force=True)
        
        # 讀取第一個文件獲取元數據（需要在合併前讀取以便生成正確的文件名）
        with open(temp_files[0], 'r', encoding='utf-8') as f:
            first_file = json.load(f)
        
        # 根據算法參數動態生成輸出文件名
        if algo_name == 'grhr' and 'grid_deg' in first_file:
            grid_deg = first_file['grid_deg']
            k_best = first_file.get('k_best_gateways', None)
            scenario = first_file.get('scenario', 'baseline')
            
            # 構建檔案名稱
            filename_parts = [f'hierarchical_gid_{grid_deg}deg']
            
            # 添加場景資訊（如果不是 baseline）
            if scenario and scenario != 'baseline':
                filename_parts.append(scenario)
            
            # 添加 K 值資訊（如果有）
            if k_best is not None:
                filename_parts.append(f'k{k_best}')
            
            output_filename = '_'.join(filename_parts) + '_signaling_stats.json'
            
            # 構建顯示名稱
            display_parts = [f'Hierarchical GID ({grid_deg}°)']
            if scenario and scenario != 'baseline':
                display_parts.append(f'{scenario.upper()}')
            if k_best is not None:
                display_parts.append(f'K={k_best}')
            display_name = ', '.join(display_parts)
            
            self.log(f"[{algo_name.upper()}] 檢測到 grid_deg={grid_deg}, scenario={scenario}, k={k_best}，使用動態文件名", force=True)
        elif algo_name == 'lohi' and 'p' in first_file and 's' in first_file:
            p = first_file['p']
            s = first_file['s']
            output_filename = f'lohi_signaling_stats_pure_p{p}_s{s}.json'
            display_name = f'LoHi (p={p}, s={s})'
            self.log(f"[{algo_name.upper()}] 檢測到 p={p}, s={s}，使用動態文件名", force=True)
        
        # 合併時間軸事件
        self.log(f"[{algo_name.upper()}] 合併時間軸事件...")
        merged_timeline, stats_by_type = self.merge_timeline_events(temp_files)
        
        # 計算摘要
        summary = self.calculate_summary(stats_by_type)
        
        self.log(f"[{algo_name.upper()}] 合併完成：{summary['total_events']} 事件, {summary['total_bytes']} 字節", force=True)
        
        # 構建最終統計數據
        from datetime import datetime
        final_stats = {
            'algorithm': first_file.get('algorithm', algo_name),
            'algorithm_display_name': display_name,
            'timestamp': datetime.now().isoformat(),
            'summary': summary,
            'timeline': merged_timeline
        }
        
        # 添加算法特定字段
        if 'grid_deg' in first_file:
            final_stats['grid_deg'] = first_file['grid_deg']
        if 'k_best_gateways' in first_file:
            final_stats['k_best_gateways'] = first_file['k_best_gateways']
        if 'scenario' in first_file:
            final_stats['scenario'] = first_file['scenario']
        if 'p' in first_file:
            final_stats['p'] = first_file['p']
            final_stats['s'] = first_file['s']
        
        # 寫入最終文件
        output_path = self.directory / output_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(final_stats, f, indent=2, ensure_ascii=False)
        
        self.log(f"[{algo_name.upper()}] 已保存到：{output_path}", force=True)
        
        # 清理臨時文件
        if not self.keep_temp:
            self.log(f"[{algo_name.upper()}] 清理臨時文件...")
            for filepath in temp_files:
                try:
                    filepath.unlink()
                except Exception as e:
                    self.log(f"  警告：無法刪除 {filepath.name}: {e}")
            
            # 刪除臨時目錄（如果為空）
            try:
                temp_dir.rmdir()
                self.log(f"[{algo_name.upper()}] 已刪除臨時目錄")
            except OSError:
                self.log(f"[{algo_name.upper()}] 臨時目錄不為空，保留")
        
        return True
    
    def merge_all(self) -> Dict[str, bool]:
        """合併所有算法的統計文件
        
        Returns:
            Dict[algorithm_name, success]
        """
        results = {}
        
        print("=" * 70)
        print("Process-Local 統計文件合併工具")
        print("=" * 70)
        print(f"目錄: {self.directory}")
        print(f"保留臨時文件: {self.keep_temp}")
        print()
        
        for algo_name, (temp_dir, output_file, display_name) in self.algorithms.items():
            success = self.merge_algorithm(algo_name, temp_dir, output_file, display_name)
            results[algo_name] = success
            print()
        
        # 輸出摘要
        print("=" * 70)
        print("合併摘要")
        print("=" * 70)
        for algo_name, success in results.items():
            status = "✓ 成功" if success else "✗ 跳過"
            print(f"{status:8} {algo_name.upper()}")
        
        successful = sum(1 for s in results.values() if s)
        print(f"\n總計：{successful}/{len(results)} 個算法完成合併")
        print("=" * 70)
        
        return results


def main():
    parser = argparse.ArgumentParser(
        description='合併 Process-Local 統計文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 基本用法
  python merge_signaling_stats.py
  
  # 指定目錄
  python merge_signaling_stats.py -d analytic_result
  
  # 保留臨時文件
  python merge_signaling_stats.py --keep-temp
  
  # 詳細模式
  python merge_signaling_stats.py -v
        """
    )
    
    parser.add_argument(
        '-d', '--directory',
        type=str,
        default='paper/satellite_networks_state/analytic_result',
        help='統計文件目錄（默認：paper/satellite_networks_state/analytic_result）'
    )
    
    parser.add_argument(
        '--keep-temp',
        action='store_true',
        help='保留臨時文件（默認：刪除）'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='顯示詳細信息'
    )
    
    args = parser.parse_args()
    
    # 檢查目錄是否存在
    directory = Path(args.directory)
    if not directory.exists():
        print(f"錯誤：目錄 '{args.directory}' 不存在", file=sys.stderr)
        return 1
    
    # 執行合併
    merger = StatsMerger(
        directory=args.directory,
        keep_temp=args.keep_temp,
        verbose=args.verbose
    )
    
    results = merger.merge_all()
    
    # 返回狀態碼
    return 0 if any(results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
