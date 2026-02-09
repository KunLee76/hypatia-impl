#!/bin/bash
# 重新運行 Baseline 和 LoHi 的動態失效場景（啟用 Chaos Monkey）
# 
# 用途：修復 Baseline 和 LoHi 沒有正確處理 ISL 失效的問題
# 
# 預期結果：
# - P1 (1% 失效): 比 Normal 略高的控制開銷
# - P5 (5% 失效): 中等增加的控制開銷
# - P10 (10% 失效): 顯著增加的控制開銷
#
# 重要參數：
# - 模擬時長：200 秒（與之前的 Normal 場景一致）
# - 時間步長：2000ms（與之前的 Normal 場景一致）
# - 輸出快照：100 個 (0, 20, 40, ..., 1980)

# 註釋: 不使用 set -e，這樣即使某個場景失敗也能繼續執行
# set -e  # 遇到錯誤立即退出

echo "======================================================================="
echo "重新運行 Baseline 和 LoHi 動態失效場景（啟用 Chaos Monkey）"
echo "======================================================================="
echo ""
echo "修復內容："
echo "  - 在 Baseline 算法中添加 Chaos Monkey ISL 失效注入"
echo "  - 在 LoHi 算法中添加 Chaos Monkey ISL 失效注入"
echo ""
echo "關鍵參數："
echo "  - 模擬時長：200 秒"
echo "  - 時間步長：2000ms"
echo "  - 快照數量：100 個"
echo "  - 多線程：4 個線程"
echo ""
echo "場景列表："
echo "  1. Baseline Dynamic P1 (1% ISL 失效)"
echo "  2. Baseline Dynamic P5 (5% ISL 失效)"
echo "  3. Baseline Dynamic P10 (10% ISL 失效)"
echo "  4. LoHi Dynamic P1 (1% ISL 失效)"
echo "  5. LoHi Dynamic P5 (5% ISL 失效)"
echo "  6. LoHi Dynamic P10 (10% ISL 失效)"
echo ""
echo "預估時間："
echo "  - 每個 Baseline 場景：~5 分鐘"
echo "  - 每個 LoHi 場景：~15 分鐘"
echo "  - 總計：~2 小時"
echo ""
echo "======================================================================="
echo ""

# 設置工作目錄
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/paper/satellite_networks_state"

# Conda 環境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

# 失效率配置
FAILURE_RATES=("0.01" "0.05" "0.10")
FAILURE_LABELS=("p1" "p5" "p10")

# 啟用 Chaos Monkey
export ENABLE_CHAOS_MONKEY=true
export CHAOS_INTERVAL_SNAPSHOTS=20  # 每 20 snapshots (2秒@100ms) 注入一次

echo "環境變數設置："
echo "  ENABLE_CHAOS_MONKEY = $ENABLE_CHAOS_MONKEY"
echo "  CHAOS_INTERVAL_SNAPSHOTS = $CHAOS_INTERVAL_SNAPSHOTS"
echo ""

# ========================================
# Baseline 場景（Floyd-Warshall）
# ========================================
echo "======================================================================="
echo "Part 1/2: Baseline 動態失效場景"
echo "======================================================================="

for i in "${!FAILURE_RATES[@]}"; do
    RATE="${FAILURE_RATES[$i]}"
    LABEL="${FAILURE_LABELS[$i]}"
    
    echo ""
    echo "-----------------------------------------------------------------------"
    echo "場景 $((i+1))/3: Baseline Dynamic ${LABEL^^} (失效率 $RATE)"
    echo "-----------------------------------------------------------------------"
    
    export CHAOS_FAILURE_RATE=$RATE
    export CHAOS_LOG_FILE="chaos_monkey_baseline_${LABEL}.log"
    
    echo "  失效率: $RATE (${LABEL})"
    echo "  日誌文件: $CHAOS_LOG_FILE"
    echo "  開始時間: $(date '+%Y-%m-%d %H:%M:%S')"
    
    # 清除舊的暫存目錄和日誌文件
    TEMP_DIR="analytic_result/temp_baseline_dynamic_${LABEL}"
    rm -rf "$TEMP_DIR"
    rm -f "$CHAOS_LOG_FILE"
    
    # 運行模擬（200秒，2000ms時間步長）
    python main_starlink_550.py \
        200 \
        2000 \
        isls_plus_grid \
        ground_stations_top_100_with_hsinchu \
        algorithm_free_one_only_over_isls_with_stats \
        4
    
    # 檢查暫存目錄是否存在
    if [ -d "$TEMP_DIR" ]; then
        echo "  > 找到暫存目錄: $TEMP_DIR"
        NUM_TEMP_FILES=$(ls -1 "$TEMP_DIR"/*.json 2>/dev/null | wc -l)
        echo "  > 暫存文件數量: $NUM_TEMP_FILES"
        
        # 合併暫存文件
        echo "  > 合併暫存文件..."
        python3 "$SCRIPT_DIR/merge_baseline_dynamic.py" "$LABEL"
        
        OUTPUT_FILE="analytic_result/baseline_dynamic_${LABEL}_signaling_stats.json"
        if [ -f "$OUTPUT_FILE" ]; then
            echo "  ✅ 完成: $OUTPUT_FILE"
        else
            echo "  ❌ 錯誤: 合併後的輸出文件未生成"
            exit 1
        fi
    else
        echo "  ⚠️  警告: 未找到暫存目錄 $TEMP_DIR"
        # 嘗試直接使用輸出文件
        if [ -f "analytic_result/baseline_signaling_stats.json" ]; then
            OUTPUT_FILE="analytic_result/baseline_dynamic_${LABEL}_signaling_stats.json"
            mv "analytic_result/baseline_signaling_stats.json" "$OUTPUT_FILE"
            echo "  ✅ 完成: $OUTPUT_FILE"
        else
            echo "  ❌ 錯誤: 輸出文件未生成，跳過此場景"
            continue  # 繼續下一個場景而不是退出
        fi
    fi
    
    # 移動日誌文件
    if [ -f "$CHAOS_LOG_FILE" ]; then
        mv "$CHAOS_LOG_FILE" "analytic_result/chaos_monkey_baseline_${LABEL}.log"
        echo "  ✅ Chaos Monkey 日誌: analytic_result/chaos_monkey_baseline_${LABEL}.log"
    fi
    
    echo "  結束時間: $(date '+%Y-%m-%d %H:%M:%S')"
done

# ========================================
# LoHi 場景（p=6, s=10）
# ========================================
echo ""
echo "======================================================================="
echo "Part 2/2: LoHi 動態失效場景"
echo "======================================================================="

for i in "${!FAILURE_RATES[@]}"; do
    RATE="${FAILURE_RATES[$i]}"
    LABEL="${FAILURE_LABELS[$i]}"
    
    echo ""
    echo "-----------------------------------------------------------------------"
    echo "場景 $((i+4))/6: LoHi Dynamic ${LABEL^^} (失效率 $RATE)"
    echo "-----------------------------------------------------------------------"
    
    export CHAOS_FAILURE_RATE=$RATE
    export CHAOS_LOG_FILE="chaos_monkey_lohi_${LABEL}.log"
    
    echo "  失效率: $RATE (${LABEL})"
    echo "  日誌文件: $CHAOS_LOG_FILE"
    echo "  開始時間: $(date '+%Y-%m-%d %H:%M:%S')"
    
    # 清除舊的暫存目錄和日誌文件
    TEMP_DIR="analytic_result/temp_lohi_dynamic_${LABEL}"
    rm -rf "$TEMP_DIR"
    rm -f "$CHAOS_LOG_FILE"
    
    # 運行模擬（200秒，2000ms時間步長）
    python main_starlink_550.py \
        200 \
        2000 \
        isls_plus_grid \
        ground_stations_top_100_with_hsinchu \
        algorithm_lohi \
        4
    
    # 檢查暫存目錄是否存在
    if [ -d "$TEMP_DIR" ]; then
        echo "  > 找到暫存目錄: $TEMP_DIR"
        NUM_TEMP_FILES=$(ls -1 "$TEMP_DIR"/*.json 2>/dev/null | wc -l)
        echo "  > 暫存文件數量: $NUM_TEMP_FILES"
        
        # 合併暫存文件
        echo "  > 合併暫存文件..."
        python3 "$SCRIPT_DIR/merge_lohi_dynamic.py" "$LABEL"
        
        OUTPUT_FILE="analytic_result/lohi_dynamic_${LABEL}_signaling_stats.json"
        if [ -f "$OUTPUT_FILE" ]; then
            echo "  ✅ 完成: $OUTPUT_FILE"
        else
            echo "  ❌ 錯誤: 合併後的輸出文件未生成"
            exit 1
        fi
    else
        echo "  ⚠️  警告: 未找到暫存目錄 $TEMP_DIR"
        # 嘗試直接使用輸出文件
        if [ -f "analytic_result/lohi_signaling_stats.json" ]; then
            OUTPUT_FILE="analytic_result/lohi_dynamic_${LABEL}_signaling_stats.json"
            mv "analytic_result/lohi_signaling_stats.json" "$OUTPUT_FILE"
            echo "  ✅ 完成: $OUTPUT_FILE"
        else
            echo "  ❌ 錯誤: 輸出文件未生成，跳過此場景"
            continue  # 繼續下一個場景而不是退出
        fi
    fi
    
    # 移動日誌文件
    if [ -f "$CHAOS_LOG_FILE" ]; then
        mv "$CHAOS_LOG_FILE" "analytic_result/chaos_monkey_lohi_${LABEL}.log"
        echo "  ✅ Chaos Monkey 日誌: analytic_result/chaos_monkey_lohi_${LABEL}.log"
    fi
    
    echo "  結束時間: $(date '+%Y-%m-%d %H:%M:%S')"
done

echo ""
echo "======================================================================="
echo "所有場景完成！"
echo "======================================================================="
echo ""
echo "輸出文件："
echo "  - analytic_result/baseline_dynamic_p1_signaling_stats.json"
echo "  - analytic_result/baseline_dynamic_p5_signaling_stats.json"
echo "  - analytic_result/baseline_dynamic_p10_signaling_stats.json"
echo "  - analytic_result/lohi_dynamic_p1_signaling_stats.json"
echo "  - analytic_result/lohi_dynamic_p5_signaling_stats.json"
echo "  - analytic_result/lohi_dynamic_p10_signaling_stats.json"
echo ""
echo "Chaos Monkey 日誌："
echo "  - analytic_result/chaos_monkey_baseline_p*.log"
echo "  - analytic_result/chaos_monkey_lohi_p*.log"
echo ""
echo "下一步："
echo "  1. 驗證數據正確性："
echo "     python3 ../../compare_changed_entries.py"
echo ""
echo "  2. 重新生成比較報告："
echo "     python3 ../../analyze_algorithm_comparison_dynamic.py"
echo ""
echo "預期結果："
echo "  - Baseline/LoHi 的控制開銷應隨失效率增加"
echo "  - P1 < P5 < P10 (changed_entries 應呈遞增趨勢)"
echo ""
