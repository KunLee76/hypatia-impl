#!/bin/bash

# ========================================
# Random P5 + P10 系列（依序執行）
# P5: 失效率 5% (6 個場景)
# P10: 失效率 10% (6 個場景)
# 總共 12 個場景
# ========================================

set -e

source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

TOTAL_START=$(date +%s)

echo ""
echo "========================================"
echo "開始執行 Random P5 + P10 系列"
echo "========================================"
echo "總場景數：12 個（P5: 6 個 + P10: 6 個）"
echo "預估時間：約 110 分鐘"
echo "========================================"
echo ""

# ========================================
# 第一部分：P5 系列
# ========================================

echo ""
echo "========================================"
echo "第一部分：執行 P5 系列（失效率 5%）"
echo "========================================"

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 清除快取
cd /home/kun/ssd2t/Leo/kun_hypatia
find satgenpy -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

mkdir -p ../../logs

# Chaos Monkey 設定
export ENABLE_CHAOS_MONKEY=true
export CHAOS_FAILURE_RATE=0.05  # P5 = 5%
export CHAOS_INTERVAL_SNAPSHOTS=1

# 模擬參數
DURATION=200
TIME_STEP=2000
ISL_TYPE="isls_plus_grid"
GS_TYPE="ground_stations_top_100_with_hsinchu"
ALGORITHM="algorithm_hierarchical_virtual_gid"
THREADS=4
GRID_DEG=27

P5_START=$(date +%s)

for K in 1 2 4 6 8 999; do
    export CHAOS_LOG_FILE="../../logs/chaos_p5_k${K}.log"
    
    echo ""
    echo "執行 Random P5 K${K}..."
    
    python main_starlink_550.py $DURATION $TIME_STEP $ISL_TYPE $GS_TYPE $ALGORITHM $THREADS $GRID_DEG $K
    
    echo "✅ Random P5 K${K} 完成"
done

P5_END=$(date +%s)
P5_DURATION=$((P5_END - P5_START))

echo ""
echo "========================================"
echo "P5 系列完成！耗時：$((P5_DURATION/60)) 分鐘"
echo "========================================"

# ========================================
# 第二部分：P10 系列
# ========================================

echo ""
echo "========================================"
echo "第二部分：執行 P10 系列（失效率 10%）"
echo "========================================"

# 更新失效率
export CHAOS_FAILURE_RATE=0.10  # P10 = 10%

P10_START=$(date +%s)

for K in 1 2 4 6 8 999; do
    export CHAOS_LOG_FILE="../../logs/chaos_p10_k${K}.log"
    
    echo ""
    echo "執行 Random P10 K${K}..."
    
    python main_starlink_550.py $DURATION $TIME_STEP $ISL_TYPE $GS_TYPE $ALGORITHM $THREADS $GRID_DEG $K
    
    echo "✅ Random P10 K${K} 完成"
done

P10_END=$(date +%s)
P10_DURATION=$((P10_END - P10_START))

echo ""
echo "========================================"
echo "P10 系列完成！耗時：$((P10_DURATION/60)) 分鐘"
echo "========================================"

# ========================================
# 總結
# ========================================

TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))
HOURS=$((TOTAL_DURATION / 3600))
MINUTES=$(((TOTAL_DURATION % 3600) / 60))

echo ""
echo "========================================"
echo "🎉 P5 + P10 系列全部完成！"
echo "========================================"
echo "P5 耗時：$((P5_DURATION/60)) 分鐘"
echo "P10 耗時：$((P10_DURATION/60)) 分鐘"
echo "總耗時：${HOURS} 小時 ${MINUTES} 分鐘"
echo "========================================"
echo ""

# 生成摘要
echo "Chaos Monkey 注入統計："
echo ""
echo "P5 系列："
for K in 1 2 4 6 8 999; do
    LOG="../../logs/chaos_p5_k${K}.log"
    if [ -f "$LOG" ]; then
        COUNT=$(grep -c '\[CHAOS_MONKEY\]' "$LOG")
        echo "  chaos_p5_k${K}.log: ${COUNT} 次注入"
    fi
done

echo ""
echo "P10 系列："
for K in 1 2 4 6 8 999; do
    LOG="../../logs/chaos_p10_k${K}.log"
    if [ -f "$LOG" ]; then
        COUNT=$(grep -c '\[CHAOS_MONKEY\]' "$LOG")
        echo "  chaos_p10_k${K}.log: ${COUNT} 次注入"
    fi
done

echo ""
echo "全部完成！可以開始分析數據了 🎊"
