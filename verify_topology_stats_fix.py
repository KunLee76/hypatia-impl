#!/usr/bin/env python3
"""
Quick verification script to check if topology statistics fix is working
Compares data before and after the fix
"""

import json
import os
from pathlib import Path

def analyze_stats(filepath):
    """Extract key statistics from a signaling stats file"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    summary = data.get('summary', {})
    by_type = summary.get('by_type', {})
    timeline = data.get('timeline', [])
    
    # Count topology change events
    topo_count = by_type.get('topology_change', {}).get('count', 0)
    topo_events = [e for e in timeline if e.get('event') == 'topology_change']
    
    # Extract delta_isl values
    delta_isl_values = []
    isl_removed_values = []
    isl_added_values = []
    
    for event in topo_events:
        detail = event.get('detail', {})
        delta_isl_values.append(detail.get('delta_isl', 0))
        isl_removed_values.append(detail.get('isl_removed', 0))
        isl_added_values.append(detail.get('isl_added', 0))
    
    # Calculate statistics
    non_zero_deltas = [d for d in delta_isl_values if d != 0]
    total_removed = sum(isl_removed_values)
    total_added = sum(isl_added_values)
    
    return {
        'topo_count': topo_count,
        'topo_events': len(topo_events),
        'non_zero_deltas': len(non_zero_deltas),
        'total_removed': total_removed,
        'total_added': total_added,
        'delta_isl_values': delta_isl_values[:10],  # First 10 for inspection
    }

def main():
    print("=" * 80)
    print("Topology Statistics Fix Verification")
    print("=" * 80)
    print()
    
    result_dir = Path(__file__).parent / "paper/satellite_networks_state/analytic_result"
    
    # Check if new files exist
    baseline_files = {
        'p1': result_dir / "baseline_dynamic_p1_signaling_stats.json",
        'p5': result_dir / "baseline_dynamic_p5_signaling_stats.json",
        'p10': result_dir / "baseline_dynamic_p10_signaling_stats.json",
    }
    
    lohi_files = {
        'p1': result_dir / "lohi_dynamic_p1_signaling_stats.json",
        'p5': result_dir / "lohi_dynamic_p5_signaling_stats.json",
        'p10': result_dir / "lohi_dynamic_p10_signaling_stats.json",
    }
    
    # Analyze Baseline
    print("【Baseline Algorithm】")
    print()
    
    baseline_results = {}
    for scenario, filepath in baseline_files.items():
        if filepath.exists():
            stats = analyze_stats(filepath)
            baseline_results[scenario] = stats
            
            print(f"{scenario.upper()}:")
            print(f"  拓撲變化事件數: {stats['topo_count']}")
            print(f"  非零 delta 事件數: {stats['non_zero_deltas']}")
            print(f"  總 ISL 移除數: {stats['total_removed']}")
            print(f"  總 ISL 添加數: {stats['total_added']}")
            print(f"  前5個 delta_isl: {stats['delta_isl_values'][:5]}")
            print()
        else:
            print(f"{scenario.upper()}: 文件不存在")
            print()
    
    # Check if there's variation across failure rates
    if baseline_results:
        print("變化檢測:")
        removed_values = [baseline_results[s]['total_removed'] for s in ['p1', 'p5', 'p10'] if s in baseline_results]
        if len(set(removed_values)) > 1:
            print(f"  ✓ ISL 移除數隨失效率變化: {removed_values}")
        else:
            print(f"  ✗ ISL 移除數仍然相同: {removed_values}")
        print()
    
    # Analyze LoHi
    print("=" * 80)
    print("【LoHi Algorithm】")
    print()
    
    lohi_results = {}
    for scenario, filepath in lohi_files.items():
        if filepath.exists():
            stats = analyze_stats(filepath)
            lohi_results[scenario] = stats
            
            print(f"{scenario.upper()}:")
            print(f"  拓撲變化事件數: {stats['topo_count']}")
            print(f"  非零 delta 事件數: {stats['non_zero_deltas']}")
            print(f"  總 ISL 移除數: {stats['total_removed']}")
            print(f"  總 ISL 添加數: {stats['total_added']}")
            print(f"  前5個 delta_isl: {stats['delta_isl_values'][:5]}")
            print()
        else:
            print(f"{scenario.upper()}: 文件不存在")
            print()
    
    # Check if there's variation across failure rates
    if lohi_results:
        print("變化檢測:")
        
        # Check delta_isl variation
        has_delta_isl = any(lohi_results[s]['delta_isl_values'][0] != 0 
                           for s in ['p1', 'p5', 'p10'] 
                           if s in lohi_results and lohi_results[s]['delta_isl_values'])
        
        if has_delta_isl:
            print(f"  ✓ LoHi 現在記錄 delta_isl (新功能)")
        else:
            print(f"  ✗ LoHi 的 delta_isl 仍為 0")
        print()
    
    print("=" * 80)
    print()
    print("預期結果:")
    print("  1. Baseline 拓撲變化事件數應該 > 0 (修復前為 0)")
    print("  2. Baseline ISL 移除數應隨失效率增加: P1 < P5 < P10")
    print("  3. LoHi 現在應記錄 delta_isl 值 (修復前沒有此欄位)")
    print("  4. 兩個算法的 total_removed 都應隨失效率增加")
    print()

if __name__ == "__main__":
    main()
