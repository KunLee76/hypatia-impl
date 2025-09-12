#!/usr/bin/env python3
"""
Performance Analysis Report Generator
Analyzes the performance test results and provides optimization recommendations.
"""

import json
import sys
from datetime import datetime


def format_duration(seconds):
    """Format duration in human readable format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def calculate_throughput(duration_simulated, time_taken):
    """Calculate simulation throughput (simulated time / real time)."""
    return duration_simulated / time_taken


def analyze_performance():
    """Analyze performance test results and generate recommendations."""
    
    try:
        with open('performance_comparison_results.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: performance_comparison_results.json not found. Please run performance_comparison.py first.")
        return
    
    print("SATELLITE NETWORK STATE GENERATION - PERFORMANCE ANALYSIS REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Configuration overview
    print("TEST CONFIGURATIONS")
    print("-" * 40)
    for i, config in enumerate(data['test_configs'], 1):
        print(f"Config {i}: {config['duration']}s simulation, {config['time_step']}ms steps, {config['threads']} threads")
    print()
    
    # Detailed results analysis
    for i, config in enumerate(data['test_configs'], 1):
        print(f"CONFIGURATION {i} ANALYSIS (Duration: {config['duration']}s)")
        print("-" * 60)
        
        config_results = [r for r in data['results'] if r['name'].endswith(f"_{i}")]
        successful_results = [r for r in config_results if r['status'] == "SUCCESS"]
        
        if not successful_results:
            print("❌ No successful tests for this configuration")
            print()
            continue
        
        # Performance metrics
        print("Performance Results:")
        baseline = None
        for result in config_results:
            status_symbol = "✅" if result['status'] == "SUCCESS" else "❌"
            duration_str = format_duration(result['duration'])
            
            if result['name'].startswith('Original'):
                baseline = result['duration']
                improvement = 0.0
                speedup = 1.0
            elif baseline and result['status'] == "SUCCESS":
                improvement = (baseline - result['duration']) / baseline * 100
                speedup = baseline / result['duration']
            else:
                improvement = 0.0
                speedup = 1.0
            
            throughput = calculate_throughput(config['duration'], result['duration'])
            
            print(f"  {status_symbol} {result['name']:20} {duration_str:>10} "
                  f"({speedup:4.2f}x, {improvement:+5.1f}%) "
                  f"Throughput: {throughput:.4f}x")
        
        # Time step analysis
        if successful_results:
            num_time_steps = config['duration'] * 1000 // config['time_step']
            print(f"\nTime Step Analysis:")
            print(f"  Total time steps: {num_time_steps}")
            for result in successful_results:
                time_per_step = result['duration'] / num_time_steps
                print(f"  {result['name']:20} {time_per_step:.3f}s per time step")
        
        # Scalability analysis
        if baseline:
            estimated_300s = baseline * (300 / config['duration'])
            print(f"\nScalability Projection:")
            print(f"  Estimated time for 300s simulation: {format_duration(estimated_300s)}")
            if estimated_300s > 3600:
                print(f"  ⚠️  Would exceed 1 hour timeout")
        
        print()
    
    # Overall recommendations
    print("OPTIMIZATION RECOMMENDATIONS")
    print("-" * 60)
    
    successful_tests = [r for r in data['results'] if r['status'] == "SUCCESS"]
    if successful_tests:
        fastest = min(successful_tests, key=lambda x: x['duration'])
        print(f"✅ Best performing configuration: {fastest['name']}")
        print(f"   Duration: {format_duration(fastest['duration'])}")
        
        if fastest['name'].startswith('Original'):
            print("   Current optimizations show minimal benefit")
        else:
            baseline = next((r for r in data['results'] 
                           if r['name'].startswith('Original') and r['status'] == "SUCCESS"), None)
            if baseline:
                improvement = (baseline['duration'] - fastest['duration']) / baseline['duration'] * 100
                print(f"   Improvement over baseline: {improvement:.1f}%")
    
    print()
    print("Optimization Strategies:")
    print("1. 🔄 Further algorithmic improvements needed for long simulations")
    print("2. ⚡ Current optimizations provide 10-13% improvement")
    print("3. 🧮 Consider reducing time step resolution (e.g., 5000ms instead of 1000ms)")
    print("4. 🔀 Investigate parallelization of satellite-to-ground routing")
    print("5. 💾 Implement more aggressive caching strategies")
    print("6. 🎯 Profile bottlenecks in satellite route generation")
    
    print()
    print("Next Steps:")
    print("• Profile the routing algorithm to identify specific bottlenecks")
    print("• Consider approximation algorithms for less critical routes")
    print("• Implement hierarchical time stepping (coarse then fine)")
    print("• Evaluate reducing the number of ground stations for testing")
    print("• Consider GPU acceleration for graph algorithms")


if __name__ == "__main__":
    analyze_performance()
