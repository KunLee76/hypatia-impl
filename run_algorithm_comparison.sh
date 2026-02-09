#!/bin/bash

# ========================================
# 演算法比較實驗批次執行腳本
# 比較 GRHR (K=4, K=8)、LoHi、Baseline 在動態失效場景下的表現
# ========================================
# 
# 實驗設計：
#   - 失效率：P1 (1%), P5 (5%), P10 (10%)
#   - 演算法：
#     1. GRHR K=4 (已完成)
#     2. GRHR K=8 (已完成)
#     3. LoHi
#     4. Baseline (algorithm_free_one_only_over_isls_with_stats)
#   - Chaos Monkey：每 2 秒動態注入失效
#   - 模擬時長：200 秒
#
# 本腳本執行 LoHi 和 Baseline 的模擬（GRHR 已有數據）
# ========================================

set -e

# 啟動 conda 環境
echo "啟動 conda 環境..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

# 切換到工作目錄
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 清除 Python 快取
echo "清除 Python 快取..."
cd /home/kun/ssd2t/Leo/kun_hypatia
find satgenpy -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find satgenpy -name "*.pyc" -delete 2>/dev/null || true
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 創建日誌目錄
mkdir -p ../../logs

# Chaos Monkey 固定設定
export ENABLE_CHAOS_MONKEY=true
export CHAOS_INTERVAL_SNAPSHOTS=1  # 每個 snapshot 觸發（2秒一次）

# 模擬參數
DURATION=200
TIME_STEP=2000  # 2000ms = 2秒
GS_TYPE="ground_stations_top_100_with_hsinchu"
THREADS=4

# 開始時間
START_TIME=$(date +%s)
echo ""
echo "========================================"
echo "開始執行演算法比較實驗"
echo "========================================"
echo "星座：Starlink-550"
echo "時長：${DURATION} 秒"
echo "Time step：${TIME_STEP} ms"
echo "Chaos 間隔：每 2 秒"
echo "地面站：${GS_TYPE}"
echo "執行緒：${THREADS}"
echo ""
echo "演算法列表："
echo "  1. LoHi"
echo "  2. Baseline (algorithm_free_one_only_over_isls_with_stats)"
echo ""
echo "失效率：P1 (1%), P5 (5%), P10 (10%)"
echo "========================================"
echo ""

# 計數器
TOTAL=6  # 2 演算法 × 3 失效率
COMPLETED=0
FAILED=0

# 失效率陣列
FAILURE_RATES=("0.01" "0.05" "0.10")
FAILURE_LABELS=("P1" "P5" "P10")

# 演算法陣列
ALGORITHMS=("algorithm_lohi" "algorithm_free_one_only_over_isls_with_stats")
ALGORITHM_NAMES=("LoHi" "Baseline")

# 執行所有場景
for i in "${!FAILURE_RATES[@]}"; do
    RATE="${FAILURE_RATES[$i]}"
    LABEL="${FAILURE_LABELS[$i]}"
    
    echo ""
    echo "========================================"
    echo "失效率：${LABEL} (${RATE})"
    echo "========================================"
    
    export CHAOS_FAILURE_RATE=$RATE
    
    for j in "${!ALGORITHMS[@]}"; do
        ALGORITHM="${ALGORITHMS[$j]}"
        ALG_NAME="${ALGORITHM_NAMES[$j]}"
        
        # ISL_TYPE 使用 dynamic 前綴
        ISL_TYPE="isls_dynamic_${LABEL,,}"  # isls_dynamic_p1, isls_dynamic_p5, isls_dynamic_p10
        
        SCENARIO_NAME="${ALG_NAME}_Dynamic_${LABEL}"
        LOG_FILE="../../logs/chaos_${ALG_NAME,,}_${LABEL,,}.log"
        
        export CHAOS_LOG_FILE=$LOG_FILE
        
        echo ""
        echo "----------------------------------------"
        echo "場景 [$((COMPLETED+1))/$TOTAL]: $SCENARIO_NAME"
        echo "演算法：${ALG_NAME}"
        echo "失效率：${RATE} (${LABEL})"
        echo "ISL Type: ${ISL_TYPE}"
        echo "日誌：${LOG_FILE}"
        echo "----------------------------------------"
        
        # 執行模擬
        SCENARIO_START=$(date +%s)
        
        if python main_starlink_550.py $DURATION $TIME_STEP $ISL_TYPE $GS_TYPE $ALGORITHM $THREADS; then
            SCENARIO_END=$(date +%s)
            SCENARIO_DURATION=$((SCENARIO_END - SCENARIO_START))
            COMPLETED=$((COMPLETED + 1))
            
            echo "✅ 完成：$SCENARIO_NAME（耗時 ${SCENARIO_DURATION} 秒）"
            
            # 檢查 Chaos Monkey 日誌
            if [ -f "$LOG_FILE" ]; then
                INJECTION_COUNT=$(grep -c "\[CHAOS_MONKEY\]" "$LOG_FILE" || echo "0")
                echo "   Chaos Monkey 注入次數：${INJECTION_COUNT}"
            else
                echo "   ⚠️  警告：Chaos Monkey 日誌未生成"
            fi
        else
            SCENARIO_END=$(date +%s)
            SCENARIO_DURATION=$((SCENARIO_END - SCENARIO_START))
            FAILED=$((FAILED + 1))
            
            echo "❌ 失敗：$SCENARIO_NAME（耗時 ${SCENARIO_DURATION} 秒）"
            echo "   繼續執行下一個場景..."
        fi
    done
done

# 結束時間
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
HOURS=$((TOTAL_DURATION / 3600))
MINUTES=$(((TOTAL_DURATION % 3600) / 60))
SECONDS=$((TOTAL_DURATION % 60))

echo ""
echo "========================================"
echo "批次執行完成"
echo "========================================"
echo "完成場景：${COMPLETED}/${TOTAL}"
echo "失敗場景：${FAILED}"
echo "總耗時：${HOURS} 小時 ${MINUTES} 分鐘 ${SECONDS} 秒"
echo "========================================"
echo ""

# 生成摘要報告
SUMMARY_FILE="../../logs/algorithm_comparison_summary_$(date +%Y%m%d_%H%M%S).txt"
echo "生成摘要報告：${SUMMARY_FILE}"

cat > "$SUMMARY_FILE" << EOF
========================================
演算法比較實驗執行摘要
========================================
執行日期：$(date '+%Y-%m-%d %H:%M:%S')
星座：Starlink-550
時長：${DURATION} 秒
Time step：${TIME_STEP} ms
Chaos 間隔：每 2 秒

執行結果：
  完成場景：${COMPLETED}/${TOTAL}
  失敗場景：${FAILED}
  總耗時：${HOURS}h ${MINUTES}m ${SECONDS}s

場景列表：
EOF

for j in "${!ALGORITHMS[@]}"; do
    ALG_NAME="${ALGORITHM_NAMES[$j]}"
    
    echo "" >> "$SUMMARY_FILE"
    echo "${ALG_NAME}：" >> "$SUMMARY_FILE"
    
    for i in "${!FAILURE_RATES[@]}"; do
        LABEL="${FAILURE_LABELS[$i]}"
        LOG_FILE="../../logs/chaos_${ALG_NAME,,}_${LABEL,,}.log"
        
        if [ -f "$LOG_FILE" ]; then
            INJECTION_COUNT=$(grep -c "\[CHAOS_MONKEY\]" "$LOG_FILE" || echo "0")
            echo "  ✅ ${ALG_NAME}_Dynamic_${LABEL} - 注入次數：${INJECTION_COUNT}" >> "$SUMMARY_FILE"
        else
            echo "  ❌ ${ALG_NAME}_Dynamic_${LABEL} - 日誌未生成" >> "$SUMMARY_FILE"
        fi
    done
done

echo ""
echo "摘要報告已儲存：${SUMMARY_FILE}"
echo ""
echo "完成！"
echo ""
echo "下一步：執行統計合併與分析腳本"
