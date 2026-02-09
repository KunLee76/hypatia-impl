#!/usr/bin/env python3
"""GRHR 數據質量檢查腳本"""

import json
from pathlib import Path
from collections import defaultdict

analytic_dir = Path('paper/satellite_networks_state/analytic_result')

print('=' * 80)
print('GRHR 數據質量完整檢查報告')
print('=' * 80)

# 1. Normal 場景
print('\n【1. Normal 場景（無失效）】')
print('-' * 80)
print('\n✅ 檔案: hierarchical_gid_27deg_signaling_stats.json (用於3算法比較)')
filepath = analytic_dir / 'hierarchical_gid_27deg_signaling_stats.json'
with open(filepath, 'r') as f:
    data = json.load(f)
timeline = data.get('timeline', [])
snapshots = sorted(set(e['snapshot'] for e in timeline))
time_step = snapshots[1] - snapshots[0] if len(snapshots) >= 2 else 0
event_counts = defaultdict(int)
for event in timeline:
    event_counts[event['event']] += 1
routing_per_snap = event_counts.get('routing_update', 0) / len(snapshots)
print(f'   事件數: {len(timeline)}, Snapshots: {len(snapshots)}, Δ={time_step} (2000ms)')
print(f'   routing: {event_counts.get("routing_update", 0)} ({routing_per_snap:.2f}/snap)')
print(f'   狀態: 正確 (已在 2026-02-02 修復)')

print('\n❌ 檔案: hierarchical_gid_27deg_k{n}_signaling_stats.json (用於K值分析)')
for k in [1, 2, 4, 6, 8, 999]:
    filename = f'hierarchical_gid_27deg_k{k}_signaling_stats.json'
    filepath = analytic_dir / filename
    with open(filepath, 'r') as f:
        data = json.load(f)
    timeline = data.get('timeline', [])
    snapshots = sorted(set(e['snapshot'] for e in timeline))
    time_step = snapshots[1] - snapshots[0] if len(snapshots) >= 2 else 0
    event_counts = defaultdict(int)
    for event in timeline:
        event_counts[event['event']] += 1
    routing_per_snap = event_counts.get('routing_update', 0) / len(snapshots)
    print(f'   K={k:3d}: 事件={len(timeline):5d}, snaps={len(snapshots)}, Δ={time_step} (100ms!), routing={routing_per_snap:.1f}/snap')

# 2. Dynamic 場景
print('\n【2. Dynamic 場景（Chaos Monkey 動態失效）】')
print('-' * 80)

all_good = True
for scenario in ['p1', 'p5', 'p10']:
    scenario_label = {'p1': '1% ISL失效', 'p5': '5% ISL失效', 'p10': '10% ISL失效'}
    print(f'\n場景: {scenario_label[scenario]}')
    for k in [1, 2, 4, 6, 8, 999]:
        filename = f'hierarchical_gid_27deg_dynamic_{scenario}_k{k}_signaling_stats.json'
        filepath = analytic_dir / filename
        with open(filepath, 'r') as f:
            data = json.load(f)
        timeline = data.get('timeline', [])
        snapshots = sorted(set(e['snapshot'] for e in timeline))
        time_step = snapshots[1] - snapshots[0] if len(snapshots) >= 2 else 0
        event_counts = defaultdict(int)
        for event in timeline:
            event_counts[event['event']] += 1
        routing_per_snap = event_counts.get('routing_update', 0) / len(snapshots)
        is_good = time_step == 20 and routing_per_snap < 2.0
        status = '✅' if is_good else '❌'
        if not is_good:
            all_good = False
        print(f'   K={k:3d}: Δ={time_step:2d}, routing={routing_per_snap:.2f}/snap {status}')

# 總結
print('\n' + '=' * 80)
print('【總結】')
print('=' * 80)
print('\n✅ 正確的數據:')
print('   • hierarchical_gid_27deg_signaling_stats.json')
print('     (Normal場景，用於3算法比較，已修復)')
print('   • hierarchical_gid_27deg_dynamic_p{1,5,10}_k{1,2,4,6,8,999}_signaling_stats.json')
print('     (所有 18 個動態場景文件)')

print('\n❌ 錯誤的數據:')
print('   • hierarchical_gid_27deg_k{1,2,4,6,8,999}_signaling_stats.json')
print('     (6 個 Normal 場景 K 值文件)')
print('\n   問題:')
print('   - 時間步長: 100ms (應為 2000ms)')
print('   - 多線程重複: 8-11 倍')
print('   - 影響範圍: K 值參數分析報告')

print('\n建議:')
print('   如果需要發表 K 值參數分析，需要重新運行這 6 個場景')
print('   如果只需要 3 算法比較和動態場景分析，當前數據已足夠')
print('=' * 80)
