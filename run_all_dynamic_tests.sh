#!/bin/bash

################################################################################
# 動態 ISL 失效場景 - Baseline & LoHi 執行腳本
################################################################################
# 用途：執行 Baseline 和 LoHi 的動態失效測試（P1/P5/P10）
# 前提：GRHR 數據已由 rerun_grhr_dynamic_200s.sh 生成
# 總共：6 個實驗 (3 Baseline + 3 LoHi)
# 預估時間：每個約 10 分鐘，總共約 1 小時
################################################################################

set -e  # 遇到錯誤立即停止

# 停用可能存在的 venv，然後啟用 conda 環境
deactivate 2>/dev/null || true
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
DURATION=200
TIMESTEP=2000
ISLS_BASE="isls_random"  # 會動態設置為 isls_random_p1, p5, p10
GS="ground_stations_top_100_with_hsinchu"
THREADS=10
GRID_DEG=27

# 目錄設置
WORK_DIR="paper/satellite_networks_state"
RESULT_DIR="${WORK_DIR}/analytic_result"
BACKUP_DIR="${RESULT_DIR}/dynamic_backup_$(date +%Y%m%d_%H%M%S)"

# 場景定義
SCENARIOS=("p1" "p5" "p10")
FAILURE_RATES=(1 5 10)

# 日誌文件
LOG_FILE="run_dynamic_tests_$(date +%Y%m%d_%H%M%S).log"

echo -e "${BLUE}================================================================================================${NC}"
echo -e "${BLUE}動態 ISL 失效場景批次執行腳本${NC}"
echo -e "${BLUE}================================================================================================${NC}"
echo "開始時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo "日誌文件: ${LOG_FILE}"
echo ""
echo "測試配置:"
echo "  - 模擬時長: ${DURATION} 秒"
echo "  - 時間步長: ${TIMESTEP} ms"
echo "  - 網格角度: ${GRID_DEG}°"
echo "  - 場景數: ${#SCENARIOS[@]} (P1=1%, P5=5%, P10=10%)"
echo "  - 算法: Baseline (3個) + LoHi (3個)"
echo "  - 總實驗數: $((${#SCENARIOS[@]} * 2)) 個"
echo "  - 注意: GRHR 數據已存在，不重複執行"
echo ""

# 創建備份
echo -e "${YELLOW}[步驟 1/3] 備份現有 Baseline & LoHi 數據...${NC}"
mkdir -p "${BACKUP_DIR}"
cp -v ${RESULT_DIR}/baseline_random_*.json "${BACKUP_DIR}/" 2>/dev/null || echo "  無 Baseline 舊數據"
cp -v ${RESULT_DIR}/lohi_random_*.json "${BACKUP_DIR}/" 2>/dev/null || echo "  無 LoHi 舊數據"
echo "  ✓ 備份完成: ${BACKUP_DIR}"
echo ""

# 函數：執行單個實驗
run_experiment() {
    local algo=$1
    local scenario=$2
    local failure_rate=$3
    local exp_num=$4
    local total_exp=$5
    
    echo -e "${GREEN}[實驗 ${exp_num}/${total_exp}] ${algo} - ${scenario} (${failure_rate}% failure)${NC}"
    
    # 設置 ISL 類型
    local ISL_TYPE="${ISLS_BASE}_${scenario}"
    
    if [ "$algo" == "Baseline" ]; then
        echo "  算法: Floyd-Warshall Baseline"
        echo "  ISL類型: ${ISL_TYPE}"
        echo "  命令: ENABLE_CHAOS_MONKEY=true CHAOS_FAILURE_RATE=${failure_rate} python main_starlink_550.py ${DURATION} ${TIMESTEP} ${ISL_TYPE} ${GS} algorithm_free_one_only_over_isls ${THREADS}"
        
        cd "$WORK_DIR"
        ENABLE_CHAOS_MONKEY=true \
        CHAOS_FAILURE_RATE=${failure_rate} \
        python main_starlink_550.py \
            ${DURATION} ${TIMESTEP} ${ISL_TYPE} ${GS} \
            algorithm_free_one_only_over_isls \
            ${THREADS} \
            >> "../../${LOG_FILE}" 2>&1
        
        # 合併統計文件
        echo "  🔄 合併統計文件..."
        TEMP_DIR="analytic_result/temp_baseline_dynamic_${scenario}"
        OUTPUT_FILE="analytic_result/baseline_random_${scenario}_signaling_stats.json"
        
        cd ../..
        if [ -d "paper/satellite_networks_state/$TEMP_DIR" ]; then
            python3 merge_random_stats_simple.py "paper/satellite_networks_state/$TEMP_DIR" "paper/satellite_networks_state/$OUTPUT_FILE"
        fi
        cd "$WORK_DIR"
        
        cd - > /dev/null
        
        output_file="${RESULT_DIR}/baseline_random_${scenario}_signaling_stats.json"
        if [ -f "$output_file" ]; then
            echo -e "  ${GREEN}✓${NC} 完成: $(basename $output_file)"
        else
            echo -e "  ${RED}✗${NC} 失敗: 輸出文件未生成"
            return 1
        fi
        
    elif [ "$algo" == "LoHi" ]; then
        echo "  算法: LoHi (p=6, s=10)"
        echo "  ISL類型: ${ISL_TYPE}"
        echo "  命令: ENABLE_CHAOS_MONKEY=true CHAOS_FAILURE_RATE=${failure_rate} python main_starlink_550.py ${DURATION} ${TIMESTEP} ${ISL_TYPE} ${GS} algorithm_lohi ${THREADS}"
        
        cd "$WORK_DIR"
        ENABLE_CHAOS_MONKEY=true \
        CHAOS_FAILURE_RATE=${failure_rate} \
        python main_starlink_550.py \
            ${DURATION} ${TIMESTEP} ${ISL_TYPE} ${GS} \
            algorithm_lohi \
            ${THREADS} \
            >> "../../${LOG_FILE}" 2>&1
        
        # 合併統計文件
        echo "  🔄 合併統計文件..."
        TEMP_DIR="analytic_result/temp_lohi_dynamic_${scenario}"
        OUTPUT_FILE="analytic_result/lohi_random_${scenario}_signaling_stats.json"
        
        cd ../..
        if [ -d "paper/satellite_networks_state/$TEMP_DIR" ]; then
            python3 merge_random_stats_simple.py "paper/satellite_networks_state/$TEMP_DIR" "paper/satellite_networks_state/$OUTPUT_FILE"
        fi
        cd "$WORK_DIR"
        
        cd - > /dev/null
        
        output_file="${RESULT_DIR}/lohi_random_${scenario}_signaling_stats.json"
        if [ -f "$output_file" ]; then
            echo -e "  ${GREEN}✓${NC} 完成: $(basename $output_file)"
        else
            echo -e "  ${RED}✗${NC} 失敗: 輸出文件未生成"
            return 1
        fi
    fi
    
    echo ""
}

# 主執行流程
total_experiments=$((${#SCENARIOS[@]} * 2))
current_exp=0

echo -e "${YELLOW}[步驟 2/3] 執行 Baseline 動態失效測試 (3 個實驗)...${NC}"
for i in "${!SCENARIOS[@]}"; do
    scenario="${SCENARIOS[$i]}"
    failure_rate="${FAILURE_RATES[$i]}"
    current_exp=$((current_exp + 1))
    run_experiment "Baseline" "$scenario" "$failure_rate" "$current_exp" "$total_experiments"
done

echo -e "${YELLOW}[步驟 3/3] 執行 LoHi 動態失效測試 (3 個實驗)...${NC}"
for i in "${!SCENARIOS[@]}"; do
    scenario="${SCENARIOS[$i]}"
    failure_rate="${FAILURE_RATES[$i]}"
    current_exp=$((current_exp + 1))
    run_experiment "LoHi" "$scenario" "$failure_rate" "$current_exp" "$total_experiments"
done

echo -e "${BLUE}================================================================================================${NC}"
echo -e "${GREEN}Baseline & LoHi 動態失效測試完成！${NC}"
echo -e "${BLUE}================================================================================================${NC}"
echo "完成時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "輸出文件位置: ${RESULT_DIR}"
echo "  - Baseline: baseline_random_{p1|p5|p10}_signaling_stats.json"
echo "  - LoHi: lohi_random_{p1|p5|p10}_signaling_stats.json"
echo "  - GRHR: hierarchical_gid_27deg_random_{p1|p5|p10}_k{1-999}_signaling_stats.json (已存在)"
echo ""
echo "備份位置: ${BACKUP_DIR}"
echo "詳細日誌: ${LOG_FILE}"
echo ""
echo "下一步："
echo "  1. 執行 analyze_random_failure_scenarios.py 分析 GRHR K 參數影響"
echo "  2. 使用 hypatia_multi_algorithm_analyzer.py 進行多算法比較"
echo ""
