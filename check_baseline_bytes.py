#!/usr/bin/env python3
import json

# 對比 Baseline Normal 和 Dynamic P1
normal_file = 'paper/satellite_networks_state/analytic_result/hierarchical_gid_27deg_signaling_stats.json'
dynamic_file = 'paper/satellite_networks_state/analytic_result/baseline_dynamic_p1_signaling_stats.json'

print('=== Baseline Normal (no Chaos Monkey) ===')
with open(normal_file, 'r') as f:
    data = json.load(f)

# Find Baseline events
baseline_events = [e for e in data['timeline'] if 'Baseline' in str(e)]
if not baseline_events:
    # Check algorithm field
    baseline_events = [e for e in data['timeline'] if e.get('algorithm') == 'baseline' or e['event'] == 'routing_update']
    # Take first 103 routing_update events (Baseline's contribution)
    routing_updates = [e for e in data['timeline'] if e['event'] == 'routing_update'][:103]
    print(f'First 103 routing_update events: {len(routing_updates)}')
    print(f'Event types: {set(e["event"] for e in routing_updates)}')

print('\n=== Baseline Dynamic P1 (1% ISL Failure) ===')
with open(dynamic_file, 'r') as f:
    data = json.load(f)

print(f'Total events: {len(data["timeline"])}')
print(f'Event types: {set(e["event"] for e in data["timeline"])}')
print(f'Total bytes: {sum(e.get("bytes", 0) for e in data["timeline"])}')

# 檢查 bytes 是否都是 0
bytes_list = [e.get('bytes', 0) for e in data['timeline']]
print(f'Bytes per event (first 10): {bytes_list[:10]}')
print(f'All bytes zero?: {all(b == 0 for b in bytes_list)}')
