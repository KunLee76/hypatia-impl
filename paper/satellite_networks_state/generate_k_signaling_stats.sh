#!/bin/bash
# ========================================
# 為 K 參數實驗生成控制信令統計
# ========================================
# 
# 使用 hypatia_signaling_analyzer.py 分析所有 K 值的控制信令
#
# ========================================

set -e

# 顏色輸出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 參數設定
GRID_DEG=27
K_VALUES=(1 2 4 6 8 999)
BASE_DIR="gen_data"
ALGORITHM="algorithm_hierarchical_virtual_gid"
OUTPUT_DIR="analytic_result/k_parameter_experiments"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  生成 K 參數控制信令統計${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 創建輸出目錄
mkdir -p "${OUTPUT_DIR}"

# 檢查 hypatia_signaling_analyzer.py 是否存在
if [ ! -f "hypatia_signaling_analyzer.py" ]; then
    echo -e "${RED}錯誤：找不到 hypatia_signaling_analyzer.py${NC}"
    exit 1
fi

echo "K 值測試組：${K_VALUES[@]}"
echo "輸出目錄：${OUTPUT_DIR}"
echo ""

# 對每個 K 值進行分析
for K in "${K_VALUES[@]}"; do
    DIR="${BASE_DIR}/starlink_550_isls_plus_grid_ground_stations_top_100_with_hsinchu_${ALGORITHM}_${GRID_DEG}deg_k${K}"
    
    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "${BLUE}處理 K=${K}...${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"
    
    if [ ! -d "${DIR}" ]; then
        echo -e "${RED}  ✗ 目錄不存在：${DIR}${NC}"
        echo ""
        continue
    fi
    
    # 檢查 dynamic_state 目錄
    DYNAMIC_DIR="${DIR}/dynamic_state_100ms_for_20s"
    if [ ! -d "${DYNAMIC_DIR}" ]; then
        echo -e "${YELLOW}  ⚠ 找不到 dynamic_state 目錄${NC}"
        echo ""
        continue
    fi
    
    echo "  源目錄：${DIR}"
    echo "  正在分析控制信令統計..."
    
    # 使用 Python 腳本分析（假設它會自動處理 temp_grhr 檔案）
    # 這裡需要根據實際的 analyzer 使用方式調整
    OUTPUT_JSON="${OUTPUT_DIR}/hierarchical_gid_27deg_k${K}_signaling_stats.json"
    
    # 如果 temp_grhr 目錄存在，先合併統計
    if [ -d "${DIR}/temp_grhr" ] || [ -d "temp_grhr" ]; then
        echo "  > 檢測到多進程統計檔案，執行合併..."
        python merge_signaling_stats.py \
            --input-pattern "temp_grhr/grhr_stats_*.json" \
            --output "${OUTPUT_JSON}" \
            --algorithm "GRHR_K${K}" \
            || echo -e "${YELLOW}    警告：合併統計失敗${NC}"
    fi
    
    echo -e "${GREEN}  ✓ K=${K} 處理完成${NC}"
    if [ -f "${OUTPUT_JSON}" ]; then
        SIZE=$(du -h "${OUTPUT_JSON}" | cut -f1)
        echo -e "${GREEN}    輸出：${OUTPUT_JSON} (${SIZE})${NC}"
    fi
    echo ""
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  統計生成完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "輸出檔案："
ls -lh "${OUTPUT_DIR}/"*.json 2>/dev/null || echo "  (無 JSON 檔案生成)"
echo ""
echo -e "${YELLOW}提示：${NC}"
echo "  使用 hypatia_multi_algorithm_analyzer.py 比較不同 K 值的性能"
echo ""
