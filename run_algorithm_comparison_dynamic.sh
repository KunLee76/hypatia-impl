#!/bin/bash
# ===================================================================================
# 演算法比較實驗：GRHR (K=4, K=8) vs LoHi vs Baseline
# 在動態 P1/P5/P10 ISL 失效場景下進行比較
# ===================================================================================

# 啟用 conda 環境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

# 設定工作目錄
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 共同參數
DURATION=200        # 200 秒模擬時間
TIME_STEP=2000      # 2000 毫秒 = 2 秒（與 Chaos Monkey 間隔一致）
GS_TYPE="ground_stations_top_100_with_hsinchu"
THREADS=4

# Chaos Monkey 參數
export CHAOS_INTERVAL_SNAPSHOTS=1  # 每 1 個快照（2秒）重新注入失效

# 清空 analytic_result 中可能衝突的臨時檔（可選）
echo "=============================================="
echo " 演算法比較實驗 - 動態 ISL 失效場景"
echo " GRHR (K=4, K=8) vs LoHi vs Baseline"
echo " 場景: P1 (1%), P5 (5%), P10 (10%)"
echo "=============================================="
echo ""

# ===================================================================================
# LoHi 演算法 (3 scenarios: P1, P5, P10)
# ===================================================================================
echo "========================================"
echo " [1/2] 執行 LoHi 演算法"
echo " 演算法: algorithm_lohi (p=6, s=10 固定分群)"
echo "========================================"

for FAILURE_RATE in 1 5 10; do
    echo ""
    echo "----------------------------------------"
    echo "  LoHi - Dynamic P${FAILURE_RATE} (${FAILURE_RATE}% 失效率)"
    echo "----------------------------------------"
    
    # 設定 Chaos Monkey 失效率
    export CHAOS_FAILURE_RATE=$(echo "scale=2; $FAILURE_RATE / 100" | bc)
    echo "  CHAOS_FAILURE_RATE = $CHAOS_FAILURE_RATE"
    echo "  CHAOS_INTERVAL_SNAPSHOTS = $CHAOS_INTERVAL_SNAPSHOTS"
    
    ISL_TYPE="isls_dynamic_p${FAILURE_RATE}"
    ALGORITHM="algorithm_lohi"
    
    echo "  ISL Type: $ISL_TYPE"
    echo "  Algorithm: $ALGORITHM"
    echo "  Duration: ${DURATION}s, Time Step: ${TIME_STEP}ms"
    echo ""
    echo "  開始執行..."
    
    python3 main_starlink_550.py \
        $DURATION \
        $TIME_STEP \
        $ISL_TYPE \
        $GS_TYPE \
        $ALGORITHM \
        $THREADS
    
    if [ $? -eq 0 ]; then
        echo "  ✓ LoHi P${FAILURE_RATE} 完成"
    else
        echo "  ✗ LoHi P${FAILURE_RATE} 失敗!"
        exit 1
    fi
done

echo ""
echo "========================================"
echo " LoHi 演算法完成 (3 scenarios)"
echo "========================================"
echo ""

# ===================================================================================
# Baseline 演算法 (3 scenarios: P1, P5, P10)
# ===================================================================================
echo "========================================"
echo " [2/2] 執行 Baseline 演算法"
echo " 演算法: algorithm_free_one_only_over_isls_with_stats (Floyd-Warshall)"
echo "========================================"

for FAILURE_RATE in 1 5 10; do
    echo ""
    echo "----------------------------------------"
    echo "  Baseline - Dynamic P${FAILURE_RATE} (${FAILURE_RATE}% 失效率)"
    echo "----------------------------------------"
    
    # 設定 Chaos Monkey 失效率
    export CHAOS_FAILURE_RATE=$(echo "scale=2; $FAILURE_RATE / 100" | bc)
    echo "  CHAOS_FAILURE_RATE = $CHAOS_FAILURE_RATE"
    echo "  CHAOS_INTERVAL_SNAPSHOTS = $CHAOS_INTERVAL_SNAPSHOTS"
    
    ISL_TYPE="isls_dynamic_p${FAILURE_RATE}"
    ALGORITHM="algorithm_free_one_only_over_isls_with_stats"
    
    echo "  ISL Type: $ISL_TYPE"
    echo "  Algorithm: $ALGORITHM"
    echo "  Duration: ${DURATION}s, Time Step: ${TIME_STEP}ms"
    echo ""
    echo "  開始執行..."
    
    python3 main_starlink_550.py \
        $DURATION \
        $TIME_STEP \
        $ISL_TYPE \
        $GS_TYPE \
        $ALGORITHM \
        $THREADS
    
    if [ $? -eq 0 ]; then
        echo "  ✓ Baseline P${FAILURE_RATE} 完成"
    else
        echo "  ✗ Baseline P${FAILURE_RATE} 失敗!"
        exit 1
    fi
done

echo ""
echo "========================================"
echo " Baseline 演算法完成 (3 scenarios)"
echo "========================================"
echo ""

# ===================================================================================
# 完成
# ===================================================================================
echo "=============================================="
echo " 所有實驗完成！"
echo "=============================================="
echo ""
echo " 執行統計："
echo "   - LoHi: 3 scenarios (P1, P5, P10)"
echo "   - Baseline: 3 scenarios (P1, P5, P10)"
echo "   - Total: 6 new scenarios"
echo ""
echo " 生成的目錄："
echo "   gen_data/starlink_550_isls_dynamic_p1_ground_stations_top_100_with_hsinchu_algorithm_lohi/"
echo "   gen_data/starlink_550_isls_dynamic_p5_ground_stations_top_100_with_hsinchu_algorithm_lohi/"
echo "   gen_data/starlink_550_isls_dynamic_p10_ground_stations_top_100_with_hsinchu_algorithm_lohi/"
echo "   gen_data/starlink_550_isls_dynamic_p1_ground_stations_top_100_with_hsinchu_algorithm_free_one_only_over_isls_with_stats/"
echo "   gen_data/starlink_550_isls_dynamic_p5_ground_stations_top_100_with_hsinchu_algorithm_free_one_only_over_isls_with_stats/"
echo "   gen_data/starlink_550_isls_dynamic_p10_ground_stations_top_100_with_hsinchu_algorithm_free_one_only_over_isls_with_stats/"
echo ""
echo " 統計臨時檔目錄："
echo "   analytic_result/temp_lohi_dynamic_p1/"
echo "   analytic_result/temp_lohi_dynamic_p5/"
echo "   analytic_result/temp_lohi_dynamic_p10/"
echo "   analytic_result/temp_baseline_dynamic_p1/"
echo "   analytic_result/temp_baseline_dynamic_p5/"
echo "   analytic_result/temp_baseline_dynamic_p10/"
echo ""
echo " 下一步：執行 merge_algorithm_comparison_dynamic.sh 合併統計數據"
