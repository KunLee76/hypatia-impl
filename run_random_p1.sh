#!/bin/bash

# ========================================
# Random P1 系列（失效率 1%）
# 6 個場景：K(1,2,4,6,8,999)
# ========================================

set -e

source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 清除快取
cd /home/kun/ssd2t/Leo/kun_hypatia
find satgenpy -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

mkdir -p ../../logs

# Chaos Monkey 設定
export ENABLE_CHAOS_MONKEY=true
export CHAOS_FAILURE_RATE=0.01  # P1 = 1%
export CHAOS_INTERVAL_SNAPSHOTS=1

# 模擬參數
DURATION=200
TIME_STEP=2000
ISL_TYPE="isls_plus_grid"
GS_TYPE="ground_stations_top_100_with_hsinchu"
ALGORITHM="algorithm_hierarchical_virtual_gid"
THREADS=4
GRID_DEG=27

echo "========================================"
echo "執行 Random P1 系列（失效率 1%）"
echo "========================================"

START_TIME=$(date +%s)

for K in 1 2 4 6 8 999; do
    export CHAOS_LOG_FILE="../../logs/chaos_p1_k${K}.log"
    
    echo ""
    echo "執行 Random P1 K${K}..."
    
    python main_starlink_550.py $DURATION $TIME_STEP $ISL_TYPE $GS_TYPE $ALGORITHM $THREADS $GRID_DEG $K
    
    echo "✅ Random P1 K${K} 完成"
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo ""
echo "========================================"
echo "P1 系列完成！總耗時：$((DURATION/60)) 分鐘"
echo "========================================"
