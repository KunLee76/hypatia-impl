#!/usr/bin/env python3
import json

# 檢查 Normal 場景中 Baseline 的 detail 欄位
normal_file = 'paper/satellite_networks_state/analytic_result/hierarchical_gid_27deg_signaling_stats.json'

print('=== Checking Baseline routing_update events in Normal scenario ===')
with open(normal_file, 'r') as f:
    data = json.load(f)

routing_updates = [e for e in data['timeline'] if e['event'] == 'routing_update'][:103]
print(f'First 3 Baseline routing_update events:')
for e in routing_updates[:3]:
    print(f'  Snapshot {e["snapshot"]}, bytes: {e.get("bytes", 0)}, detail: {e.get("detail", {})}')

print(f'\nTotal bytes in Normal scenario (Baseline): {sum(e.get("bytes", 0) for e in routing_updates)}')

print('\n=== Checking Baseline routing_update events in Dynamic P1 scenario ===')
dynamic_file = 'paper/satellite_networks_state/analytic_result/baseline_dynamic_p1_signaling_stats.json'
with open(dynamic_file, 'r') as f:
    data = json.load(f)

print(f'First 3 routing_update events:')
for e in data['timeline'][:3]:
    print(f'  Snapshot {e["snapshot"]}, bytes: {e.get("bytes", 0)}, detail: {e.get("detail", {})}')

print(f'\nTotal bytes in Dynamic P1 (raw): {sum(e.get("bytes", 0) for e in data["timeline"])}')
