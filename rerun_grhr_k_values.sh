#!/bin/bash
# 重跑 GRHR Normal 場景的 6 個 K 值（只執行模擬）
# 模擬完成後，使用 merge_all_grhr_k_values.sh 進行合併

set -e  # 遇到錯誤立即停止

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 激活 conda 環境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

# K 值列表
K_VALUES=(1 2 4 6 8 999)

echo "=========================================="
echo "開始重跑 GRHR Normal 場景 (6 個 K 值)"
echo "=========================================="
echo "預計總時間: 54-60 分鐘"
echo ""

TOTAL_START=$(date +%s)

for K in "${K_VALUES[@]}"; do
    echo "=========================================="
    echo "開始執行: K=${K}"
    echo "=========================================="
    echo "指令: python main_starlink_550.py 200 2000 isls_plus_grid ground_stations_top_100_with_hsinchu algorithm_hierarchical_virtual_gid 4 27 ${K}"
    echo ""
    
    # 記錄開始時間
    START_TIME=$(date +%s)
    
    # 執行模擬
    python main_starlink_550.py 200 2000 isls_plus_grid \
        ground_stations_top_100_with_hsinchu \
        algorithm_hierarchical_virtual_gid \
        4 27 ${K}
    
    # 記錄結束時間
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    MINUTES=$((DURATION / 60))
    SECONDS=$((DURATION % 60))
    
    echo ""
    echo "✓ K=${K} 模擬完成 (耗時: ${MINUTES}分${SECONDS}秒)"
    echo ""
done

TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))
TOTAL_MINUTES=$((TOTAL_DURATION / 60))

echo "=========================================="
echo "全部模擬完成！"
echo "=========================================="
echo "總耗時: ${TOTAL_MINUTES} 分鐘"
echo ""
echo "生成的 temp 目錄:"
for K in "${K_VALUES[@]}"; do
    echo "  • temp_grhr_k${K}/"
done
echo ""
echo "下一步:"
echo "  1. 檢查 temp 文件: cd analytic_result && ls -lh temp_grhr_k*/"
echo "  2. 執行合併腳本: cd /home/kun/ssd2t/Leo/kun_hypatia && ./merge_all_grhr_k_values.sh"
