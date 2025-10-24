# Centralized JSON Output Update

## Overview
All three routing algorithms have been updated to output their signaling statistics JSON files to a centralized `analytic_result` directory instead of scattering them in the root `paper/satellite_networks_state` directory.

## Changes Made

### 1. Algorithm Files Modified

#### algorithm_hierarchical_virtual_pid.py
- **File**: `satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_pid.py`
- **Locations Modified**: 2
- **Changes**:
  - Changed `stats_output_dir = "."` to `stats_output_dir = "analytic_result"`
  - Added `os.makedirs(stats_output_dir, exist_ok=True)` to ensure directory exists
- **Output File**: `analytic_result/hierarchical_gid_{grid_deg}deg_signaling_stats.json`

#### algorithm_hierarchical_virtual_pid_dijkstra.py
- **File**: `satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_pid_dijkstra.py`
- **Locations Modified**: 2
- **Changes**:
  - Changed `stats_output_dir = "."` to `stats_output_dir = "analytic_result"`
  - Added `os.makedirs(stats_output_dir, exist_ok=True)` to ensure directory exists
- **Output File**: `analytic_result/hierarchical_gid_dijkstra_{grid_deg}deg_signaling_stats.json`

#### algorithm_free_one_only_over_isls_with_stats.py
- **File**: `satgenpy/satgen/dynamic_state/algorithm_free_one_only_over_isls_with_stats.py`
- **Locations Modified**: 1
- **Changes**:
  - Changed `stats_output_dir = "."` to `stats_output_dir = "analytic_result"`
  - Added `os.makedirs(stats_output_dir, exist_ok=True)` to ensure directory exists
- **Output File**: `analytic_result/baseline_floyd_warshall_signaling_stats.json`

### 2. Analyzer Scripts Updated

#### hypatia_signaling_analyzer.py
- **File**: `hypatia_signaling_analyzer.py`
- **Change**: Updated default `stats_dir` parameter
  - From: `stats_dir="paper/satellite_networks_state"`
  - To: `stats_dir="paper/satellite_networks_state/analytic_result"`
- **Function**: Automatically reads from the centralized directory
- **Features**: Supports auto-discovery of multiple grid configurations (10°, 15°, 20°, 25°)

#### hypatia_multi_algorithm_analyzer.py
- **File**: `hypatia_multi_algorithm_analyzer.py`
- **Change**: Updated default `stats_dir` parameter
  - From: `stats_dir="paper/satellite_networks_state"`
  - To: `stats_dir="paper/satellite_networks_state/analytic_result"`
- **Function**: Automatically discovers and compares all algorithm variants
- **Features**: Gradient color scheme, dynamic sizing, automatic sorting by category and grid_deg

## Directory Structure

```
paper/satellite_networks_state/
├── analytic_result/                                    # ← New centralized directory
│   ├── baseline_floyd_warshall_signaling_stats.json
│   ├── hierarchical_gid_10deg_signaling_stats.json
│   ├── hierarchical_gid_15deg_signaling_stats.json
│   ├── hierarchical_gid_20deg_signaling_stats.json
│   ├── hierarchical_gid_25deg_signaling_stats.json
│   ├── hierarchical_gid_dijkstra_10deg_signaling_stats.json
│   ├── hierarchical_gid_dijkstra_15deg_signaling_stats.json
│   ├── hierarchical_gid_dijkstra_20deg_signaling_stats.json
│   └── hierarchical_gid_dijkstra_25deg_signaling_stats.json
├── signaling_analysis_results/                         # Analyzer output
│   └── (comparison charts and reports)
└── multi_algorithm_analysis/                           # Multi-algo analyzer output
    └── (multi-algorithm comparison charts)
```

## Benefits

1. **Clean Organization**: All JSON outputs in one place, easier to manage
2. **Easy Discovery**: Analyzers automatically find all files in centralized location
3. **Reduced Clutter**: Root directory no longer filled with multiple JSON files
4. **Scalability**: Easy to add more grid configurations or algorithm variants
5. **Automated Creation**: `os.makedirs()` ensures directory exists automatically

## Usage

### Running Algorithms
The algorithms will automatically create the `analytic_result` directory and save JSON files there:

```bash
cd paper/satellite_networks_state
python ../../satgenpy/satgen/post_analysis/main_print_routes_and_rtt.py \
    kuiper_630_isls_plus_grid_ground_stations_top_100_algorithm_free_one_only_over_isls_with_stats \
    200 1584 isls_plus_grid ground_stations_top_100 algorithm_free_one_only_over_isls_with_stats
```

### Running Analyzers
Analyzers will automatically read from the centralized directory:

```bash
# Single comparison analyzer
python ../../hypatia_signaling_analyzer.py

# Multi-algorithm analyzer
python ../../hypatia_multi_algorithm_analyzer.py
```

## JSON File Format

All algorithms now output unified JSON format:

```json
{
    "algorithm": "algorithm_hierarchical_virtual_pid_dijkstra",
    "algorithm_display_name": "Hierarchical GID Dijkstra (15°)",
    "grid_deg": 15,
    "timestamp": "2024-01-15T10:30:00.123456",
    "summary": {
        "total_events": 1234,
        "total_bytes": 567890,
        "events_by_type": {...}
    },
    "timeline": [
        {
            "snapshot": 0,
            "time_ms": 0,
            "event": "initialization",
            "count": 100,
            "bytes": 5000,
            "detail": "..."
        }
    ]
}
```

## Testing

To verify the complete workflow:

1. Run all three algorithms with different grid sizes (10°, 15°, 20°, 25°)
2. Check that JSON files are in `analytic_result/` directory
3. Run both analyzers to ensure they correctly discover and process files
4. Verify output charts and reports are generated correctly

## Notes

- The `analytic_result` directory is created automatically when algorithms run
- Old JSON files in the root directory can be safely removed after migration
- Analyzers default to the new directory but can still accept custom paths
- All three algorithms maintain backward compatibility with existing JSON structure
