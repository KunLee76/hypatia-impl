#!/bin/bash

# ===================================================================
# Baseline & LoHi Re-run Script (After Topology Statistics Fix)
# ===================================================================
# Purpose: Re-run Baseline and LoHi with fixed topology statistics
#          to properly capture Chaos Monkey's impact
# Date: 2026-02-06
# Estimated Time: ~2 hours total (1 hour each algorithm)
# ===================================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="/home/kun/ssd2t/Leo/kun_hypatia"
OUTPUT_DIR="$PROJECT_ROOT/paper/satellite_networks_state/analytic_result"
NUM_THREADS=4
DURATION_S=200
TIME_STEP_MS=2000

echo "========================================================================"
echo "  Baseline & LoHi Re-run with Fixed Topology Statistics"
echo "========================================================================"
echo ""
echo "Configuration:"
echo "  - Project Root: $PROJECT_ROOT"
echo "  - Output Dir: $OUTPUT_DIR"
echo "  - Duration: ${DURATION_S}s"
echo "  - Time Step: ${TIME_STEP_MS}ms"
echo "  - Threads: $NUM_THREADS"
echo ""

# Activate conda environment
echo -e "${BLUE}[1/7]${NC} Activating conda environment..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

cd "$PROJECT_ROOT/paper/satellite_networks_state"

# Backup existing files
echo -e "${BLUE}[2/7]${NC} Backing up existing result files..."
BACKUP_DIR="$OUTPUT_DIR/backup_before_topology_fix_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

for file in baseline_dynamic_p*.json lohi_dynamic_p*.json chaos_monkey_baseline_p*.log chaos_monkey_lohi_p*.log; do
    if [ -f "$OUTPUT_DIR/$file" ]; then
        cp "$OUTPUT_DIR/$file" "$BACKUP_DIR/" || true
    fi
done

echo "  ✓ Backup created: $BACKUP_DIR"
echo ""

# ===================================================================
# BASELINE Algorithm
# ===================================================================

echo "========================================================================"
echo "  BASELINE Algorithm Re-run"
echo "========================================================================"
echo ""

SCENARIOS=("p1" "p5" "p10")
FAILURE_RATES=("0.01" "0.05" "0.10")

for i in "${!SCENARIOS[@]}"; do
    SCENARIO="${SCENARIOS[$i]}"
    RATE="${FAILURE_RATES[$i]}"
    
    echo -e "${YELLOW}[Baseline ${SCENARIO^^}]${NC} Failure Rate: $RATE"
    
    START_TIME=$(date +%s)
    
    export ENABLE_VERBOSE_LOGS=false
    export ENABLE_CHAOS_MONKEY=true
    export CHAOS_FAILURE_RATE=$RATE
    export CHAOS_INTERVAL_SNAPSHOTS=20
    export CHAOS_LOG_FILE="$OUTPUT_DIR/chaos_monkey_baseline_${SCENARIO}.log"
    export SIGNALING_STATS_OUTPUT_FILE="$OUTPUT_DIR/baseline_dynamic_${SCENARIO}_signaling_stats.json"
    
    python main_starlink_550.py \
        $DURATION_S \
        $TIME_STEP_MS \
        isls_plus_grid \
        ground_stations_top_100_with_hsinchu \
        algorithm_free_one_only_over_isls_with_stats \
        $NUM_THREADS
    
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    # Verify output file
    OUTPUT_FILE="$OUTPUT_DIR/baseline_dynamic_${SCENARIO}_signaling_stats.json"
    if [ -f "$OUTPUT_FILE" ]; then
        SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')
        echo -e "  ${GREEN}✓${NC} 完成 (耗時: ${ELAPSED}秒, 大小: $SIZE)"
    else
        echo -e "  ${RED}✗${NC} 警告：輸出文件未生成"
    fi
    
    echo ""
done

echo -e "${GREEN}✓ Baseline 全部完成${NC}"
echo ""

# ===================================================================
# LoHi Algorithm
# ===================================================================

echo "========================================================================"
echo "  LoHi Algorithm Re-run"
echo "========================================================================"
echo ""

for i in "${!SCENARIOS[@]}"; do
    SCENARIO="${SCENARIOS[$i]}"
    RATE="${FAILURE_RATES[$i]}"
    
    echo -e "${YELLOW}[LoHi ${SCENARIO^^}]${NC} Failure Rate: $RATE"
    
    START_TIME=$(date +%s)
    
    export ENABLE_VERBOSE_LOGS=false
    export ENABLE_CHAOS_MONKEY=true
    export CHAOS_FAILURE_RATE=$RATE
    export CHAOS_INTERVAL_SNAPSHOTS=20
    export CHAOS_LOG_FILE="$OUTPUT_DIR/chaos_monkey_lohi_${SCENARIO}.log"
    export SIGNALING_STATS_OUTPUT_FILE="$OUTPUT_DIR/lohi_dynamic_${SCENARIO}_signaling_stats.json"
    
    python main_starlink_550.py \
        $DURATION_S \
        $TIME_STEP_MS \
        isls_plus_grid \
        ground_stations_top_100_with_hsinchu \
        algorithm_lohi \
        $NUM_THREADS
    
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    # Verify output file
    OUTPUT_FILE="$OUTPUT_DIR/lohi_dynamic_${SCENARIO}_signaling_stats.json"
    if [ -f "$OUTPUT_FILE" ]; then
        SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')
        echo -e "  ${GREEN}✓${NC} 完成 (耗時: ${ELAPSED}秒, 大小: $SIZE)"
    else
        echo -e "  ${RED}✗${NC} 警告：輸出文件未生成"
    fi
    
    echo ""
done

echo -e "${GREEN}✓ LoHi 全部完成${NC}"
echo ""

# ===================================================================
# Verification
# ===================================================================

echo "========================================================================"
echo "  Verification"
echo "========================================================================"
echo ""

echo "Generated files:"
ls -lh "$OUTPUT_DIR"/*.json | grep -E "(baseline|lohi)_dynamic" | tail -6

echo ""
echo "Chaos Monkey logs:"
ls -lh "$OUTPUT_DIR"/chaos_monkey_*.log | tail -6

echo ""
echo -e "${GREEN}✓✓✓ 所有任務完成！${NC}"
echo ""
echo "Next steps:"
echo "  1. Verify topology statistics show variation across P1/P5/P10"
echo "  2. Run: python3 analyze_algorithm_comparison_dynamic.py"
echo "  3. Check if control traffic now correlates with failure rate"
echo ""
