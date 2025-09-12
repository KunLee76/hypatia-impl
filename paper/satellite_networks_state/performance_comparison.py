#!/usr/bin/env python3
"""
Performance comparison script for satellite network state generation.
Tests different optimization configurations and measures their impact.
"""

import subprocess
import time
import sys
import os
import shutil
import json
from datetime import datetime


def run_test(name, command, description):
    """Run a test and measure its performance."""
    print(f"\n{'='*60}")
    print(f"Running test: {name}")
    print(f"Description: {description}")
    print(f"Command: {command}")
    print('='*60)
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            status = "SUCCESS"
            print(f"✓ Test completed successfully in {duration:.2f} seconds")
        else:
            status = "FAILED"
            print(f"✗ Test failed after {duration:.2f} seconds")
            print(f"Error: {result.stderr}")
        
        return {
            'name': name,
            'description': description,
            'command': command,
            'duration': duration,
            'status': status,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'timestamp': datetime.now().isoformat()
        }
        
    except subprocess.TimeoutExpired:
        print(f"✗ Test timed out after 1 hour")
        return {
            'name': name,
            'description': description,
            'command': command,
            'duration': 3600,
            'status': "TIMEOUT",
            'stdout': "",
            'stderr': "Process timed out",
            'timestamp': datetime.now().isoformat()
        }


def cleanup_gen_data():
    """Clean up generated data to ensure fair comparison."""
    if os.path.exists("gen_data"):
        shutil.rmtree("gen_data")
    print("Cleaned up gen_data directory")


def main():
    """Run performance comparison tests."""
    print("Satellite Network State Generation - Performance Comparison")
    print("=" * 60)
    
    # Test parameters - start with small values for quick testing
    test_configs = [
        {
            "duration": 60,      # 60 seconds
            "time_step": 1000,   # 1 second steps
            "algorithm": "algorithm_hierarchical_region",
            "threads": 4
        },
        {
            "duration": 300,     # 5 minutes
            "time_step": 1000,   # 1 second steps
            "algorithm": "algorithm_hierarchical_region", 
            "threads": 4
        }
    ]
    
    results = []
    
    for i, config in enumerate(test_configs):
        print(f"\n\nTest Configuration {i+1}:")
        print(f"  Duration: {config['duration']}s")
        print(f"  Time step: {config['time_step']}ms")
        print(f"  Algorithm: {config['algorithm']}")
        print(f"  Threads: {config['threads']}")
        
        # Test 1: Original implementation
        cleanup_gen_data()
        test1 = run_test(
            f"Original_{i+1}",
            f"python3 main_25x25.py {config['duration']} {config['time_step']} {config['algorithm']} {config['threads']}",
            f"Original implementation (Duration: {config['duration']}s)"
        )
        results.append(test1)
        
        # Test 2: Fast mode with cache
        cleanup_gen_data()
        test2 = run_test(
            f"FastMode_{i+1}",
            f"python3 main_25x25_fast.py {config['duration']} {config['time_step']} {config['algorithm']} {config['threads']}",
            f"Fast mode with cache (Duration: {config['duration']}s)"
        )
        results.append(test2)
        
        # Test 3: Fast mode without cache
        cleanup_gen_data()
        test3 = run_test(
            f"FastModeNoCache_{i+1}",
            f"python3 main_25x25_fast.py {config['duration']} {config['time_step']} {config['algorithm']} {config['threads']} --no-cache",
            f"Fast mode without cache (Duration: {config['duration']}s)"
        )
        results.append(test3)
        
        # Test 4: No fast mode but with cache
        cleanup_gen_data()
        test4 = run_test(
            f"CacheOnly_{i+1}",
            f"python3 main_25x25_fast.py {config['duration']} {config['time_step']} {config['algorithm']} {config['threads']} --no-fast-mode",
            f"Cache only, no fast mode (Duration: {config['duration']}s)"
        )
        results.append(test4)
    
    # Generate performance report
    print(f"\n\n{'='*80}")
    print("PERFORMANCE COMPARISON REPORT")
    print('='*80)
    
    # Group results by configuration
    for i, config in enumerate(test_configs):
        config_results = [r for r in results if r['name'].endswith(f"_{i+1}")]
        
        print(f"\nConfiguration {i+1} (Duration: {config['duration']}s):")
        print("-" * 50)
        
        for result in config_results:
            status_symbol = "✓" if result['status'] == "SUCCESS" else "✗"
            print(f"{status_symbol} {result['name']:20} {result['duration']:8.2f}s  {result['description']}")
        
        # Calculate speedup if original succeeded
        original = next((r for r in config_results if r['name'].startswith('Original')), None)
        if original and original['status'] == "SUCCESS":
            print(f"\nSpeedup compared to original:")
            for result in config_results:
                if result['name'] != original['name'] and result['status'] == "SUCCESS":
                    speedup = original['duration'] / result['duration']
                    improvement = (1 - result['duration'] / original['duration']) * 100
                    print(f"  {result['name']:20} {speedup:6.2f}x faster ({improvement:5.1f}% improvement)")
    
    # Save detailed results to JSON
    with open('performance_comparison_results.json', 'w') as f:
        json.dump({
            'test_configs': test_configs,
            'results': results,
            'summary': {
                'total_tests': len(results),
                'successful_tests': len([r for r in results if r['status'] == "SUCCESS"]),
                'failed_tests': len([r for r in results if r['status'] == "FAILED"]),
                'timeout_tests': len([r for r in results if r['status'] == "TIMEOUT"])
            }
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: performance_comparison_results.json")
    
    # Final summary
    successful = [r for r in results if r['status'] == "SUCCESS"]
    if successful:
        fastest = min(successful, key=lambda x: x['duration'])
        print(f"\nFastest successful configuration:")
        print(f"  {fastest['name']}: {fastest['duration']:.2f}s - {fastest['description']}")
    else:
        print(f"\nNo tests completed successfully!")


if __name__ == "__main__":
    # Check if we're in the right directory
    if not os.path.exists("main_25x25.py"):
        print("Error: main_25x25.py not found. Please run this script from the satellite_networks_state directory.")
        sys.exit(1)
    
    main()
