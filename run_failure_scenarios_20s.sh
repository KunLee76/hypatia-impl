#!/bin/bash
# ISL Failure 場景實驗腳本（30個實驗：5 scenarios × 6 K values）
# 參數：20s 模擬時間，100ms 時間步

set -e

# 激活 conda 環境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

echo "========================================"
echo "ISL Failure 場景實驗（20s，100ms 時間步）"
echo "========================================"
echo ""

# 配置參數
DURATION=20
TIME_STEP_MS=100
GRID_DEG=27

# 定義 K 值範圍
K_VALUES=(1 2 4 6 8 999)

# 定義失效場景（包含 baseline）
SCENARIOS=(
    "baseline:0"
    "l1:1"
    "l2:2"
    "l3:3"
    "l4:4"
)

# 統計實驗總數
TOTAL_EXPERIMENTS=$((${#SCENARIOS[@]} * ${#K_VALUES[@]}))
CURRENT=0

echo "總共 ${TOTAL_EXPERIMENTS} 個實驗（${#SCENARIOS[@]} scenarios × ${#K_VALUES[@]} K values）"
echo "每個實驗：${DURATION}s 模擬，${TIME_STEP_MS}ms 時間步（200 snapshots）"
echo ""

# 遍歷所有場景和 K 值組合
for scenario_pair in "${SCENARIOS[@]}"; do
    # 分割場景名稱和 ISL 數量
    IFS=':' read -r scenario_name isl_num <<< "$scenario_pair"
    
    for K in "${K_VALUES[@]}"; do
        CURRENT=$((CURRENT + 1))
        
        echo "========================================="
        echo "實驗 ${CURRENT}/${TOTAL_EXPERIMENTS}: Scenario=${scenario_name}, K=${K}"
        echo "========================================="
        
        # 根據場景選擇輸出目錄
        if [ "$scenario_name" = "baseline" ]; then
            OUTPUT_DIR="paper/satellite_networks_state/gen_data/starlink_550_${GRID_DEG}deg_k${K}"
            ISL_PARAM="isls_plus_grid"
            echo "  類型：Baseline (無 ISL 失效)"
        else
            OUTPUT_DIR="paper/satellite_networks_state/gen_data/starlink_550_isls_failure_${scenario_name}_${GRID_DEG}deg_k${K}"
            ISL_PARAM="isls_failure_${scenario_name}"
            echo "  類型：ISL Failure (${isl_num} ISLs)"
        fi
        
        echo "  K 值：${K}"
        echo "  ISL 參數：${ISL_PARAM}"
        echo "  輸出目錄：${OUTPUT_DIR}"
        echo "  時間：${DURATION}s，時間步：${TIME_STEP_MS}ms"
        echo ""
        
        # 清理舊數據
        if [ -d "$OUTPUT_DIR" ]; then
            echo "  清理舊數據..."
            rm -rf "$OUTPUT_DIR"
        fi
        
        # 運行實驗
        echo "  開始運行..."
        START_TIME=$(date +%s)
        
        cd paper/satellite_networks_state
        python main_starlink_550.py \
            "${DURATION}" \
            "${TIME_STEP_MS}" \
            "${ISL_PARAM}" \
            "ground_stations_top_100_with_hsinchu" \
            "algorithm_hierarchical_virtual_gid" \
            10 \
            "${GRID_DEG}" \
            "${K}" 2>&1 | tee "../../logs/failure_${scenario_name}_k${K}_$(date +%Y%m%d_%H%M%S).log"
        cd ../..
        
        END_TIME=$(date +%s)
        ELAPSED=$((END_TIME - START_TIME))
        
        echo ""
        echo "  ✓ 完成！耗時：${ELAPSED} 秒"
        echo ""
        
        # 檢查臨時統計文件
        if [ "$scenario_name" = "baseline" ]; then
            TEMP_DIR="paper/satellite_networks_state/analytic_result/temp_grhr_k${K}"
        else
            TEMP_DIR="paper/satellite_networks_state/analytic_result/temp_grhr_failure_${scenario_name}_k${K}"
        fi
        
        if [ -d "$TEMP_DIR" ]; then
            TEMP_FILES=$(ls "$TEMP_DIR"/*.json 2>/dev/null | wc -l)
            echo "  臨時統計文件：${TEMP_DIR} (${TEMP_FILES} 個文件)"
        else
            echo "  ⚠️ 警告：臨時統計目錄不存在：${TEMP_DIR}"
        fi
        
        echo ""
        sleep 2
    done
done

echo ""
echo "========================================"
echo "所有實驗完成！"
echo "========================================"
echo ""
echo "下一步："
echo "1. 使用 merge_signaling_stats.py 合併統計文件"
echo "2. 運行 analyze_failure_scenarios.py 生成分析圖表"
echo ""
