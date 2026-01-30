#!/bin/bash

# =========================================================================
# 隨機 ISL 失效場景批量實驗腳本 (20秒模擬)
# =========================================================================
# 用途：執行 18 個隨機失效場景實驗
#       - 3 個失效概率場景: p1 (1%), p5 (5%), p10 (10%)
#       - 6 個 K 值: 1, 2, 4, 6, 8, 999
#
# 執行方式：
#   chmod +x run_random_failure_scenarios_20s.sh
#   ./run_random_failure_scenarios_20s.sh
#
# 輸出目錄結構：
#   gen_data/starlink_550_isls_random_p1_27deg_k*/
#   gen_data/starlink_550_isls_random_p5_27deg_k*/
#   gen_data/starlink_550_isls_random_p10_27deg_k*/
#
# 統計文件：
#   analytic_result/temp_grhr_random_p*_k*/grhr_stats_pid*_tid*.json
#   (最終合併成 hierarchical_gid_27deg_random_p*_k*_signaling_stats.json)
# =========================================================================

# 配置參數
DURATION_S=20        # 模擬時長（秒）
TIMESTEP_MS=100      # 時間步長（毫秒）
GRID_DEG=27          # 網格大小（度）
NUM_THREADS=10       # 並行線程數

# 場景定義：失效概率（格式: 標籤:概率值）
SCENARIOS=(
    "p1:0.01"    # 1% 失效率
    "p5:0.05"    # 5% 失效率
    "p10:0.10"   # 10% 失效率
)

# K 值列表
K_VALUES=(1 2 4 6 8 999)

# 固定隨機種子（確保可重複性）
RANDOM_SEED=42

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}隨機 ISL 失效場景批量實驗${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "配置參數："
echo "  - 模擬時長: ${DURATION_S}s"
echo "  - 時間步長: ${TIMESTEP_MS}ms"
echo "  - 網格大小: ${GRID_DEG}°"
echo "  - 線程數: ${NUM_THREADS}"
echo "  - 隨機種子: ${RANDOM_SEED}"
echo ""
echo "場景數量: ${#SCENARIOS[@]} 種失效率"
echo "K 值數量: ${#K_VALUES[@]} 種配置"
echo "總實驗數: $((${#SCENARIOS[@]} * ${#K_VALUES[@]})) 個"
echo ""

# 計算預估時間（每個實驗約 15 分鐘）
TOTAL_EXPERIMENTS=$((${#SCENARIOS[@]} * ${#K_VALUES[@]}))
ESTIMATED_MINUTES=$((TOTAL_EXPERIMENTS * 15))
ESTIMATED_HOURS=$((ESTIMATED_MINUTES / 60))
ESTIMATED_MINUTES_REMAIN=$((ESTIMATED_MINUTES % 60))

echo -e "${YELLOW}預估總耗時: ${ESTIMATED_HOURS}h ${ESTIMATED_MINUTES_REMAIN}min${NC}"
echo ""

# 確認執行
read -p "是否繼續執行? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消執行"
    exit 1
fi

# 切換到工作目錄
cd "$(dirname "$0")/paper/satellite_networks_state" || exit 1

# 計數器
CURRENT=0
FAILED=0
SUCCESS=0

# 開始時間
START_TIME=$(date +%s)

echo ""
echo -e "${GREEN}開始執行實驗...${NC}"
echo ""

# 遍歷所有場景和 K 值組合
for scenario_config in "${SCENARIOS[@]}"; do
    # 解析場景配置
    IFS=':' read -r scenario_label failure_prob <<< "$scenario_config"
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}場景: Random ${scenario_label} (失效率=${failure_prob})${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    for K in "${K_VALUES[@]}"; do
        CURRENT=$((CURRENT + 1))
        
        echo ""
        echo -e "${YELLOW}[${CURRENT}/${TOTAL_EXPERIMENTS}] 執行: Random ${scenario_label}, K=${K}${NC}"
        echo "---"
        
        # 設定環境變數
        export SATGEN_GRID_DEG=${GRID_DEG}
        export K_BEST_GATEWAYS=${K}
        
        # 執行實驗
        # 注意：ISL selection 參數格式為 isls_random_pX
        python main_starlink_550.py \
            ${DURATION_S} \
            ${TIMESTEP_MS} \
            "isls_random_${scenario_label}" \
            ground_stations_top_100 \
            algorithm_hierarchical_virtual_gid \
            ${NUM_THREADS} \
            ${GRID_DEG} \
            ${K} \
            2>&1 | tee "../../logs/random_${scenario_label}_k${K}.log"
        
        # 檢查執行結果
        if [ ${PIPESTATUS[0]} -eq 0 ]; then
            echo -e "${GREEN}✓ Random ${scenario_label}, K=${K} 完成${NC}"
            SUCCESS=$((SUCCESS + 1))
        else
            echo -e "${RED}✗ Random ${scenario_label}, K=${K} 失敗${NC}"
            FAILED=$((FAILED + 1))
        fi
        
        # 顯示進度
        PERCENT=$((CURRENT * 100 / TOTAL_EXPERIMENTS))
        ELAPSED=$(($(date +%s) - START_TIME))
        AVG_TIME=$((ELAPSED / CURRENT))
        REMAINING=$((AVG_TIME * (TOTAL_EXPERIMENTS - CURRENT)))
        
        echo "進度: ${PERCENT}% (${CURRENT}/${TOTAL_EXPERIMENTS})"
        echo "已耗時: $((ELAPSED / 60))min, 預估剩餘: $((REMAINING / 60))min"
    done
done

# 結束時間
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}批量實驗執行完畢${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "執行摘要："
echo "  - 總實驗數: ${TOTAL_EXPERIMENTS}"
echo "  - 成功: ${GREEN}${SUCCESS}${NC}"
echo "  - 失敗: ${RED}${FAILED}${NC}"
echo "  - 總耗時: $((TOTAL_TIME / 3600))h $((TOTAL_TIME % 3600 / 60))min $((TOTAL_TIME % 60))s"
echo ""

if [ ${FAILED} -eq 0 ]; then
    echo -e "${GREEN}✓ 所有實驗執行成功！${NC}"
    echo ""
    echo "下一步："
    echo "  1. 合併統計數據："
    echo "     ./merge_all_random_failure_scenarios.sh"
    echo ""
    echo "  2. 生成分析圖表："
    echo "     python analyze_random_failure_scenarios.py"
else
    echo -e "${YELLOW}⚠ 部分實驗執行失敗，請檢查日誌文件${NC}"
    echo "失敗日誌位置: logs/random_*.log"
fi

echo ""
echo "輸出目錄："
echo "  - 場景數據: gen_data/starlink_550_isls_random_p*_27deg_k*/"
echo "  - 臨時統計: analytic_result/temp_grhr_random_p*_k*/"
echo "  - 執行日誌: logs/random_*.log"
