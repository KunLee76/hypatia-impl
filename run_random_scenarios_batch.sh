#!/bin/bash

# ========================================
# Random 場景批次執行腳本（使用 Starlink 星座）
# 18 個場景：P1/P5/P10 × K(1,2,4,6,8,999)
# 時長：200 秒
# Time step：2000ms（每 2 秒一個 snapshot）
# Chaos Monkey：每個 snapshot 觸發（每 2 秒）
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
export SATGEN_GRID_DEG=27

# 模擬參數
DURATION=200
TIME_STEP=2000  # 2000ms = 2秒
ISL_TYPE="isls_plus_grid"
GS_TYPE="ground_stations_top_100_with_hsinchu"
ALGORITHM="algorithm_hierarchical_virtual_gid"
THREADS=4
GRID_DEG=27

# 開始時間
START_TIME=$(date +%s)
echo ""
echo "========================================"
echo "開始執行 Random 場景批次模擬"
echo "========================================"
echo "星座：Starlink-550"
echo "時長：${DURATION} 秒"
echo "Time step：${TIME_STEP} ms"
echo "Chaos 間隔：每 2 秒"
echo "地面站：${GS_TYPE}"
echo "執行緒：${THREADS}"
echo "Grid degree：${GRID_DEG}"
echo "========================================"
echo ""

# 計數器
TOTAL=18
COMPLETED=0
FAILED=0

# 失效率陣列
FAILURE_RATES=("0.01" "0.05" "0.10")
FAILURE_LABELS=("P1" "P5" "P10")

# K 值陣列
K_VALUES=(1 2 4 6 8 999)

# 執行所有場景
for i in "${!FAILURE_RATES[@]}"; do
    RATE="${FAILURE_RATES[$i]}"
    LABEL="${FAILURE_LABELS[$i]}"
    
    echo ""
    echo "========================================"
    echo "執行 ${LABEL} 系列（失效率 ${RATE}）"
    echo "========================================"
    
    export CHAOS_FAILURE_RATE=$RATE
    
    for K in "${K_VALUES[@]}"; do
        SCENARIO_NAME="Random_${LABEL}_K${K}"
        LOG_FILE="../../logs/chaos_${LABEL,,}_k${K}.log"
        
        export CHAOS_LOG_FILE=$LOG_FILE
        
        echo ""
        echo "----------------------------------------"
        echo "場景 [$((COMPLETED+1))/$TOTAL]: $SCENARIO_NAME"
        echo "失效率：${RATE} (${LABEL})"
        echo "K 值：${K}"
        echo "日誌：${LOG_FILE}"
        echo "----------------------------------------"
        
        # 執行模擬
        SCENARIO_START=$(date +%s)
        
        if python main_starlink_550.py $DURATION $TIME_STEP $ISL_TYPE $GS_TYPE $ALGORITHM $THREADS $GRID_DEG $K; then
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
SUMMARY_FILE="../../logs/random_scenarios_summary_$(date +%Y%m%d_%H%M%S).txt"
echo "生成摘要報告：${SUMMARY_FILE}"

cat > "$SUMMARY_FILE" << EOF
========================================
Random 場景批次執行摘要
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

for i in "${!FAILURE_RATES[@]}"; do
    RATE="${FAILURE_RATES[$i]}"
    LABEL="${FAILURE_LABELS[$i]}"
    
    echo "" >> "$SUMMARY_FILE"
    echo "${LABEL} 系列（失效率 ${RATE}）：" >> "$SUMMARY_FILE"
    
    for K in "${K_VALUES[@]}"; do
        LOG_FILE="../../logs/chaos_${LABEL,,}_k${K}.log"
        
        if [ -f "$LOG_FILE" ]; then
            INJECTION_COUNT=$(grep -c "\[CHAOS_MONKEY\]" "$LOG_FILE" || echo "0")
            echo "  ✅ Random_${LABEL}_K${K} - 注入次數：${INJECTION_COUNT}" >> "$SUMMARY_FILE"
        else
            echo "  ❌ Random_${LABEL}_K${K} - 日誌未生成" >> "$SUMMARY_FILE"
        fi
    done
done

echo ""
echo "摘要報告已儲存：${SUMMARY_FILE}"
echo ""
echo "完成！"
