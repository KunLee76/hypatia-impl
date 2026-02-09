#!/usr/bin/env python3
import json

# 檢查三個算法的拓撲變化事件
files = {
    'Baseline': 'paper/satellite_networks_state/analytic_result/baseline_dynamic_p1_signaling_stats.json',
    'LoHi': 'paper/satellite_networks_state/analytic_result/lohi_dynamic_p1_signaling_stats.json',
    'GRHR': 'paper/satellite_networks_state/analytic_result/hierarchical_gid_27deg_dynamic_p1_k4_signaling_stats.json'
}

for algo, fpath in files.items():
    print(f'=== {algo} ===')
    with open(fpath, 'r') as f:
        data = json.load(f)
    
    topo_changes = [e for e in data['timeline'] if e['event'] == 'topology_change']
    print(f'Topology_change events: {len(topo_changes)}')
    
    if topo_changes:
        print(f'First 3 topology changes: ')
        for e in topo_changes[:3]:
            print(f'  Snapshot {e["snapshot"]}, time {e["time_ms"]}ms, detail: {e.get("detail", {})}')
    print()
