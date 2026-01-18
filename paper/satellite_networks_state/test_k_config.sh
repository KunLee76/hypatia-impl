#!/bin/bash
# ========================================
# 快速測試 K 參數配置（不實際運行）
# ========================================

set -e

DURATION_S=20
TIME_STEP_MS=100
ISL_TYPE="isls_plus_grid"
GS_TYPE="ground_stations_top_100_with_hsinchu"
ALGORITHM="algorithm_hierarchical_virtual_gid"
NUM_THREADS=10
GRID_DEG=27
K_VALUES=(1 2 4 6 999)

echo "=========================================="
echo "  K_BEST_GATEWAYS 參數配置驗證"
echo "=========================================="
echo ""
echo "將要執行的命令："
echo ""

for K in "${K_VALUES[@]}"; do
    CMD="python main_starlink_550.py ${DURATION_S} ${TIME_STEP_MS} ${ISL_TYPE} ${GS_TYPE} ${ALGORITHM} ${NUM_THREADS} ${GRID_DEG} ${K}"
    echo "K=${K}:"
    echo "  ${CMD}"
    echo ""
    
    OUTPUT_DIR="gen_data/starlink_550_${ISL_TYPE}_${GS_TYPE}_${ALGORITHM}_${GRID_DEG}deg_k${K}"
    echo "  輸出目錄：${OUTPUT_DIR}"
    
    if [ -d "${OUTPUT_DIR}" ]; then
        echo "  狀態：✓ 目錄已存在（將被覆蓋）"
    else
        echo "  狀態：○ 目錄不存在（將新建）"
    fi
    echo ""
done

echo "=========================================="
echo "預估資訊："
echo "  - 測試數量：${#K_VALUES[@]} 個"
echo "  - 每個測試時長：約 3-5 分鐘（取決於機器性能）"
echo "  - 總預估時長：約 15-25 分鐘"
echo "=========================================="
echo ""
echo "確認配置無誤後，執行："
echo "  ./run_k_experiments.sh"
echo ""
