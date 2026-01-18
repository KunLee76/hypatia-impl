#!/bin/bash
# ========================================
# K 參數實驗結果分析腳本
# ========================================
# 
# 自動分析所有 K 值實驗的結果
# 包括：RTT 性能、控制信令開銷
#
# ========================================

set -e

# 環境檢查
echo "檢查環境..."
if [[ "$CONDA_DEFAULT_ENV" != "" ]]; then
    echo "  ✓ Conda 環境：${CONDA_DEFAULT_ENV}"
else
    echo "  ⚠ 警告：未檢測到 conda 環境"
fi
echo ""

# 實驗參數
GRID_DEG=27
K_VALUES=(1 2 4 6 8 999)  # 包括 8 因為它已經完成
BASE_DIR="gen_data"
ANALYSIS_DIR="../satgenpy_analysis/data"

# 顏色輸出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  K 參數實驗結果分析${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 檢查哪些 K 值已完成
echo "檢查實驗完成狀態..."
echo ""
COMPLETED_K=()
for K in "${K_VALUES[@]}"; do
    DIR="${BASE_DIR}/starlink_550_isls_plus_grid_ground_stations_top_100_with_hsinchu_algorithm_hierarchical_virtual_gid_${GRID_DEG}deg_k${K}"
    if [ -d "${DIR}" ]; then
        COMPLETED_K+=($K)
        SIZE=$(du -sh "${DIR}" | cut -f1)
        echo -e "  ${GREEN}✓${NC} K=${K} (${SIZE})"
    else
        echo -e "  ${RED}✗${NC} K=${K} (目錄不存在)"
    fi
done
echo ""

if [ ${#COMPLETED_K[@]} -eq 0 ]; then
    echo -e "${RED}錯誤：沒有找到任何完成的實驗！${NC}"
    exit 1
fi

echo -e "${GREEN}找到 ${#COMPLETED_K[@]} 個完成的實驗${NC}"
echo ""

# 創建分析輸出目錄
mkdir -p "${ANALYSIS_DIR}"

# 對每個完成的 K 值進行分析
for K in "${COMPLETED_K[@]}"; do
    DIR="${BASE_DIR}/starlink_550_isls_plus_grid_ground_stations_top_100_with_hsinchu_algorithm_hierarchical_virtual_gid_${GRID_DEG}deg_k${K}"
    OUTPUT_DIR="${ANALYSIS_DIR}/k${K}_analysis"
    
    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "${BLUE}分析 K=${K}...${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"
    
    # RTT 分析
    echo "  > 執行 RTT 分析..."
    cd ../satgenpy
    python -m satgen.post_analysis.analyze_rtt \
        "${OUTPUT_DIR}" \
        "../paper/satellite_networks_state/${DIR}" \
        100 \
        20 \
        || echo -e "${YELLOW}  警告：RTT 分析失敗${NC}"
    cd ../paper/satellite_networks_state
    
    echo -e "${GREEN}  ✓ K=${K} 分析完成${NC}"
    echo ""
done

# 生成比較報告
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  生成比較報告${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

REPORT_FILE="k_parameter_comparison_report.txt"
echo "K 參數實驗比較報告" > ${REPORT_FILE}
echo "生成時間：$(date)" >> ${REPORT_FILE}
echo "========================================" >> ${REPORT_FILE}
echo "" >> ${REPORT_FILE}

for K in "${COMPLETED_K[@]}"; do
    OUTPUT_DIR="${ANALYSIS_DIR}/k${K}_analysis"
    echo "K = ${K}" >> ${REPORT_FILE}
    echo "----------------------------------------" >> ${REPORT_FILE}
    
    # 提取平均 RTT（如果存在）
    if [ -f "${OUTPUT_DIR}/data/ecdf.txt" ]; then
        # 這裡可以添加更詳細的統計提取
        echo "  RTT 數據：${OUTPUT_DIR}/data/ecdf.txt" >> ${REPORT_FILE}
    else
        echo "  RTT 數據：未找到" >> ${REPORT_FILE}
    fi
    
    # 提取控制信令（如果存在）
    SIGNALING_FILE="${BASE_DIR}/starlink_550_isls_plus_grid_ground_stations_top_100_with_hsinchu_algorithm_hierarchical_virtual_gid_${GRID_DEG}deg_k${K}/signaling_stats_timeline.csv"
    if [ -f "${SIGNALING_FILE}" ]; then
        LINES=$(wc -l < "${SIGNALING_FILE}")
        echo "  控制信令事件數：$((LINES - 1))" >> ${REPORT_FILE}
    else
        echo "  控制信令數據：未找到" >> ${REPORT_FILE}
    fi
    
    echo "" >> ${REPORT_FILE}
done

echo -e "${GREEN}✓ 比較報告已生成：${REPORT_FILE}${NC}"
echo ""
cat ${REPORT_FILE}
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  分析完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "結果位置："
for K in "${COMPLETED_K[@]}"; do
    echo "  K=${K}: ${ANALYSIS_DIR}/k${K}_analysis"
done
echo ""
echo "比較報告：${REPORT_FILE}"
echo ""
