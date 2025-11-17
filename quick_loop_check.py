#!/usr/bin/env python3
import sys

fstate_file = sys.argv[1] if len(sys.argv) > 1 else 'paper/satellite_networks_state/gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_lohi/dynamic_state_100ms_for_1s/fstate_0.txt'

# Build routing table
routing = {}
with open(fstate_file) as f:
    for line in f:
        parts = line.strip().split(',')
        if len(parts) == 5:
            src, dst, next_hop = int(parts[0]), int(parts[1]), int(parts[2])
            routing[(src, dst)] = next_hop

total = len(routing)
loops = 0

# Check for loops
for (src, dst), first_hop in routing.items():
    visited = {src}
    current = first_hop
    
    for _ in range(100):  # Max 100 hops
        if current == dst:
            break
        if current in visited:
            loops += 1
            break
        visited.add(current)
        current = routing.get((current, dst), dst)

print(f'總路由數: {total}')
print(f'Routing loops: {loops}')
print(f'Loop率: {loops/total*100:.4f}%')
