#!/bin/bash
# 批次執行所有 K 值的 baseline 實驗
# 配置: 200秒, 2000ms步長, Grid=27°

set -e  # 遇到錯誤立即停止

# 清除失效場景相關的環境變數
unset CHAOS_FAILURE_RATE
unset CHAOS_LOG_FILE

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

echo "=================================================="
echo "重新運行 K 參數實驗 (K=1,2,4,6,8,999)"
echo "配置: 200秒, 2000ms步長, Grid=27° [BASELINE - 無失效]"
echo "=================================================="
echo ""

# K 值列表
K_VALUES=(1 2 4 6 8 999)

# 記錄開始時間
SCRIPT_START=$(date +%s)

# 清理所有舊的 temp 目錄
echo "清理舊的 temp 目錄..."
cd analytic_result
for K in "${K_VALUES[@]}"; do
    if [ -d "temp_grhr_k${K}" ]; then
        rm -rf "temp_grhr_k${K}"
        echo "  ✓ 清理 temp_grhr_k${K}/"
    fi
done
cd ..
echo ""

for K in "${K_VALUES[@]}"; do
    echo "=========================================="
    echo "運行 K=$K 實驗..."
    echo "開始時間: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    
    START_TIME=$(date +%s)
    
    python main_starlink_550.py 200 2000 isls_plus_grid ground_stations_top_100_with_hsinchu algorithm_hierarchical_virtual_gid 10 27 $K
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    if [ $? -eq 0 ]; then
        echo "✓ K=$K 完成！耗時: ${DURATION}秒"
    else
        echo "✗ K=$K 失敗！"
        exit 1
    fi
    
    echo ""
done

# 計算總耗時
SCRIPT_END=$(date +%s)
TOTAL_DURATION=$((SCRIPT_END - SCRIPT_START))
HOURS=$((TOTAL_DURATION / 3600))
MINUTES=$(((TOTAL_DURATION % 3600) / 60))
SECONDS=$((TOTAL_DURATION % 60))

echo "=================================================="
echo "所有實驗完成！"
echo "完成時間: $(date '+%Y-%m-%d %H:%M:%S')"
printf "總耗時: %02d:%02d:%02d\n" ${HOURS} ${MINUTES} ${SECONDS}
echo "=================================================="
echo ""
echo "生成的文件："
cd analytic_result
ls -lh hierarchical_gid_27deg_k*_signaling_stats.json | grep -v BACKUP | tail -6
echo ""
echo "[下一步] 執行分析與圖表生成："
echo "  cd /home/kun/ssd2t/Leo/kun_hypatia"
echo "  python analyze_k_parameter.py"
