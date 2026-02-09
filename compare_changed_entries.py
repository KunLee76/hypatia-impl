#!/usr/bin/env python3
import json

files = {
    'Normal': 'paper/satellite_networks_state/analytic_result/hierarchical_gid_27deg_signaling_stats.json',
    'Dynamic P1': 'paper/satellite_networks_state/analytic_result/baseline_dynamic_p1_signaling_stats.json',
    'Dynamic P5': 'paper/satellite_networks_state/analytic_result/baseline_dynamic_p5_signaling_stats.json',
    'Dynamic P10': 'paper/satellite_networks_state/analytic_result/baseline_dynamic_p10_signaling_stats.json',
}

for name, fpath in files.items():
    with open(fpath, 'r') as f:
        data = json.load(f)
    
    if name == 'Normal':
        timeline = [e for e in data['timeline'] if e['event'] == 'routing_update'][:103]
    else:
        timeline = data['timeline']
    
    total_changed = sum(e.get('detail', {}).get('changed_entries', 0) for e in timeline)
    print(f'{name}: {len(timeline)} events, {total_changed} total changed_entries')
    
    # Sample first 3 events
    print(f'  First 3: {[e.get("detail", {}).get("changed_entries") for e in timeline[:3]]}')
