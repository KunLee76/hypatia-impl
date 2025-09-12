#!/usr/bin/env python3
"""
Fast mode version of main_25x25.py with performance optimizations.
Supports:
1. Fast mode for hierarchical region algorithm
2. Cache reuse between time steps
3. Reduced logging for faster execution
"""

import sys
sys.path.append("../../satgenpy")
import satgen
import os
import shutil
import time
import argparse


# GENERATION CONSTANTS
BASE_NAME = "25x25"
NICE_NAME = "25x25-Legacy-Fast"

# 25x25
MAX_GSL_LENGTH_M = 1089686
MAX_ISL_LENGTH_M = 1000000000
NUM_ORBS = 25
NUM_SATS_PER_ORB = 25


def calculate_fast(duration_s, time_step_ms, dynamic_state_algorithm, num_threads, fast_mode=True, use_cache=True):
    """
    Enhanced version with performance optimizations.
    
    Args:
        duration_s: Simulation duration in seconds
        time_step_ms: Time step in milliseconds
        dynamic_state_algorithm: Algorithm name
        num_threads: Number of threads
        fast_mode: Enable fast mode optimizations
        use_cache: Enable caching between time steps
    """
    
    print(f"Starting calculation with:")
    print(f"  Duration: {duration_s}s")
    print(f"  Time step: {time_step_ms}ms")
    print(f"  Algorithm: {dynamic_state_algorithm}")
    print(f"  Threads: {num_threads}")
    print(f"  Fast mode: {fast_mode}")
    print(f"  Use cache: {use_cache}")
    
    start_time = time.time()

    # Add base name to setting
    name = BASE_NAME + "_" + dynamic_state_algorithm
    if fast_mode:
        name += "_fast"

    # Create output directories
    if not os.path.isdir("gen_data"):
        os.makedirs("gen_data")
    if not os.path.isdir("gen_data/" + name):
        os.makedirs("gen_data/" + name)

    # Ground stations
    print("Generating ground stations...")
    shutil.copy("input_data/legacy/ground_stations_first_100.txt", "gen_data/" + name + "/ground_stations.txt")

    # TLEs
    print("Generating TLEs...")
    shutil.copy("input_data/legacy/starlink_tles_25x25.txt", "gen_data/" + name + "/tles.txt")

    # ISLs
    print("Generating ISLs...")
    satgen.generate_plus_grid_isls(
        "gen_data/" + name + "/isls.txt",
        NUM_ORBS,
        NUM_SATS_PER_ORB,
        isl_shift=1,
        idx_offset=0
    )

    # Description
    print("Generating description...")
    satgen.generate_description(
        "gen_data/" + name + "/description.txt",
        MAX_GSL_LENGTH_M,
        MAX_ISL_LENGTH_M
    )

    # GSL interfaces
    ground_stations = satgen.read_ground_stations_extended("gen_data/" + name + "/ground_stations.txt")
    if dynamic_state_algorithm == "algorithm_free_one_only_over_isls" \
            or dynamic_state_algorithm == "algorithm_free_one_only_gs_relays" \
            or dynamic_state_algorithm == "algorithm_hierarchical_region":
        gsl_interfaces_per_satellite = 1
    elif dynamic_state_algorithm == "algorithm_paired_many_only_over_isls":
        gsl_interfaces_per_satellite = len(ground_stations)
    else:
        raise ValueError("Unknown dynamic state algorithm")

    print("Generating GSL interfaces info..")
    satgen.generate_simple_gsl_interfaces_info(
        "gen_data/" + name + "/gsl_interfaces_info.txt",
        NUM_ORBS * NUM_SATS_PER_ORB,
        len(ground_stations),
        gsl_interfaces_per_satellite,
        1,
        1,
        1
    )

    # Setup time
    setup_time = time.time() - start_time
    print(f"Setup completed in {setup_time:.2f} seconds")

    # Forwarding state - with optimizations
    print("Generating forwarding state with optimizations...")
    forwarding_start = time.time()
    
    # Set environment variables for optimizations
    if fast_mode:
        os.environ['SATGEN_FAST_MODE'] = '1'
    if use_cache:
        os.environ['SATGEN_USE_CACHE'] = '1'
    
    try:
        satgen.help_dynamic_state(
            "gen_data",
            num_threads,
            name,
            time_step_ms,
            duration_s,
            MAX_GSL_LENGTH_M,
            MAX_ISL_LENGTH_M,
            dynamic_state_algorithm,
            True  # Enable verbose logs to debug region grouping
        )
    finally:
        # Clean up environment variables
        if 'SATGEN_FAST_MODE' in os.environ:
            del os.environ['SATGEN_FAST_MODE']
        if 'SATGEN_USE_CACHE' in os.environ:
            del os.environ['SATGEN_USE_CACHE']
    
    forwarding_time = time.time() - forwarding_start
    total_time = time.time() - start_time
    
    print(f"\nPerformance Summary:")
    print(f"  Setup time: {setup_time:.2f}s")
    print(f"  Forwarding state time: {forwarding_time:.2f}s")
    print(f"  Total time: {total_time:.2f}s")
    
    # Calculate time steps and performance metrics
    num_time_steps = duration_s * 1000 // time_step_ms
    time_per_step = forwarding_time / num_time_steps if num_time_steps > 0 else 0
    
    print(f"  Time steps: {num_time_steps}")
    print(f"  Time per step: {time_per_step:.3f}s")
    
    if fast_mode:
        print(f"  Optimizations: Fast mode enabled")
    if use_cache:
        print(f"  Optimizations: Cache enabled")


def main():
    parser = argparse.ArgumentParser(description='Fast mode satellite network state generator')
    parser.add_argument('duration', type=int, help='Duration in seconds')
    parser.add_argument('time_step', type=int, help='Time step in milliseconds')
    parser.add_argument('algorithm', type=str, help='Dynamic state algorithm')
    parser.add_argument('num_threads', type=int, help='Number of threads')
    parser.add_argument('--no-fast-mode', action='store_true', help='Disable fast mode')
    parser.add_argument('--no-cache', action='store_true', help='Disable caching')
    
    args = parser.parse_args()
    
    # Validate algorithm
    valid_algorithms = [
        "algorithm_free_one_only_over_isls",
        "algorithm_free_one_only_gs_relays", 
        "algorithm_paired_many_only_over_isls",
        "algorithm_hierarchical_region"
    ]
    
    if args.algorithm not in valid_algorithms:
        print(f"Error: Invalid algorithm '{args.algorithm}'")
        print(f"Valid algorithms: {', '.join(valid_algorithms)}")
        exit(1)
    
    calculate_fast(
        args.duration,
        args.time_step,
        args.algorithm,
        args.num_threads,
        fast_mode=not args.no_fast_mode,
        use_cache=not args.no_cache
    )


if __name__ == "__main__":
    main()
