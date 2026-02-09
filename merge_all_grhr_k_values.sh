#!/bin/bash
# 合併所有 K 值的 temp 文件
# 需要先執行 rerun_grhr_k_values.sh 完成模擬

set -e

cd /home/kun/ssd2t/Leo/kun_hypatia

K_VALUES=(1 2 4 6 8 999)

echo "=========================================="
echo "合併所有 K 值的 temp 文件"
echo "=========================================="
echo ""

# 檢查 temp 目錄是否存在
echo "檢查 temp 目錄..."
for K in "${K_VALUES[@]}"; do
    TEMP_DIR="paper/satellite_networks_state/analytic_result/temp_grhr_k${K}"
    if [ ! -d "$TEMP_DIR" ]; then
        echo "❌ 錯誤: $TEMP_DIR 不存在"
        echo "請先執行 rerun_grhr_k_values.sh"
        exit 1
    fi
    
    FILE_COUNT=$(ls -1 "$TEMP_DIR"/grhr_stats_pid*_tid*.json 2>/dev/null | wc -l)
    echo "  K=${K}: 找到 ${FILE_COUNT} 個 temp 文件"
    
    if [ $FILE_COUNT -eq 0 ]; then
        echo "❌ 錯誤: K=${K} 沒有找到 temp 文件"
        exit 1
    fi
done

echo ""
echo "開始合併..."
echo ""

for K in "${K_VALUES[@]}"; do
    echo "=========================================="
    echo "合併 K=${K}"
    echo "=========================================="
    
    python3 merge_grhr_k_value.py ${K}
    
    if [ $? -eq 0 ]; then
        echo "✓ K=${K} 合併成功"
    else
        echo "❌ K=${K} 合併失敗"
        exit 1
    fi
    echo ""
done

echo "=========================================="
echo "全部合併完成！"
echo "=========================================="
echo ""
echo "生成的文件:"
for K in "${K_VALUES[@]}"; do
    FILE="paper/satellite_networks_state/analytic_result/hierarchical_gid_27deg_k${K}_signaling_stats.json"
    if [ -f "$FILE" ]; then
        SIZE=$(ls -lh "$FILE" | awk '{print $5}')
        echo "  ✓ hierarchical_gid_27deg_k${K}_signaling_stats.json (${SIZE})"
    else
        echo "  ❌ hierarchical_gid_27deg_k${K}_signaling_stats.json (不存在)"
    fi
done

echo ""
echo "執行驗證腳本..."
python3 grhr_data_quality_check.py

echo ""
echo "完成！可以檢查 K 值分析報告是否正確。"
