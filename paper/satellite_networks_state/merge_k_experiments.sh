#!/bin/bash
# ========================================
# 整合 K 參數實驗的控制信令統計
# ========================================
# 
# 步驟：
# 1. 識別每個 K 值對應的 PID 組
# 2. 使用 merge_signaling_stats.py 合併
# 3. 生成統一命名的 JSON 檔案
#
# ========================================

set -e

cd /home/kun/ssd2t/Leo/kun_hypatia

# 顏色輸出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  整合 K 參數控制信令統計${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

TEMP_DIR="paper/satellite_networks_state/analytic_result/temp_grhr"
OUTPUT_DIR="paper/satellite_networks_state/analytic_result"

# 檢查 temp_grhr 目錄
if [ ! -d "${TEMP_DIR}" ]; then
    echo -e "${RED}錯誤：找不到 ${TEMP_DIR}${NC}"
    exit 1
fi

# 獲取所有 PID 組，按時間排序（最新的 5 組對應 K=1,2,4,6,999）
echo "正在識別 PID 組..."
PIDS=($(ls ${TEMP_DIR}/grhr_stats_*.json | sed 's/.*_pid\([0-9]*\)_.*/\1/' | sort -u | tail -5))

echo "找到最新的 5 組 PID（對應 K=1,2,4,6,999）："
for i in "${!PIDS[@]}"; do
    COUNT=$(ls ${TEMP_DIR}/grhr_stats_pid${PIDS[$i]}_*.json 2>/dev/null | wc -l)
    echo "  組 $((i+1)): PID=${PIDS[$i]} (${COUNT} 個檔案)"
done
echo ""

# K 值映射（假設按順序對應）
K_VALUES=(1 2 4 6 999)

# 確認映射
echo -e "${YELLOW}請確認以下 PID 到 K 值的映射：${NC}"
for i in "${!PIDS[@]}"; do
    echo "  PID ${PIDS[$i]} → K=${K_VALUES[$i]}"
done
echo ""
read -p "是否正確？(y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消。請手動調整 K_VALUES 陣列。"
    exit 1
fi

# 對每個 K 值進行合併
for i in "${!PIDS[@]}"; do
    PID=${PIDS[$i]}
    K=${K_VALUES[$i]}
    
    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "${BLUE}處理 K=${K} (PID=${PID})...${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"
    
    # 檢查該 PID 的檔案數量
    FILES=(${TEMP_DIR}/grhr_stats_pid${PID}_*.json)
    FILE_COUNT=${#FILES[@]}
    
    echo "  找到 ${FILE_COUNT} 個統計檔案"
    
    # 輸出檔案名稱
    OUTPUT_JSON="${OUTPUT_DIR}/hierarchical_gid_27deg_k${K}_signaling_stats.json"
    
    # 執行合併
    echo "  正在合併..."
    python merge_signaling_stats.py \
        --input-pattern "${TEMP_DIR}/grhr_stats_pid${PID}_*.json" \
        --output "${OUTPUT_JSON}" \
        --algorithm "GRHR_27deg_K${K}" \
        || {
            echo -e "${RED}  ✗ 合併失敗${NC}"
            continue
        }
    
    if [ -f "${OUTPUT_JSON}" ]; then
        SIZE=$(du -h "${OUTPUT_JSON}" | cut -f1)
        echo -e "${GREEN}  ✓ 已生成：${OUTPUT_JSON} (${SIZE})${NC}"
    fi
    echo ""
done

# 同時處理 K=8（如果有舊的統計檔案）
echo -e "${BLUE}----------------------------------------${NC}"
echo -e "${BLUE}檢查 K=8 的統計檔案...${NC}"
echo -e "${BLUE}----------------------------------------${NC}"

K8_JSON="${OUTPUT_DIR}/hierarchical_gid_27deg_signaling_stats.json"
K8_OUTPUT="${OUTPUT_DIR}/hierarchical_gid_27deg_k8_signaling_stats.json"

if [ -f "${K8_JSON}" ] && [ ! -f "${K8_OUTPUT}" ]; then
    echo "  找到舊的 K=8 統計檔案"
    cp "${K8_JSON}" "${K8_OUTPUT}"
    echo -e "${GREEN}  ✓ 已複製為：${K8_OUTPUT}${NC}"
elif [ -f "${K8_OUTPUT}" ]; then
    echo -e "${GREEN}  ✓ K=8 統計檔案已存在${NC}"
else
    echo -e "${YELLOW}  ⚠ 未找到 K=8 的統計檔案${NC}"
fi
echo ""

# 列出所有生成的檔案
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  完成！生成的統計檔案：${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
ls -lh ${OUTPUT_DIR}/hierarchical_gid_27deg_k*_signaling_stats.json 2>/dev/null || echo "  (無檔案)"
echo ""

echo -e "${YELLOW}下一步：${NC}"
echo "  使用 hypatia_multi_algorithm_analyzer.py 比較不同 K 值的性能"
echo ""
