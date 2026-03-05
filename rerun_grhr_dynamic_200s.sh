#!/bin/bash

# ========================================
# 重新執行 GRHR 動態失效場景（200秒，使用新的 control signaling 統計邏輯）
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

# 備份舊的 JSON 文件（如果存在）
echo ""
echo "========================================"
echo "備份舊的動態失效 JSON 文件"
echo "========================================"
cd analytic_result
BACKUP_DIR="BACKUP_random_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 備份 GRHR 動態失效的 JSON 文件（支援 random 和 dynamic 命名）
for file in hierarchical_gid_27deg_random_*.json hierarchical_gid_27deg_dynamic_*.json; do
    if [ -f "$file" ]; then
        mv "$file" "$BACKUP_DIR/"
        echo "  ✓ 已備份: $file"
    fi
done

echo "  ✅ 備份完成：$BACKUP_DIR"
echo ""

# 清理 temp 目錄
echo "========================================"
echo "清理舊的 temp 目錄"
echo "========================================"
for temp_dir in temp_grhr_random_* temp_grhr_dynamic_*; do
    if [ -d "$temp_dir" ]; then
        rm -rf "$temp_dir"
        echo "  ✓ 已清理: $temp_dir"
    fi
done
echo "  ✅ temp 目錄清理完成"
echo ""

# 返回到 paper/satellite_networks_state
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# Chaos Monkey 固定設定
export ENABLE_CHAOS_MONKEY=true
export CHAOS_INTERVAL_SNAPSHOTS=1  # 每個 snapshot 觸發（2秒一次）
export SATGEN_GRID_DEG=27

# 模擬參數
DURATION=200
TIME_STEP=2000  # 2000ms = 2秒
ISL_TYPE_BASE="isls_random"  # ⚠️ 使用 random 前綴讓 Python 自動推斷正確命名
GS_TYPE="ground_stations_top_100_with_hsinchu"
ALGORITHM="algorithm_hierarchical_virtual_gid"
THREADS=10  # 使用 10 個執行緒加速
GRID_DEG=27

# 開始時間
START_TIME=$(date +%s)
echo ""
echo "========================================"
echo "開始執行 GRHR 動態失效場景批次模擬"
echo "========================================"
echo "星座：Starlink-550"
echo "時長：${DURATION} 秒"
echo "Time step：${TIME_STEP} ms"
echo "Chaos 間隔：每 2 秒"
echo "ISL Type：${ISL_TYPE_BASE}_* (+ ENABLE_CHAOS_MONKEY)"
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
FAILURE_LABELS=("p1" "p5" "p10")  # 小寫，與 JSON 命名一致

# K 值陣列
K_VALUES=(1 2 4 6 8 999)

# 執行所有場景
for i in "${!FAILURE_RATES[@]}"; do
    RATE="${FAILURE_RATES[$i]}"
    LABEL="${FAILURE_LABELS[$i]}"
    
    echo ""
    echo "========================================"
    echo "執行 ${LABEL^^} 系列（失效率 ${RATE}）- 動態失效"
    echo "========================================"
    
    export CHAOS_FAILURE_RATE=$RATE
    
    for K in "${K_VALUES[@]}"; do
        SCENARIO_NAME="GRHR_random_${LABEL}_K${K}"
        LOG_FILE="../../logs/chaos_grhr_${LABEL}_k${K}.log"
        ISL_TYPE="${ISL_TYPE_BASE}_${LABEL}"  # isls_random_p1, isls_random_p5, isls_random_p10
        
        export CHAOS_LOG_FILE=$LOG_FILE
        export K_BEST_GATEWAYS=$K
        
        echo ""
        echo "----------------------------------------"
        echo "場景 [$((COMPLETED+1))/$TOTAL]: $SCENARIO_NAME"
        echo "失效率：${RATE} (${LABEL^^})"
        echo "K 值：${K}"
        echo "日誌：${LOG_FILE}"
        echo "----------------------------------------"
        
        # 清理舊的日誌文件
        if [ -f "$LOG_FILE" ]; then
            rm "$LOG_FILE"
        fi
        
        # 執行模擬
        SCENARIO_START=$(date +%s)
        
        # ⚠️ 重要：使用 isls_plus_grid + ENABLE_CHAOS_MONKEY 環境變量
        if python main_starlink_550.py $DURATION $TIME_STEP $ISL_TYPE $GS_TYPE $ALGORITHM $THREADS $GRID_DEG $K; then
            echo ""
            echo "   🔄 合併統計文件..."
            
            TEMP_DIR="analytic_result/temp_grhr_random_${LABEL}_k${K}"
            OUTPUT_FILE="analytic_result/hierarchical_gid_27deg_random_${LABEL}_k${K}_signaling_stats.json"
            
            cd ../..
            if [ -d "paper/satellite_networks_state/$TEMP_DIR" ]; then
                python3 merge_random_stats_simple.py "paper/satellite_networks_state/$TEMP_DIR" "paper/satellite_networks_state/$OUTPUT_FILE"
            else
                echo "   ⚠️  警告：臨時目錄不存在 $TEMP_DIR"
            fi
            cd paper/satellite_networks_state
            
            SCENARIO_END=$(date +%s)
            SCENARIO_DURATION=$((SCENARIO_END - SCENARIO_START))
            COMPLETED=$((COMPLETED + 1))
            
            echo "✅ 完成：$SCENARIO_NAME（耗時 ${SCENARIO_DURATION} 秒）"
            
            # 檢查 Chaos Monkey 日誌
            if [ -f "$LOG_FILE" ]; then
                INJECTION_COUNT=$(grep -c "\[CHAOS_MONKEY\]" "$LOG_FILE" || echo "0")
                echo "   Chaos Monkey 注入次數：${INJECTION_COUNT}"
                
                # 預期注入次數 = 100（200秒 / 2秒間隔）
                EXPECTED_INJECTIONS=100
                if [ "$INJECTION_COUNT" -ne "$EXPECTED_INJECTIONS" ]; then
                    echo "   ⚠️  警告：注入次數 ($INJECTION_COUNT) 不等於預期 ($EXPECTED_INJECTIONS)"
                fi
            else
                echo "   ⚠️  警告：Chaos Monkey 日誌未生成"
            fi
            
            # 檢查 JSON 輸出文件
            JSON_FILE="analytic_result/hierarchical_gid_27deg_random_${LABEL}_k${K}_signaling_stats.json"
            if [ -f "$JSON_FILE" ]; then
                echo "   ✅ JSON 文件已生成：${JSON_FILE}"
                # 檢查 JSON 格式（是否有 summary.by_type）
                if grep -q '"by_type"' "$JSON_FILE"; then
                    echo "   ✅ JSON 格式正確（包含 by_type）"
                else
                    echo "   ⚠️  警告：JSON 格式可能不正確（缺少 by_type）"
                fi
            else
                echo "   ❌ 錯誤：JSON 文件未生成"
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

# 返回到根目錄
cd /home/kun/ssd2t/Leo/kun_hypatia

# 生成摘要報告
SUMMARY_FILE="logs/grhr_dynamic_200s_summary_$(date +%Y%m%d_%H%M%S).txt"
echo "生成摘要報告：${SUMMARY_FILE}"

cat > "$SUMMARY_FILE" << EOF
========================================
GRHR 動態失效場景批次執行摘要
========================================
執行日期：$(date '+%Y-%m-%d %H:%M:%S')
星座：Starlink-550
時長：${DURATION} 秒
Time step：${TIME_STEP} ms
Chaos 間隔：每 2 秒
ISL Type：${ISL_TYPE} (+ ENABLE_CHAOS_MONKEY)
地面站：${GS_TYPE}
演算法：GRHR (Hierarchical Virtual GID)
Grid degree：${GRID_DEG}
執行緒：${THREADS}

場景數：${TOTAL}
完成數：${COMPLETED}
失敗數：${FAILED}
總耗時：${HOURS} 小時 ${MINUTES} 分鐘 ${SECONDS} 秒

失效率 & K 值組合：
  - P1 (1%): K=1,2,4,6,8,999
  - P5 (5%): K=1,2,4,6,8,999
  - P10 (10%): K=1,2,4,6,8,999

輸出文件位置：
  - JSON: paper/satellite_networks_state/analytic_result/hierarchical_gid_27deg_random_*.json
  - Logs: logs/chaos_grhr_*.log
  - Backup: paper/satellite_networks_state/analytic_result/BACKUP_random_*

注意事項：
  ✓ 已使用新的 control signaling 統計邏輯（by_type 格式）
  ✓ 已清理舊的 temp 目錄
  ✓ 已備份舊的 JSON 文件
  ✓ Chaos Monkey 每 2 秒觸發一次（每個 snapshot）
  ✓ 預期每個場景有 100 次 ISL 失效注入

下一步驟：
  1. 驗證 JSON 文件格式正確（包含 summary.by_type）
  2. 使用 analyze_dynamic_scenarios.py 生成分析圖表
  3. 與舊數據比較，確認控制信令統計邏輯修正的影響

========================================
EOF

echo "✅ 摘要報告已保存：${SUMMARY_FILE}"
echo ""

# 列出生成的 JSON 文件
echo "========================================"
echo "生成的 JSON 文件："
echo "========================================"
cd paper/satellite_networks_state/analytic_result
ls -lh hierarchical_gid_27deg_random_*.json | tail -20

echo ""
echo "========================================"
echo "Chaos Monkey 日誌文件："
echo "========================================"
cd /home/kun/ssd2t/Leo/kun_hypatia
ls -lh logs/chaos_grhr_*.log | tail -20

echo ""
echo "🎉 批次執行完成！"
echo "請檢查日誌和 JSON 文件確認執行結果。"
