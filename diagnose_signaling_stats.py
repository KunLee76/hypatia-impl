#!/usr/bin/env python3
"""
診斷控制信令統計數據的異常
"""
import json
import glob
from pathlib import Path

def diagnose_stats_file(file_path):
    """診斷單個統計文件"""
    print(f"\n{'='*80}")
    print(f"檔案: {file_path}")
    print('='*80)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    algo_name = data.get('algorithm_display_name', data.get('algorithm', 'Unknown'))
    print(f"演算法: {algo_name}")
    
    summary = data.get('summary', {})
    by_type = summary.get('by_type', {})
    
    print(f"\n📊 事件類型統計:")
    for event_type, stats in by_type.items():
        count = stats.get('count', 0)
        print(f"  {event_type:25s}: {count:6d} 次")
    
    print(f"\n總事件數: {summary.get('total_events', 0)}")
    
    # 檢查 timeline
    timeline = data.get('timeline', [])
    print(f"\n📈 Timeline 分析:")
    print(f"  總記錄數: {len(timeline)}")
    
    if timeline:
        # 檢查 snapshot 範圍
        snapshots = [row.get('snapshot', 0) for row in timeline]
        print(f"  Snapshot 範圍: {min(snapshots)} ~ {max(snapshots)}")
        print(f"  唯一 snapshot 數: {len(set(snapshots))}")
        
        # 檢查時間範圍
        times = [row.get('time_ms', 0) for row in timeline]
        print(f"  時間範圍: {min(times)} ~ {max(times)} ms")
        print(f"  持續時間: {(max(times) - min(times)) / 1000:.1f} 秒")
        
        # 統計每種事件的 snapshot 分布
        print(f"\n  各事件類型的 snapshot 分布:")
        event_snapshots = {}
        for row in timeline:
            ev = row.get('event', 'unknown')
            snap = row.get('snapshot', 0)
            if ev not in event_snapshots:
                event_snapshots[ev] = set()
            event_snapshots[ev].add(snap)
        
        for ev, snaps in sorted(event_snapshots.items()):
            print(f"    {ev:25s}: {len(snaps):4d} 個唯一 snapshot")
            if len(snaps) > 2010:
                print(f"      ⚠️  超過 2000 個 snapshot！")
        
        # 檢查是否有重複的 snapshot
        print(f"\n  Snapshot 重複檢查:")
        for event_type in by_type.keys():
            event_rows = [r for r in timeline if r.get('event') == event_type]
            event_snaps = [r.get('snapshot', 0) for r in event_rows]
            unique_snaps = len(set(event_snaps))
            total_rows = len(event_rows)
            if total_rows != unique_snaps:
                print(f"    ⚠️  {event_type}: {total_rows} 記錄但只有 {unique_snaps} 個唯一 snapshot")
                # 找出重複的 snapshot
                from collections import Counter
                snap_counts = Counter(event_snaps)
                duplicates = {s: c for s, c in snap_counts.items() if c > 1}
                if duplicates:
                    print(f"       重複的 snapshot (前10個): {list(duplicates.items())[:10]}")
            else:
                print(f"    ✅ {event_type}: 無重複")

def main():
    stats_dir = Path("paper/satellite_networks_state/analytic_result")
    
    # 查找所有統計文件
    patterns = [
        "baseline_floyd_warshall_signaling_stats.json",
        "hierarchical_gid_*deg_signaling_stats.json",
        "lohi_signaling_stats*.json"
    ]
    
    all_files = []
    for pattern in patterns:
        files = glob.glob(str(stats_dir / pattern))
        # 排除 dijkstra 版本（如果要看就取消這行）
        files = [f for f in files if 'dijkstra' not in f]
        all_files.extend(files)
    
    if not all_files:
        print(f"❌ 在 {stats_dir} 找不到統計文件")
        return
    
    print(f"找到 {len(all_files)} 個統計文件\n")
    
    for file_path in sorted(all_files):
        try:
            diagnose_stats_file(file_path)
        except Exception as e:
            print(f"\n❌ 處理 {file_path} 時發生錯誤: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
