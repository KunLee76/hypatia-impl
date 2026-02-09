#!/usr/bin/env python3
import json
from collections import defaultdict

# 檢查 Baseline Dynamic P1 數據
baseline_file = 'paper/satellite_networks_state/analytic_result/baseline_dynamic_p1_signaling_stats.json'
lohi_file = 'paper/satellite_networks_state/analytic_result/lohi_dynamic_p1_signaling_stats.json'
grhr_file = 'paper/satellite_networks_state/analytic_result/hierarchical_gid_27deg_dynamic_p1_k4_signaling_stats.json'

print('=== Baseline Dynamic P1 (1% ISL Failure) ===')
with open(baseline_file, 'r') as f:
    data = json.load(f)
timeline = data['timeline']
event_counts = defaultdict(int)
for e in timeline:
    event_counts[e['event']] += 1
print(f'Total events: {len(timeline)}')
print(f'Event breakdown: {dict(event_counts)}')
print(f'Snapshots with events: {len(set(e["snapshot"] for e in timeline))}')
print(f'First 5 events: {[{k:v for k,v in e.items() if k != "detail"} for e in timeline[:5]]}')

print('\n=== LoHi Dynamic P1 ===')
with open(lohi_file, 'r') as f:
    data = json.load(f)
timeline = data['timeline']
event_counts = defaultdict(int)
for e in timeline:
    event_counts[e['event']] += 1
print(f'Total events: {len(timeline)}')
print(f'Event breakdown: {dict(event_counts)}')
print(f'Snapshots with events: {len(set(e["snapshot"] for e in timeline))}')

print('\n=== GRHR Dynamic P1 K=4 ===')
with open(grhr_file, 'r') as f:
    data = json.load(f)
timeline = data['timeline']
event_counts = defaultdict(int)
for e in timeline:
    event_counts[e['event']] += 1
print(f'Total events: {len(timeline)}')
print(f'Event breakdown: {dict(event_counts)}')
print(f'Snapshots with events: {len(set(e["snapshot"] for e in timeline))}')
