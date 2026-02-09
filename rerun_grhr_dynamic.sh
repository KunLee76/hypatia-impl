#!/bin/bash

###############################################################################
# GRHR 動態失效場景重跑腳本
# 
# 目的：修復 refresh_gid_members_and_subgraphs() 雙重調用問題後重新執行
# 場景：P1/P5/P10 動態失效（Chaos Monkey）
# K值：K=4 和 K=8
# 
# 用法：bash rerun_grhr_dynamic.sh
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "========================================================================"
echo "  GRHR 動態失效場景重跑（修復雙重調用問題）"
echo "========================================================================"
echo ""
echo "場景："
echo "  - P1/P5/P10 動態失效（Chaos Monkey）"
echo "  - K=4 和 K=8"
echo "  - 修復後預期：gid_rebuilds 減半"
echo ""
echo "按 Enter 繼續，或 Ctrl+C 取消..."
read

# 激活 conda 環境
echo ""
echo "激活 Python 環境..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia
echo "✓ 環境已激活: $(which python3)"
echo ""

# 配置
DURATION=200
TIME_STEP=2000
CONSTELLATION="starlink_550"
ISL_SELECTION="isls_plus_grid"
GROUND_STATIONS="ground_stations_top_100_with_hsinchu"
ALGORITHM="algorithm_hierarchical_virtual_gid"
NUM_THREADS=4

# 失效率和 K 值
FAILURE_RATES=("0.01" "0.05" "0.10")
FAILURE_LABELS=("p1" "p5" "p10")
K_VALUES=(4 8)

# 輸出目錄
ANALYTIC_DIR="paper/satellite_networks_state/analytic_result"

echo ""
echo "========================================================================"
echo "  開始執行 GRHR 重跑"
echo "========================================================================"
echo ""

TOTAL_RUNS=$((${#FAILURE_RATES[@]} * ${#K_VALUES[@]}))
CURRENT_RUN=0

# 遍歷所有 K 值
for K in "${K_VALUES[@]}"; do
    echo ""
    echo "--------------------------------------------------------------------"
    echo "  K=${K}"
    echo "--------------------------------------------------------------------"
    echo ""
    
    # 遍歷所有失效率
    for i in "${!FAILURE_RATES[@]}"; do
        FAILURE_RATE="${FAILURE_RATES[$i]}"
        LABEL="${FAILURE_LABELS[$i]}"
        CURRENT_RUN=$((CURRENT_RUN + 1))
        
        echo ""
        echo -e "${BLUE}[${CURRENT_RUN}/${TOTAL_RUNS}] GRHR K=${K} ${LABEL^^}${NC}"
        echo "  失效率: ${FAILURE_RATE}"
        echo "  輸出: hierarchical_gid_27deg_dynamic_${LABEL}_k${K}_signaling_stats.json"
        echo ""
        
        # 設置環境變量
        export ENABLE_CHAOS_MONKEY=true
        export CHAOS_FAILURE_RATE="${FAILURE_RATE}"
        export CHAOS_INTERVAL_SNAPSHOTS=20
        export K_VALUE="${K}"
        
        # 執行模擬
        echo -e "${YELLOW}執行中...${NC}"
        start_time=$(date +%s)
        
        cd "${SCRIPT_DIR}/paper/satellite_networks_state"
        
        if python main_${CONSTELLATION}.py \
            ${DURATION} \
            ${TIME_STEP} \
            ${ISL_SELECTION} \
            ${GROUND_STATIONS} \
            ${ALGORITHM} \
            ${NUM_THREADS}; then
            
            end_time=$(date +%s)
            elapsed=$((end_time - start_time))
            minutes=$((elapsed / 60))
            seconds=$((elapsed % 60))
            
            echo -e "${GREEN}✓ 完成${NC} (耗時: ${minutes}分${seconds}秒)"
            
            # 檢查輸出文件
            OUTPUT_FILE="${ANALYTIC_DIR}/hierarchical_gid_27deg_dynamic_${LABEL}_k${K}_signaling_stats.json"
            if [ -f "$OUTPUT_FILE" ]; then
                # 快速驗證：提取關鍵統計
                gid_rebuilds=$(python3 -c "import json; d=json.load(open('$OUTPUT_FILE')); print(d.get('gid_rebuilds', 0))")
                total_messages=$(python3 -c "import json; d=json.load(open('$OUTPUT_FILE')); print(d.get('total_messages', 0))")
                echo "  統計: GID重建=${gid_rebuilds}, 總訊息=${total_messages}"
            else
                echo -e "${RED}⚠ 警告：輸出文件未生成${NC}"
            fi
        else
            end_time=$(date +%s)
            elapsed=$((end_time - start_time))
            echo -e "${RED}✗ 失敗${NC} (耗時: ${elapsed}秒)"
            echo "  場景: GRHR K=${K} ${LABEL}"
            exit 1
        fi
        
        cd "${SCRIPT_DIR}"
    done
done

echo ""
echo "========================================================================"
echo "  GRHR 重跑完成！"
echo "========================================================================"
echo ""
echo "生成的文件："
for K in "${K_VALUES[@]}"; do
    for LABEL in "${FAILURE_LABELS[@]}"; do
        FILE="${ANALYTIC_DIR}/hierarchical_gid_27deg_dynamic_${LABEL}_k${K}_signaling_stats.json"
        if [ -f "$FILE" ]; then
            SIZE=$(du -h "$FILE" | cut -f1)
            echo "  ✓ ${FILE} (${SIZE})"
        else
            echo -e "  ${RED}✗ ${FILE} (未生成)${NC}"
        fi
    done
done

echo ""
echo "下一步："
echo "  1. 驗證修復效果："
echo "     python3 verify_grhr_fix.py"
echo ""
echo "  2. 生成完整對比分析："
echo "     python3 analyze_algorithm_comparison_dynamic.py"
echo ""
echo "========================================================================"
