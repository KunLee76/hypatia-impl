#!/bin/bash
# ========================================
# 分別合併每個 K 值的控制信令統計
# ========================================

set -e

cd /home/kun/ssd2t/Leo/kun_hypatia

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  分別合併 K 參數控制信令統計${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

TEMP_DIR="paper/satellite_networks_state/analytic_result/temp_grhr"
OUTPUT_DIR="paper/satellite_networks_state/analytic_result"

# 獲取最新的 5 組 PID（對應 K=1,2,4,6,999）
echo "正在識別 PID 組..."
cd "${TEMP_DIR}"
PIDS=($(ls grhr_stats_*.json | sed 's/.*_pid\([0-9]*\)_.*/\1/' | sort -u | tail -5))
cd - > /dev/null

echo "找到最新的 5 組 PID："
for i in "${!PIDS[@]}"; do
    COUNT=$(ls ${TEMP_DIR}/grhr_stats_pid${PIDS[$i]}_*.json 2>/dev/null | wc -l)
    echo "  組 $((i+1)): PID=${PIDS[$i]} (${COUNT} 個檔案)"
done
echo ""

# K 值映射
K_VALUES=(1 2 4 6 999)

echo -e "${YELLOW}PID 到 K 值的映射：${NC}"
for i in "${!PIDS[@]}"; do
    echo "  PID ${PIDS[$i]} → K=${K_VALUES[$i]}"
done
echo ""
read -p "是否正確？(y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 1
fi

# 為每個 K 值創建臨時目錄並合併
for i in "${!PIDS[@]}"; do
    PID=${PIDS[$i]}
    K=${K_VALUES[$i]}
    
    echo -e "${BLUE}----------------------------------------${NC}"
    echo -e "${BLUE}處理 K=${K} (PID=${PID})...${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"
    
    # 創建臨時目錄
    TEMP_K_DIR="/tmp/grhr_k${K}_$$"
    mkdir -p "${TEMP_K_DIR}"
    
    # 複製該 PID 的檔案到臨時目錄
    cp ${TEMP_DIR}/grhr_stats_pid${PID}_*.json "${TEMP_K_DIR}/"
    FILE_COUNT=$(ls ${TEMP_K_DIR}/*.json | wc -l)
    echo "  已複製 ${FILE_COUNT} 個檔案到臨時目錄"
    
    # 執行 merge_signaling_stats.py（它會處理目錄下所有檔案）
    echo "  正在合併..."
    
    # 創建臨時輸出目錄
    TEMP_OUTPUT_DIR="/tmp/grhr_output_k${K}_$$"
    mkdir -p "${TEMP_OUTPUT_DIR}/temp_grhr"
    
    # 移動檔案到預期的結構
    mv ${TEMP_K_DIR}/* "${TEMP_OUTPUT_DIR}/temp_grhr/"
    
    # 執行合併
    python merge_signaling_stats.py -d "${TEMP_OUTPUT_DIR}" -v || {
        echo -e "${RED}  ✗ 合併失敗${NC}"
        rm -rf "${TEMP_K_DIR}" "${TEMP_OUTPUT_DIR}"
        continue
    }
    
    # 移動輸出檔案
    OUTPUT_JSON="${OUTPUT_DIR}/hierarchical_gid_27deg_k${K}_signaling_stats.json"
    if [ -f "${TEMP_OUTPUT_DIR}/hierarchical_gid_27deg_signaling_stats.json" ]; then
        mv "${TEMP_OUTPUT_DIR}/hierarchical_gid_27deg_signaling_stats.json" "${OUTPUT_JSON}"
        SIZE=$(du -h "${OUTPUT_JSON}" | cut -f1)
        echo -e "${GREEN}  ✓ 已生成：${OUTPUT_JSON} (${SIZE})${NC}"
    else
        echo -e "${RED}  ✗ 未找到輸出檔案${NC}"
    fi
    
    # 清理臨時目錄
    rm -rf "${TEMP_K_DIR}" "${TEMP_OUTPUT_DIR}"
    echo ""
done

# 處理 K=8（從舊檔案複製）
echo -e "${BLUE}----------------------------------------${NC}"
echo -e "${BLUE}處理 K=8...${NC}"
echo -e "${BLUE}----------------------------------------${NC}"

K8_SOURCE="${OUTPUT_DIR}/hierarchical_gid_27deg_signaling_stats.json"
K8_OUTPUT="${OUTPUT_DIR}/hierarchical_gid_27deg_k8_signaling_stats.json"

if [ -f "${K8_SOURCE}" ] && [ ! -f "${K8_OUTPUT}" ]; then
    cp "${K8_SOURCE}" "${K8_OUTPUT}"
    echo -e "${GREEN}  ✓ 已複製：${K8_OUTPUT}${NC}"
elif [ -f "${K8_OUTPUT}" ]; then
    echo -e "${GREEN}  ✓ 已存在：${K8_OUTPUT}${NC}"
else
    echo -e "${YELLOW}  ⚠ 未找到 K=8 的統計檔案${NC}"
fi
echo ""

# 列出所有生成的檔案
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  完成！生成的統計檔案：${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
ls -lh ${OUTPUT_DIR}/hierarchical_gid_27deg_k*_signaling_stats.json
echo ""
