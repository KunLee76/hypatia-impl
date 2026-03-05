#!/bin/bash

set -e

# 停用 venv 並啟用 conda
deactivate 2>/dev/null || true
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

echo "================================"
echo "執行 LoHi P5 & P10"
echo "================================"

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

echo ""
echo "[1/2] LoHi P5 (5% 失效率)..."
ENABLE_CHAOS_MONKEY=true \
CHAOS_FAILURE_RATE=5 \
python main_starlink_550.py 200 2000 isls_random_p5 \
    ground_stations_top_100_with_hsinchu algorithm_lohi 10

echo ""
echo "[2/2] LoHi P10 (10% 失效率)..."
ENABLE_CHAOS_MONKEY=true \
CHAOS_FAILURE_RATE=10 \
python main_starlink_550.py 200 2000 isls_random_p10 \
    ground_stations_top_100_with_hsinchu algorithm_lohi 10

echo ""
echo "模擬完成，開始合併統計文件..."

cd /home/kun/ssd2t/Leo/kun_hypatia

python3 merge_random_stats_simple.py \
    "paper/satellite_networks_state/analytic_result/temp_lohi_random_p5" \
    "paper/satellite_networks_state/analytic_result/lohi_random_p5_signaling_stats.json"

python3 merge_random_stats_simple.py \
    "paper/satellite_networks_state/analytic_result/temp_lohi_random_p10" \
    "paper/satellite_networks_state/analytic_result/lohi_random_p10_signaling_stats.json"

echo ""
echo "✓ LoHi P5 & P10 完成"
