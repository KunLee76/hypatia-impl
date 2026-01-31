#!/bin/bash

# =========================================================================
# 合併所有動態失效場景（Chaos Monkey）的統計數據
# =========================================================================
# 用途：將各個 Dynamic 場景的臨時統計文件合併成最終統計文件
#
# 輸入：
#   analytic_result/temp_grhr_dynamic_p*_k*/grhr_stats_pid*_tid*.json
#
# 輸出：
#   analytic_result/hierarchical_gid_27deg_dynamic_p*_k*_signaling_stats.json
#
# 執行方式：
#   ./merge_all_dynamic_scenarios.sh
# =========================================================================

# 切換到工作目錄
cd "$(dirname "$0")/paper/satellite_networks_state" || exit 1

# 顏色輸出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}合併動態失效場景統計數據${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# 定義場景和 K 值
SCENARIOS=("p1" "p5" "p10")
K_VALUES=(1 2 4 6 8 999)

# 計數器
TOTAL=$((${#SCENARIOS[@]} * ${#K_VALUES[@]}))
CURRENT=0
SUCCESS=0
FAILED=0

# 遍歷所有場景和 K 值組合
for scenario in "${SCENARIOS[@]}"; do
    echo -e "${YELLOW}處理場景: dynamic_${scenario}${NC}"
    echo "---"
    
    for K in "${K_VALUES[@]}"; do
        CURRENT=$((CURRENT + 1))
        
        TEMP_DIR="analytic_result/temp_grhr_dynamic_${scenario}_k${K}"
        OUTPUT_FILE="analytic_result/hierarchical_gid_27deg_dynamic_${scenario}_k${K}_signaling_stats.json"
        
        echo -n "[$CURRENT/$TOTAL] 合併 dynamic_${scenario}, K=${K} ... "
        
        # 檢查臨時目錄是否存在
        if [ ! -d "$TEMP_DIR" ]; then
            echo -e "${RED}失敗 (目錄不存在: $TEMP_DIR)${NC}"
            FAILED=$((FAILED + 1))
            continue
        fi
        
        # 檢查是否有統計文件
        STAT_FILES=$(find "$TEMP_DIR" -name "grhr_stats_pid*_tid*.json" 2>/dev/null)
        if [ -z "$STAT_FILES" ]; then
            echo -e "${RED}失敗 (無統計文件)${NC}"
            FAILED=$((FAILED + 1))
            continue
        fi
        
        # 使用简单合并脚本
        python3 ../../merge_random_stats_simple.py \
            "$TEMP_DIR" \
            "$OUTPUT_FILE" \
            > /dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}完成${NC}"
            SUCCESS=$((SUCCESS + 1))
        else
            echo -e "${RED}失敗${NC}"
            FAILED=$((FAILED + 1))
        fi
    done
    echo ""
done

# 結果摘要
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}合併完成${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "結果摘要："
echo "  - 總場景數: $TOTAL"
echo "  - 成功: ${GREEN}${SUCCESS}${NC}"
echo "  - 失敗: ${RED}${FAILED}${NC}"
echo ""

if [ $SUCCESS -gt 0 ]; then
    echo "輸出文件："
    ls -lh analytic_result/hierarchical_gid_27deg_dynamic_*.json 2>/dev/null
    echo ""
    echo -e "${GREEN}✓ 統計數據合併成功！${NC}"
    echo ""
    echo "驗證時間範圍："
    for json_file in analytic_result/hierarchical_gid_27deg_dynamic_*.json; do
        if [ -f "$json_file" ]; then
            echo "  $(basename $json_file):"
            python3 -c "import json; d=json.load(open('$json_file')); print(f'    時間範圍: {d.get(\"time_window\", \"N/A\")}, 事件數: {d.get(\"total_events\", 0)}')"
        fi
    done
else
    echo -e "${RED}✗ 所有場景合併失敗${NC}"
    exit 1
fi
