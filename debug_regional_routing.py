 #!/usr/bin/env python3

"""
Debug script to analyze the geographical grouping routing issues.
"""

import sys
import os
import networkx as nx
from collections import defaultdict

# Add satgenpy to path
sys.path.append('/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')

def analyze_fstate_file(fstate_path):
    """Analyze fstate file to understand routing issues."""
    print(f"Analyzing fstate file: {fstate_path}")
    
    # Read fstate file
    satellite_routes = defaultdict(list)
    with open(fstate_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split(',')
                if len(parts) >= 3:
                    src = int(parts[0])
                    dst = int(parts[1])
                    next_hop = int(parts[2])
                    satellite_routes[src].append((dst, next_hop))
    
    print(f"Total satellites with routes: {len(satellite_routes)}")
    
    # Check which satellites have no routes
    all_satellites = set()
    for src in satellite_routes:
        all_satellites.add(src)
        for dst, next_hop in satellite_routes[src]:
            all_satellites.add(dst)
            all_satellites.add(next_hop)
    
    max_sat = max(all_satellites) if all_satellites else 0
    satellites_without_routes = []
    for i in range(max_sat + 1):
        if i not in satellite_routes:
            satellites_without_routes.append(i)
    
    print(f"Satellites without routes: {satellites_without_routes[:20]}")  # Show first 20
    
    # Check specific routes for 625->626, 625->627
    if 625 in satellite_routes:
        routes_625 = satellite_routes[625]
        print(f"Routes from satellite 625:")
        for dst, next_hop in routes_625:
            if dst in [626, 627]:
                print(f"  625 -> {dst}: next_hop = {next_hop}")
                
                # Check if next_hop has routes
                if next_hop in satellite_routes:
                    next_routes = satellite_routes[next_hop]
                    has_route_to_dst = any(d == dst for d, _ in next_routes)
                    print(f"    Next hop {next_hop} has {len(next_routes)} routes, has route to {dst}: {has_route_to_dst}")
                else:
                    print(f"    Next hop {next_hop} has NO routes!")
    else:
        print("No routes found for satellite 625")
    
    return satellite_routes, satellites_without_routes

def check_isl_connectivity(isls_path):
    """Check ISL connectivity."""
    print(f"\nAnalyzing ISL file: {isls_path}")
    
    G = nx.Graph()
    with open(isls_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    sat1 = int(parts[0])
                    sat2 = int(parts[1])
                    G.add_edge(sat1, sat2)
    
    print(f"ISL graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    
    # Check connectivity between satellites 0-5 and 625-627
    problem_sats = list(range(6))  # 0-5
    target_sats = [625, 626, 627]
    
    for prob_sat in problem_sats:
        if prob_sat in G:
            print(f"Satellite {prob_sat} has {G.degree(prob_sat)} ISL connections")
            neighbors = list(G.neighbors(prob_sat))
            print(f"  Neighbors: {neighbors[:5]}...")  # Show first 5
        else:
            print(f"Satellite {prob_sat} not in ISL graph")
    
    # Check if 625, 626, 627 are connected
    for sat in target_sats:
        if sat in G:
            print(f"Satellite {sat} has {G.degree(sat)} ISL connections")
            # Check path to satellite 0
            if 0 in G and nx.has_path(G, 0, sat):
                path_length = nx.shortest_path_length(G, 0, sat)
                print(f"  Path from 0 to {sat}: length {path_length}")
            else:
                print(f"  No path from 0 to {sat}")
        else:
            print(f"Satellite {sat} not in ISL graph")
    
    return G

def main():
    # Check if custom fstate path is provided
    if len(sys.argv) > 1:
        fstate_path = sys.argv[1]
        if not os.path.isabs(fstate_path):
            # If relative path, make it absolute from current directory
            fstate_path = os.path.abspath(fstate_path)
    else:
        # Default paths
        base_path = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_region/dynamic_state_100ms_for_2000s"
        fstate_path = os.path.join(base_path, "fstate_0.txt")
    
    # Check input data paths
    input_base = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/input_data/starlink_550"
    isls_path = os.path.join(input_base, "isls.txt") 
    
    if not os.path.exists(fstate_path):
        print(f"fstate file not found: {fstate_path}")
        return
    
    # Analyze fstate
    satellite_routes, satellites_without_routes = analyze_fstate_file(fstate_path)
    
    # Check ISL connectivity if file exists
    if os.path.exists(isls_path):
        isl_graph = check_isl_connectivity(isls_path)
    else:
        print(f"ISL file not found: {isls_path}")
        # Try other possible locations
        for possible_isl in [
            "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/input_data/starlink_550/isls_0.txt",
            "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_region/isls.txt"
        ]:
            if os.path.exists(possible_isl):
                print(f"Found ISL file at: {possible_isl}")
                isl_graph = check_isl_connectivity(possible_isl)
                break
        else:
            print("No ISL file found")

if __name__ == "__main__":
    main()
