#!/usr/bin/env python3
import json

# TLV 控制訊息格式常數
CTRL_HDR_BYTES = 32          # 控制訊息標頭
ROUTE_ENTRY_BYTES = 32       # 路由表項

def calculate_event_bytes(event, is_lohi=False):
    """根據事件類型和detail計算字節數"""
    ev_type = event.get('event') or event.get('type')
    if not ev_type:
        return 0
    
    detail = event.get('detail') or {}
    
    if ev_type == 'routing_update':
        n_entries = int(detail.get('changed_entries', 0) or 0)
        return CTRL_HDR_BYTES + n_entries * ROUTE_ENTRY_BYTES
    
    return 0

# Test on Baseline Dynamic P1
dynamic_file = 'paper/satellite_networks_state/analytic_result/baseline_dynamic_p1_signaling_stats.json'
with open(dynamic_file, 'r') as f:
    data = json.load(f)

total_bytes = 0
for event in data['timeline']:
    total_bytes += calculate_event_bytes(event, False)

print(f'Baseline Dynamic P1 recalculated total bytes: {total_bytes} bytes = {total_bytes/1024:.2f} KB')

# Test on Normal scenario
normal_file = 'paper/satellite_networks_state/analytic_result/hierarchical_gid_27deg_signaling_stats.json'
with open(normal_file, 'r') as f:
    data = json.load(f)

routing_updates = [e for e in data['timeline'] if e['event'] == 'routing_update'][:103]
total_bytes = 0
for event in routing_updates:
    total_bytes += calculate_event_bytes(event, False)

print(f'Baseline Normal recalculated total bytes: {total_bytes} bytes = {total_bytes/1024:.2f} KB')
