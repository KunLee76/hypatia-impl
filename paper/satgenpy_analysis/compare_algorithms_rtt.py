"""
Compare RTT performance between LoHi and GRHR algorithms.

Usage:
    python compare_algorithms_rtt.py <data_dir> <duration_s> <src_id> <dst_id>

Example:
    python compare_algorithms_rtt.py data 20 720 721
"""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

def read_ground_stations(gs_file_path):
    """
    Read ground station information.
    
    Returns:
        dict: {gs_id: gs_name, ...}
    """
    gs_dict = {}
    if not os.path.exists(gs_file_path):
        print(f"Warning: Ground stations file not found: {gs_file_path}")
        return gs_dict
    
    with open(gs_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) < 2:
                continue
            gs_id = int(parts[0])
            gs_name = parts[1]
            # Remove dashes and convert to more readable format
            # e.g., "New-York-Newark" -> "New York Newark"
            gs_name = gs_name.replace('-', ' ')
            # Handle special cases with parentheses
            # e.g., "Mumbai-(Bombay)" -> "Mumbai"
            if '(' in gs_name:
                gs_name = gs_name.split('(')[0].strip()
            gs_dict[gs_id] = gs_name
    
    return gs_dict

def extract_constellation_name(file_path):
    """
    Extract constellation name from file path.
    
    Example:
        "data/oneweb_1200_isls_plus_grid_.../..." -> "oneweb_1200"
    """
    parts = file_path.split('/')
    for part in parts:
        if 'oneweb' in part.lower() or 'starlink' in part.lower() or 'kuiper' in part.lower():
            # Extract constellation name before "_isls_"
            if '_isls_' in part:
                return part.split('_isls_')[0]
            # Fallback: take first two parts (e.g., "oneweb_1200")
            subparts = part.split('_')
            if len(subparts) >= 2:
                return '_'.join(subparts[:2])
    return "Unknown"

def read_rtt_file(file_path):
    """
    Read RTT data from file.
    
    Returns:
        list of tuples: [(time_ns, rtt_ns), ...]
    """
    data = []
    if not os.path.exists(file_path):
        print(f"Warning: File not found: {file_path}")
        return data
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) != 2:
                continue
            time_ns = int(parts[0])
            rtt_ns = float(parts[1])
            data.append((time_ns, rtt_ns))
    
    return data

def plot_comparison(lohi_data, grhr_data, src_id, dst_id, src_name, dst_name, constellation_name, duration_s, output_path):
    """
    Plot RTT comparison between LoHi and GRHR.
    
    Args:
        lohi_data: List of (time_ns, rtt_ns) for LoHi
        grhr_data: List of (time_ns, rtt_ns) for GRHR
        src_id: Source node ID
        dst_id: Destination node ID
        src_name: Source node name
        dst_name: Destination node name
        constellation_name: Name of satellite constellation
        duration_s: Duration in seconds
        output_path: Output file path
    """
    # Adjusted figure size
    fig, ax = plt.subplots(figsize=(9, 6))
    
    # Convert to milliseconds and seconds
    if lohi_data:
        lohi_times = [t[0] / 1e9 for t in lohi_data]  # ns to seconds
        lohi_rtts = [t[1] / 1e6 for t in lohi_data]   # ns to milliseconds
        ax.plot(lohi_times, lohi_rtts, 
                color='orangered', 
                linewidth=2, 
                label='LoHi',
                marker='o',
                markersize=3,
                alpha=0.8)
    
    if grhr_data:
        grhr_times = [t[0] / 1e9 for t in grhr_data]  # ns to seconds
        grhr_rtts = [t[1] / 1e6 for t in grhr_data]   # ns to milliseconds
        ax.plot(grhr_times, grhr_rtts, 
                color='green', 
                linewidth=2, 
                label='GRHR',
                marker='s',
                markersize=3,
                alpha=0.8)
    
    # Formatting
    ax.set_xlabel('Time (seconds)', fontsize=14, fontweight='bold')
    ax.set_ylabel('RTT (ms)', fontsize=14, fontweight='bold')
    ax.set_title(f'{constellation_name}: {src_name} → {dst_name}', 
                 fontsize=16, fontweight='bold', pad=20)
    
    # Grid - 虛線樣式
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    
    # Legend - 放在圖內
    ax.legend(loc='best', fontsize=12, framealpha=0.9)
    
    # Set x-axis limits and ticks - 每 2 秒一個刻度
    ax.set_xlim(0, duration_s)
    ax.set_xticks(np.arange(0, duration_s + 1, 2))  # 0, 2, 4, 6, ..., duration_s
    
    # Tight layout
    plt.tight_layout()
    
    # Save
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Plot saved to: {output_path}")
    
    # Statistics
    print("\n" + "=" * 70)
    print(f"Statistics Summary: {src_name} → {dst_name}")
    print("=" * 70)
    
    if lohi_data:
        lohi_rtts_valid = [r for r in lohi_rtts if r > 0]
        if lohi_rtts_valid:
            print(f"\nLoHi:")
            print(f"  - Data points: {len(lohi_data)}")
            print(f"  - Min RTT: {min(lohi_rtts_valid):.2f} ms")
            print(f"  - Max RTT: {max(lohi_rtts_valid):.2f} ms")
            print(f"  - Avg RTT: {sum(lohi_rtts_valid)/len(lohi_rtts_valid):.2f} ms")
            unreachable_count = len([r for r in lohi_rtts if r == 0])
            if unreachable_count > 0:
                print(f"  - Unreachable: {unreachable_count} / {len(lohi_data)} ({unreachable_count/len(lohi_data)*100:.1f}%)")
    
    if grhr_data:
        grhr_rtts_valid = [r for r in grhr_rtts if r > 0]
        if grhr_rtts_valid:
            print(f"\nGRHR:")
            print(f"  - Data points: {len(grhr_data)}")
            print(f"  - Min RTT: {min(grhr_rtts_valid):.2f} ms")
            print(f"  - Max RTT: {max(grhr_rtts_valid):.2f} ms")
            print(f"  - Avg RTT: {sum(grhr_rtts_valid)/len(grhr_rtts_valid):.2f} ms")
            unreachable_count = len([r for r in grhr_rtts if r == 0])
            if unreachable_count > 0:
                print(f"  - Unreachable: {unreachable_count} / {len(grhr_data)} ({unreachable_count/len(grhr_data)*100:.1f}%)")
    
    if lohi_rtts_valid and grhr_rtts_valid:
        lohi_avg = sum(lohi_rtts_valid) / len(lohi_rtts_valid)
        grhr_avg = sum(grhr_rtts_valid) / len(grhr_rtts_valid)
        improvement = ((lohi_avg - grhr_avg) / lohi_avg) * 100
        print(f"\nComparison:")
        if improvement > 0:
            print(f"  🎯 GRHR is {improvement:.1f}% better than LoHi")
        else:
            print(f"  🎯 LoHi is {-improvement:.1f}% better than GRHR")
    
    print("=" * 70)

def main():
    if len(sys.argv) != 6:
        print("Usage: python compare_algorithms_rtt.py <data_dir> <constellation> <duration_s> <src_id> <dst_id>")
        print("\nExample:")
        print("  python compare_algorithms_rtt.py data oneweb_1200 20 720 721")
        print("  python compare_algorithms_rtt.py data starlink_550 20 720 721")
        sys.exit(1)
    
    data_dir = sys.argv[1]
    constellation_name = sys.argv[2]
    duration_s = int(sys.argv[3])
    src_id = sys.argv[4]
    dst_id = sys.argv[5]
    
    print("=" * 70)
    print("RTT Algorithm Comparison Tool")
    print("=" * 70)
    print(f"Constellation: {constellation_name.upper()}")
    print(f"Data directory: {data_dir}")
    print(f"Duration: {duration_s}s")
    print(f"Route: {src_id} → {dst_id}")
    print("=" * 70)
    
    # Search for matching algorithm directories
    lohi_candidates = [d for d in os.listdir(data_dir) 
                      if constellation_name in d and 'algorithm_lohi' in d]
    grhr_candidates = [d for d in os.listdir(data_dir) 
                      if constellation_name in d and 'algorithm_hierarchical_virtual_gid' in d]
    
    if not lohi_candidates or not grhr_candidates:
        print(f"\n❌ Error: Could not find algorithm directories for {constellation_name}!")
        if not lohi_candidates:
            print(f"  - LoHi directory not found (should contain '{constellation_name}' and 'algorithm_lohi')")
        if not grhr_candidates:
            print(f"  - GRHR directory not found (should contain '{constellation_name}' and 'algorithm_hierarchical_virtual_gid')")
        sys.exit(1)
    
    lohi_pattern = lohi_candidates[0]
    grhr_pattern = grhr_candidates[0]
    
    lohi_file = os.path.join(
        data_dir,
        lohi_pattern,
        f"100ms_for_{duration_s}s",
        "manual",
        "data",
        f"networkx_rtt_{src_id}_to_{dst_id}.txt"
    )
    
    grhr_file = os.path.join(
        data_dir,
        grhr_pattern,
        f"100ms_for_{duration_s}s",
        "manual",
        "data",
        f"networkx_rtt_{src_id}_to_{dst_id}.txt"
    )
    
    # Find ground stations file
    gs_file_pattern = lohi_pattern.replace('_algorithm_lohi', '')
    gs_file = None
    
    # Search in satellite_networks_state/gen_data/
    potential_gs_paths = [
        os.path.join(data_dir, "..", "..", "satellite_networks_state", "gen_data", gs_file_pattern, "ground_stations.txt"),
        os.path.join(data_dir, "..", "..", "satellite_networks_state", "gen_data", lohi_pattern, "ground_stations.txt"),
    ]
    
    for path in potential_gs_paths:
        normalized_path = os.path.normpath(path)
        if os.path.exists(normalized_path):
            gs_file = normalized_path
            break
    
    # Read ground station names and determine actual number of satellites
    gs_dict = {}
    num_satellites = 0
    
    if gs_file:
        gs_dict = read_ground_stations(gs_file)
        
        # Determine actual number of satellites from TLE file
        tles_file = gs_file.replace('ground_stations.txt', 'tles.txt')
        if os.path.exists(tles_file):
            with open(tles_file, 'r') as f:
                num_satellites = sum(1 for line in f) // 3  # Each satellite has 3 lines in TLE
        else:
            # Fallback: calculate from source node ID
            # The first GS node ID should equal the number of satellites
            num_satellites = int(src_id)
        
        print(f"Ground stations file: {gs_file}")
        print(f"Loaded {len(gs_dict)} ground stations")
        print(f"Satellites: {num_satellites}, Ground stations start from ID {num_satellites}")
    else:
        print("⚠️  Warning: Ground stations file not found, using IDs instead of names")
        # Fallback: assume source ID is the first ground station
        num_satellites = int(src_id)
    
    # Get names or use IDs as fallback
    src_gs_index = int(src_id) - num_satellites
    dst_gs_index = int(dst_id) - num_satellites
    
    src_name = gs_dict.get(src_gs_index, f"GS-{src_id}")
    dst_name = gs_dict.get(dst_gs_index, f"GS-{dst_id}")
    
    # Output path
    output_dir = os.path.join(data_dir, "algorithm_comparison")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(
        output_dir,
        f"rtt_comparison_{src_id}_to_{dst_id}_{duration_s}s.pdf"
    )
    
    print(f"\nReading data files...")
    print(f"  LoHi: {lohi_file}")
    print(f"  GRHR: {grhr_file}")
    
    # Read data
    lohi_data = read_rtt_file(lohi_file)
    grhr_data = read_rtt_file(grhr_file)
    
    if not lohi_data and not grhr_data:
        print("\n❌ Error: No data found in either file!")
        sys.exit(1)
    
    if not lohi_data:
        print("\n⚠️  Warning: No LoHi data found")
    if not grhr_data:
        print("\n⚠️  Warning: No GRHR data found")
    
    # Plot
    print(f"\nGenerating comparison plot...")
    print(f"Constellation: {constellation_name}")
    print(f"Route: {src_name} ({src_id}) → {dst_name} ({dst_id})")
    plot_comparison(lohi_data, grhr_data, src_id, dst_id, src_name, dst_name, constellation_name, duration_s, output_path)

if __name__ == "__main__":
    main()
