#!/bin/bash
# ===================================================================================
# 合併 LoHi 和 Baseline 的動態場景統計數據
# ===================================================================================

cd /home/kun/ssd2t/Leo/kun_hypatia

echo "=============================================="
echo " 合併演算法比較實驗的統計數據"
echo "=============================================="
echo ""

ANALYTIC_DIR="paper/satellite_networks_state/analytic_result"

# ===================================================================================
# 合併 LoHi 統計數據
# ===================================================================================
echo "========================================"
echo " [1/2] 合併 LoHi 統計數據"
echo "========================================"

for P in 1 5 10; do
    TEMP_DIR="${ANALYTIC_DIR}/temp_lohi_dynamic_p${P}"
    OUTPUT_FILE="${ANALYTIC_DIR}/lohi_dynamic_p${P}_signaling_stats.json"
    
    echo ""
    echo "  處理: temp_lohi_dynamic_p${P}"
    
    if [ -d "$TEMP_DIR" ]; then
        FILE_COUNT=$(ls -1 "$TEMP_DIR"/*.json 2>/dev/null | wc -l)
        echo "    找到 ${FILE_COUNT} 個臨時 JSON 檔案"
        
        if [ $FILE_COUNT -gt 0 ]; then
            echo "    合併到: $OUTPUT_FILE"
            python3 merge_signaling_stats.py "$TEMP_DIR" "$OUTPUT_FILE"
            
            if [ $? -eq 0 ]; then
                echo "    ✓ LoHi P${P} 合併完成"
            else
                echo "    ✗ LoHi P${P} 合併失敗!"
            fi
        else
            echo "    ⚠ 沒有找到 JSON 檔案，跳過"
        fi
    else
        echo "    ⚠ 目錄不存在: $TEMP_DIR"
    fi
done

echo ""
echo "========================================"
echo " LoHi 合併完成"
echo "========================================"
echo ""

# ===================================================================================
# 合併 Baseline 統計數據
# ===================================================================================
echo "========================================"
echo " [2/2] 合併 Baseline 統計數據"
echo "========================================"

for P in 1 5 10; do
    TEMP_DIR="${ANALYTIC_DIR}/temp_baseline_dynamic_p${P}"
    OUTPUT_FILE="${ANALYTIC_DIR}/baseline_dynamic_p${P}_signaling_stats.json"
    
    echo ""
    echo "  處理: temp_baseline_dynamic_p${P}"
    
    if [ -d "$TEMP_DIR" ]; then
        FILE_COUNT=$(ls -1 "$TEMP_DIR"/*.json 2>/dev/null | wc -l)
        echo "    找到 ${FILE_COUNT} 個臨時 JSON 檔案"
        
        if [ $FILE_COUNT -gt 0 ]; then
            echo "    合併到: $OUTPUT_FILE"
            python3 merge_signaling_stats.py "$TEMP_DIR" "$OUTPUT_FILE"
            
            if [ $? -eq 0 ]; then
                echo "    ✓ Baseline P${P} 合併完成"
            else
                echo "    ✗ Baseline P${P} 合併失敗!"
            fi
        else
            echo "    ⚠ 沒有找到 JSON 檔案，跳過"
        fi
    else
        echo "    ⚠ 目錄不存在: $TEMP_DIR"
    fi
done

echo ""
echo "========================================"
echo " Baseline 合併完成"
echo "========================================"
echo ""

# ===================================================================================
# 顯示結果
# ===================================================================================
echo "=============================================="
echo " 統計檔案清單"
echo "=============================================="
echo ""

echo "LoHi:"
ls -la ${ANALYTIC_DIR}/lohi_dynamic_p*_signaling_stats.json 2>/dev/null || echo "  (無檔案)"

echo ""
echo "Baseline:"
ls -la ${ANALYTIC_DIR}/baseline_dynamic_p*_signaling_stats.json 2>/dev/null || echo "  (無檔案)"

echo ""
echo "GRHR (已存在):"
ls -la ${ANALYTIC_DIR}/hierarchical_gid_27deg_dynamic_p*_k*_signaling_stats.json 2>/dev/null || echo "  (無檔案)"

echo ""
echo "=============================================="
echo " 合併完成！"
echo "=============================================="
echo ""
echo " 下一步：執行 analyze_algorithm_comparison_dynamic.py 生成比較圖表"
