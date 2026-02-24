#!/usr/bin/env python3
"""
合併 GRHR K 值場景的 temp 文件
用法: python3 merge_grhr_k_value.py <k_value>
例如: python3 merge_grhr_k_value.py 4
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

def merge_grhr_k_value(k_value):
    """合併指定 K 值的 temp 文件"""
    
    temp_dir = Path(f'paper/satellite_networks_state/analytic_result/temp_grhr_k{k_value}')
    output_file = Path(f'paper/satellite_networks_state/analytic_result/hierarchical_gid_27deg_k{k_value}_signaling_stats.json')
    
    if not temp_dir.exists():
        print(f"❌ 錯誤: 目錄 {temp_dir} 不存在")
        sys.exit(1)
    
    # 獲取所有 temp 文件
    temp_files = list(temp_dir.glob('grhr_stats_pid*_tid*.json'))
    
    if not temp_files:
        print(f"❌ 錯誤: {temp_dir} 中沒有找到 temp 文件")
        sys.exit(1)
    
    print(f"找到 {len(temp_files)} 個 temp 文件")
    
    # 使用所有文件進行合併（多線程並行運行，每個線程生成一個文件）
    recent_files = sorted(temp_files)
    
    print(f"使用所有 {len(recent_files)} 個文件進行合併")
    
    # 去重合併
    seen_events = set()
    all_events = []
    stats_by_type = defaultdict(lambda: {'count': 0, 'bytes': 0})
    
    for fpath in recent_files:
        with open(fpath, 'r') as f:
            data = json.load(f)
        
        timeline = data.get('timeline', [])
        
        for event in timeline:
            # 使用 (snapshot, time_ms, event_type, detail_json) 作為唯一鍵
            detail_json = json.dumps(event.get('detail', {}), sort_keys=True)
            key = (event['snapshot'], event['time_ms'], event['event'], detail_json)
            
            if key not in seen_events:
                seen_events.add(key)
                all_events.append(event)
                stats_by_type[event['event']]['count'] += event['count']
                stats_by_type[event['event']]['bytes'] += event.get('bytes', 0)
    
    # 按 snapshot 和 time_ms 排序
    all_events.sort(key=lambda x: (x['snapshot'], x['time_ms']))
    
    # 統計信息
    unique_snapshots = len(set(e['snapshot'] for e in all_events))
    routing_updates = stats_by_type.get('routing_update', {}).get('count', 0)
    gateway_updates = stats_by_type.get('gateway_update', {}).get('count', 0)
    gid_rebuilds = stats_by_type.get('gid_rebuild', {}).get('count', 0)
    
    # 構建輸出數據
    output_data = {
        'algorithm_display_name': f'GRHR (27°, K={k_value})',
        'grid_deg': 27,
        'k_best_gateways': k_value,
        'timeline': all_events,
        'summary': {
            'total_events': len(all_events),
            'unique_snapshots': unique_snapshots,
            'event_counts': dict(stats_by_type)
        }
    }
    
    # 保存文件
    with open(output_file, 'w') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    # 輸出統計
    print(f"\n合併完成:")
    print(f"  總事件數: {len(all_events)}")
    print(f"  不同的 snapshots: {unique_snapshots}")
    print(f"  routing_update: {routing_updates} ({routing_updates/unique_snapshots:.2f}/snapshot)")
    print(f"  gateway_update: {gateway_updates} ({gateway_updates/unique_snapshots:.2f}/snapshot)")
    print(f"  gid_rebuild: {gid_rebuilds}")
    print(f"\n✓ 已保存到: {output_file}")
    
    # 驗證數據正確性
    if unique_snapshots != 100:
        print(f"⚠️  警告: Snapshots 數量為 {unique_snapshots}，應為 100")
    
    if routing_updates / unique_snapshots > 2.0:
        print(f"⚠️  警告: routing_update 平均值過高 ({routing_updates/unique_snapshots:.2f}/snapshot)")
    
    return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("用法: python3 merge_grhr_k_value.py <k_value>")
        print("例如: python3 merge_grhr_k_value.py 4")
        sys.exit(1)
    
    try:
        k_value = int(sys.argv[1])
    except ValueError:
        print(f"❌ 錯誤: K 值必須是整數，收到: {sys.argv[1]}")
        sys.exit(1)
    
    print(f"=" * 80)
    print(f"合併 GRHR K={k_value} 的 temp 文件")
    print(f"=" * 80)
    
    merge_grhr_k_value(k_value)
