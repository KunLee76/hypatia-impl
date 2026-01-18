#!/bin/bash
# ========================================
# K_BEST_GATEWAYS 參數實驗批次執行腳本
# ========================================
# 
# 測試配置：
#   - 星座：Starlink-550 (1584 satellites)
#   - 時長：20 秒
#   - Time step：100 毫秒
#   - Ground stations：top_100_with_hsinchu (101 stations)
#   - Grid degree：27 度
#   - K 值：1, 2, 4, 6, 999 (8 已完成，不重複測試)
#
# ========================================

set -e  # 遇到錯誤立即停止

# ========================================
# 環境檢查
# ========================================
echo "檢查 Python 環境..."
PYTHON_PATH=$(which python)
echo "  Python 路徑：${PYTHON_PATH}"

# 檢查是否在 conda 環境中
if [[ "$CONDA_DEFAULT_ENV" != "" ]]; then
    echo "  ✓ Conda 環境：${CONDA_DEFAULT_ENV}"
else
    echo "  ⚠ 警告：未檢測到 conda 環境！"
    echo "  建議先執行：conda activate kun_hypatia"
    read -p "是否繼續？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 測試 Python 能否導入必要的模組
echo "  測試模組導入..."
# 設置 PYTHONPATH 以包含 satgenpy
export PYTHONPATH="${PWD}/../../satgenpy:${PYTHONPATH}"

# 測試基礎模組
python -c "import networkx; import numpy" 2>/dev/null && echo "  ✓ 基礎模組可用 (networkx, numpy)" || {
    echo "  ✗ 錯誤：無法導入基礎模組！"
    echo "  請確保已安裝 networkx 和 numpy"
    exit 1
}

# 測試 satgen 模組（警告而非錯誤）
python -c "import sys; sys.path.insert(0, '../../satgenpy'); import satgen" 2>/dev/null && echo "  ✓ satgen 模組可用" || {
    echo "  ⚠ 警告：無法直接導入 satgen 模組（正常情況，運行時會自動處理）"
}
echo ""

# 實驗參數設定
DURATION_S=20
TIME_STEP_MS=100
ISL_TYPE="isls_plus_grid"
GS_TYPE="ground_stations_top_100_with_hsinchu"
ALGORITHM="algorithm_hierarchical_virtual_gid"
NUM_THREADS=10
GRID_DEG=27

# K 值測試組（不包括 8，因為已完成）
K_VALUES=(1 2 4 6 999)

# 顏色輸出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  K_BEST_GATEWAYS 參數實驗${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "實驗配置："
echo "  星座：Starlink-550"
echo "  時長：${DURATION_S} 秒"
echo "  Time step：${TIME_STEP_MS} 毫秒"
echo "  Ground stations：${GS_TYPE}"
echo "  Grid degree：${GRID_DEG}°"
echo "  K 值測試組：${K_VALUES[@]} (999=All)"
echo "  線程數：${NUM_THREADS}"
echo ""

# 記錄開始時間
START_TIME=$(date +%s)

# 執行每個 K 值的測試
for K in "${K_VALUES[@]}"; do
    echo -e "${GREEN}----------------------------------------${NC}"
    echo -e "${GREEN}正在執行 K=${K} 的測試...${NC}"
    echo -e "${GREEN}----------------------------------------${NC}"
    
    # 記錄此次測試的開始時間
    TEST_START=$(date +%s)
    
    # 執行測試
    python main_starlink_550.py \
        ${DURATION_S} \
        ${TIME_STEP_MS} \
        ${ISL_TYPE} \
        ${GS_TYPE} \
        ${ALGORITHM} \
        ${NUM_THREADS} \
        ${GRID_DEG} \
        ${K}
    
    # 計算此次測試耗時
    TEST_END=$(date +%s)
    TEST_DURATION=$((TEST_END - TEST_START))
    
    echo -e "${GREEN}✓ K=${K} 測試完成！耗時：${TEST_DURATION} 秒${NC}"
    echo ""
    
    # 顯示生成的目錄
    OUTPUT_DIR="gen_data/starlink_550_${ISL_TYPE}_${GS_TYPE}_${ALGORITHM}_${GRID_DEG}deg_k${K}"
    if [ -d "${OUTPUT_DIR}" ]; then
        echo -e "${BLUE}輸出目錄：${OUTPUT_DIR}${NC}"
        echo -e "${BLUE}目錄大小：$(du -sh ${OUTPUT_DIR} | cut -f1)${NC}"
    fi
    echo ""
done

# 計算總耗時
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
MINUTES=$((TOTAL_DURATION / 60))
SECONDS=$((TOTAL_DURATION % 60))

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  所有測試完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "完成的測試："
for K in "${K_VALUES[@]}"; do
    OUTPUT_DIR="gen_data/starlink_550_${ISL_TYPE}_${GS_TYPE}_${ALGORITHM}_${GRID_DEG}deg_k${K}"
    if [ -d "${OUTPUT_DIR}" ]; then
        echo -e "  ${GREEN}✓${NC} K=${K} → ${OUTPUT_DIR}"
    else
        echo -e "  ${RED}✗${NC} K=${K} → 目錄不存在！"
    fi
done
echo ""
echo "總耗時：${MINUTES} 分 ${SECONDS} 秒"
echo ""
echo -e "${YELLOW}提示：${NC}"
echo "  - 可以使用 analyze_rtt.py 分析 RTT 性能"
echo "  - 可以使用 hypatia_signaling_analyzer.py 分析控制信令開銷"
echo "  - 比較不同 K 值的結果以評估最佳參數"
echo ""
