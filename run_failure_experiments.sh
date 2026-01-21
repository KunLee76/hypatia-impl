#!/bin/bash

# ISL 失效場景批次實驗腳本
# 
# 功能：對每個失效場景 × 每個 K 值運行實驗
# 輸出：gen_data/starlink_550_isls_failure_XX_..._k{K}/
#
# 使用方式：
#   bash run_failure_experiments.sh
#
# 注意：
#   1. 確保已生成失效場景：input_data/failure_scenarios/isls_*.txt
#   2. 實驗時間較長：5 個場景 × 6 個 K 值 = 30 個實驗
#   3. 每個實驗約 15 分鐘（200s, 100ms timestep）

# 激活 conda 環境
source /home/kun/miniconda3/bin/activate kun_hypatia

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 創建日誌目錄
mkdir -p /home/kun/ssd2t/Leo/kun_hypatia/logs

echo "======================================================"
echo "ISL 失效場景批次實驗"
echo "======================================================"
echo ""
echo "實驗配置："
echo "  時長: 100 秒"
echo "  時間步: 100 毫秒"
echo "  網格度數: 27°"
echo "  並行執行緒: 10"
echo "  失效場景: baseline, l1, l2, l3, l4"
echo "  K 值: 1, 2, 4, 6, 8, 999"
echo ""
echo "預估總時間: ~3.5 小時（30 個實驗 × 7 分鐘）"
echo "======================================================"
echo ""

# 失效場景列表
SCENARIOS=("baseline" "failure_l1" "failure_l2" "failure_l3" "failure_l4")
SCENARIO_NAMES=("Baseline (無失效)" "Level 1 (輕度)" "Level 2 (中度)" "Level 3 (重度)" "Level 4 (極端)")

# K 值列表
K_VALUES=(1 2 4 6 8 999)

# 實驗計數器
TOTAL_EXPERIMENTS=$((${#SCENARIOS[@]} * ${#K_VALUES[@]}))
CURRENT_EXPERIMENT=0
FAILED_EXPERIMENTS=()

echo "開始時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 雙層循環：場景 × K值
for i in "${!SCENARIOS[@]}"; do
    SCENARIO="${SCENARIOS[$i]}"
    SCENARIO_NAME="${SCENARIO_NAMES[$i]}"
    
    echo "======================================================"
    echo "場景 $((i+1))/${#SCENARIOS[@]}: $SCENARIO_NAME"
    echo "======================================================"
    echo ""
    
    for K in "${K_VALUES[@]}"; do
        CURRENT_EXPERIMENT=$((CURRENT_EXPERIMENT + 1))
        
        echo "------------------------------------------------------"
        echo "實驗 ${CURRENT_EXPERIMENT}/${TOTAL_EXPERIMENTS}"
        echo "場景: ${SCENARIO_NAME}"
        echo "K 值: ${K}"
        echo "開始時間: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "------------------------------------------------------"
        
        # 構建 ISL 選擇參數
        if [ "$SCENARIO" == "baseline" ]; then
            ISL_PARAM="isls_plus_grid"
        else
            ISL_PARAM="isls_${SCENARIO}"
        fi
        
        # 運行實驗
        echo "🚀 執行指令:"
        echo "   python main_starlink_550.py 100 100 \\"
        echo "     ${ISL_PARAM} \\"
        echo "     ground_stations_top_100_with_hsinchu \\"
        echo "     algorithm_hierarchical_virtual_gid 10 27 ${K}"
        echo ""
        
        # 記錄開始時間
        START_TIME=$(date +%s)
        
        # 執行（將輸出重定向到日誌文件）
        LOG_FILE="logs/failure_exp_${SCENARIO}_k${K}.log"
        mkdir -p logs
        
        python main_starlink_550.py 100 100 \
            ${ISL_PARAM} \
            ground_stations_top_100_with_hsinchu \
            algorithm_hierarchical_virtual_gid 10 27 ${K} \
            > "${LOG_FILE}" 2>&1
        
        EXIT_CODE=$?
        
        # 計算執行時間
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        MINUTES=$((DURATION / 60))
        SECONDS=$((DURATION % 60))
        
        if [ $EXIT_CODE -eq 0 ]; then
            echo "✅ 完成！耗時: ${MINUTES}分${SECONDS}秒"
        else
            echo "❌ 失敗！退出碼: ${EXIT_CODE}"
            FAILED_EXPERIMENTS+=("${SCENARIO}_k${K}")
        fi
        
        echo "結束時間: $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
        
        # 顯示進度
        PROGRESS=$((CURRENT_EXPERIMENT * 100 / TOTAL_EXPERIMENTS))
        echo "📊 總體進度: ${CURRENT_EXPERIMENT}/${TOTAL_EXPERIMENTS} (${PROGRESS}%)"
        echo ""
        
        # 小休息，避免系統過載
        if [ ${CURRENT_EXPERIMENT} -lt ${TOTAL_EXPERIMENTS} ]; then
            echo "⏸  休息 5 秒..."
            sleep 5
            echo ""
        fi
    done
done

echo "======================================================"
echo "✅ 所有實驗完成！"
echo "======================================================"
echo "完成時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "實驗統計："
echo "  總實驗數: ${TOTAL_EXPERIMENTS}"
echo "  成功: $((TOTAL_EXPERIMENTS - ${#FAILED_EXPERIMENTS[@]}))"
echo "  失敗: ${#FAILED_EXPERIMENTS[@]}"

if [ ${#FAILED_EXPERIMENTS[@]} -gt 0 ]; then
    echo ""
    echo "失敗的實驗："
    for exp in "${FAILED_EXPERIMENTS[@]}"; do
        echo "  - ${exp}"
    done
fi

echo ""
echo "======================================================"
echo "下一步："
echo "1. 檢查生成的目錄："
echo "   ls -d gen_data/starlink_550_isls_*_27deg_k*/"
echo ""
echo "2. 合併控制信令統計："
echo "   cd /home/kun/ssd2t/Leo/kun_hypatia"
echo "   python merge_signaling_stats.py"
echo ""
echo "3. 運行 RTT 分析："
echo "   bash analyze_failure_rtt.sh"
echo "======================================================"
