#!/bin/bash

# ========================================
# Failure 場景批次執行腳本
# Baseline + L1-L4 × K(1,2,4,6,8,999)
# 總共 30 個場景
# ========================================

set -e

source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

TOTAL_START=$(date +%s)

echo ""
echo "========================================"
echo "開始執行 Failure 場景"
echo "========================================"
echo "總場景數：30 個"
echo "  - Baseline: 6 個 (K=1,2,4,6,8,999)"
echo "  - L1: 6 個 (固定失效 1 條 ISL)"
echo "  - L2: 6 個 (固定失效 2 條 ISL)"
echo "  - L3: 6 個 (固定失效 3 條 ISL)"
echo "  - L4: 6 個 (固定失效 4 條 ISL)"
echo "預估時間：約 160 分鐘 (2.7 小時)"
echo "========================================"
echo ""

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 清除快取
cd /home/kun/ssd2t/Leo/kun_hypatia
find satgenpy -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

mkdir -p ../../logs

# 禁用 Chaos Monkey（使用固定失效）
export ENABLE_CHAOS_MONKEY=false

# 模擬參數
DURATION=200
TIME_STEP=2000
GS_TYPE="ground_stations_top_100_with_hsinchu"
ALGORITHM="algorithm_hierarchical_virtual_gid"
THREADS=4
GRID_DEG=27

# 場景列表
SCENARIOS=("baseline" "failure_l1" "failure_l2" "failure_l3" "failure_l4")
K_VALUES=(1 2 4 6 8 999)

# 遍歷每個場景
for SCENARIO in "${SCENARIOS[@]}"; do
    SCENARIO_START=$(date +%s)
    SCENARIO_UPPER=$(echo "$SCENARIO" | tr '[:lower:]' '[:upper:]')
    
    echo ""
    echo "========================================"
    echo "開始執行 ${SCENARIO_UPPER} 系列"
    echo "========================================"
    
    # 設定 ISL 類型
    if [ "$SCENARIO" = "baseline" ]; then
        ISL_TYPE="isls_plus_grid"
    else
        ISL_TYPE="isls_${SCENARIO}"
    fi
    
    # 遍歷每個 K 值
    for K in "${K_VALUES[@]}"; do
        echo ""
        echo "執行 ${SCENARIO_UPPER} K${K}..."
        
        python main_starlink_550.py $DURATION $TIME_STEP $ISL_TYPE $GS_TYPE $ALGORITHM $THREADS $GRID_DEG $K
        
        echo "✅ ${SCENARIO_UPPER} K${K} 完成"
    done
    
    SCENARIO_END=$(date +%s)
    SCENARIO_DURATION=$((SCENARIO_END - SCENARIO_START))
    
    echo ""
    echo "========================================"
    echo "${SCENARIO_UPPER} 系列完成！耗時：$((SCENARIO_DURATION/60)) 分鐘"
    echo "========================================"
done

# ========================================
# 總結
# ========================================

TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))
HOURS=$((TOTAL_DURATION / 3600))
MINUTES=$(((TOTAL_DURATION % 3600) / 60))

echo ""
echo "========================================"
echo "🎉 Failure 場景全部完成！"
echo "========================================"
echo "總耗時：${HOURS} 小時 ${MINUTES} 分鐘"
echo ""
echo "各場景耗時："
echo "  - Baseline: 已完成"
echo "  - L1: 已完成"
echo "  - L2: 已完成"
echo "  - L3: 已完成"
echo "  - L4: 已完成"
echo "========================================"
echo ""

# 生成數據目錄統計
echo "生成的數據目錄："
echo ""
ls -d ../../paper/satellite_networks_state/gen_data/starlink_550_isls_*_algorithm_hierarchical_virtual_gid_${GRID_DEG}deg_k*/dynamic_state_2000ms_for_200s 2>/dev/null | while read dir; do
    scenario_name=$(echo "$dir" | grep -oP 'isls_[^_]+(?:_[^_]+)*' | head -1)
    k_value=$(echo "$dir" | grep -oP 'k\d+' | tail -1)
    echo "  ✅ ${scenario_name} ${k_value}"
done

echo ""
echo "全部完成！可以開始分析數據了 🎊"
echo ""
echo "下一步："
echo "  1. 驗證所有 30 個數據目錄已生成"
echo "  2. 更新分析腳本讀取 200s 數據"
echo "  3. 重新生成比較分析圖表"
