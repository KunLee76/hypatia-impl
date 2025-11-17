#!/bin/bash
# OneWeb 星座 LoHi 測試腳本

set -e  # Exit on error

echo "======================================================================"
echo "OneWeb 星座 LoHi 演算法測試"
echo "======================================================================"
echo ""

# 配置參數
DURATION=20  # 20 秒
TIME_STEP=100  # 100 ms
ISL_TYPE="isls_plus_grid"
GS_TYPE="ground_stations_top_100"
ALGORITHM="algorithm_lohi"
THREADS=4

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
STATE_DIR="${SCRIPT_DIR}/paper/satellite_networks_state"
OUTPUT_DIR="${STATE_DIR}/gen_data/oneweb_1200_${ISL_TYPE}_${GS_TYPE}_${ALGORITHM}"

echo "【測試配置】"
echo "  星座: OneWeb (18 planes × 40 sats = 720 satellites)"
echo "  軌道傾角: 87.9° (Polar orbit)"
echo "  軌道高度: 1,200 km"
echo "  模擬時長: ${DURATION} 秒"
echo "  時間步長: ${TIME_STEP} ms"
echo "  演算法: LoHi (p=6, s=10)"
echo "  執行緒數: ${THREADS}"
echo ""

echo "【預期結果】"
echo "  ✅ Loops: 0%"
echo "  ✅ Cross-PID ISL: ~13.3%"
echo "  ✅ PID 數量: 12"
echo "  ✅ 完美整除: 18÷6=3, 40÷10=4"
echo ""

# 檢查檔案
if [ ! -f "${STATE_DIR}/main_oneweb_1200.py" ]; then
    echo "❌ 錯誤: main_oneweb_1200.py 不存在"
    echo "   請確認檔案位置: ${STATE_DIR}/main_oneweb_1200.py"
    exit 1
fi

echo "======================================================================"
echo "Step 1: 產生 OneWeb 衛星網路狀態"
echo "======================================================================"
echo ""

cd "${STATE_DIR}"

echo "執行指令:"
echo "  python main_oneweb_1200.py ${DURATION} ${TIME_STEP} ${ISL_TYPE} ${GS_TYPE} ${ALGORITHM} ${THREADS}"
echo ""

START_TIME=$(date +%s)

python main_oneweb_1200.py ${DURATION} ${TIME_STEP} ${ISL_TYPE} ${GS_TYPE} ${ALGORITHM} ${THREADS}

END_TIME=$(date +%s)
DURATION_SEC=$((END_TIME - START_TIME))
DURATION_MIN=$((DURATION_SEC / 60))
DURATION_SEC_REM=$((DURATION_SEC % 60))

echo ""
echo "✅ 完成！執行時間: ${DURATION_MIN}m${DURATION_SEC_REM}s"
echo ""

# 檢查輸出
if [ -d "${OUTPUT_DIR}" ]; then
    echo "======================================================================"
    echo "Step 2: 檢查輸出檔案"
    echo "======================================================================"
    echo ""
    echo "輸出目錄: ${OUTPUT_DIR}"
    echo ""
    
    # 統計檔案
    if [ -f "${OUTPUT_DIR}/fstate/fstate_0.txt" ]; then
        echo "✅ Forwarding state 檔案已產生"
        NUM_FSTATE=$(ls -1 "${OUTPUT_DIR}/fstate/" | wc -l)
        echo "   - 總數: ${NUM_FSTATE} 個時間點"
    fi
    
    if [ -f "${OUTPUT_DIR}/logs/lohi_log_0.txt" ]; then
        echo "✅ LoHi log 檔案已產生"
        
        # 檢查 loops
        echo ""
        echo "【Loops 檢查】"
        if grep -q "Loop detected" "${OUTPUT_DIR}/logs/lohi_log_0.txt"; then
            LOOP_COUNT=$(grep -c "Loop detected" "${OUTPUT_DIR}/logs/lohi_log_0.txt")
            echo "   ⚠️  發現 ${LOOP_COUNT} 個 loops"
        else
            echo "   ✅ 0 loops (完美!)"
        fi
    fi
    
    echo ""
    echo "======================================================================"
    echo "Step 3: 分析建議"
    echo "======================================================================"
    echo ""
    
    echo "【路徑分析】"
    echo "  cd ${SCRIPT_DIR}/satgenpy"
    echo "  python -m satgen.post_analysis.main_print_graphical_routes_and_rtt \\"
    echo "    ../paper/satgenpy_analysis/data \\"
    echo "    ../paper/satellite_networks_state/${OUTPUT_DIR##*/} \\"
    echo "    100 ${DURATION} 720 729"
    echo ""
    
    echo "【ISL 拓撲分析】"
    echo "  建立類似 analyze_isl_topology.py 的分析腳本"
    echo "  分析 OneWeb 的 Cross-PID ISL 分布"
    echo "  驗證是否為理論值 13.3%"
    echo ""
    
    echo "【比較 Starlink 550】"
    echo "  - OneWeb: 720 sats, 12 PIDs, 13.3% Cross-PID ISL, Polar"
    echo "  - Starlink 550: 1584 sats, 36 PIDs, 14.6% Cross-PID ISL, Inclined"
    echo "  - 兩者 loops 應該都是 0%"
    echo ""
    
else
    echo "❌ 錯誤: 輸出目錄不存在"
    echo "   預期位置: ${OUTPUT_DIR}"
    exit 1
fi

echo "======================================================================"
echo "測試完成！"
echo "======================================================================"
echo ""
echo "下一步:"
echo "  1. 執行路徑分析（上述指令）"
echo "  2. 建立 OneWeb ISL 拓撲分析腳本"
echo "  3. 比較 OneWeb vs Starlink 550 結果"
echo "  4. 撰寫論文章節"
echo ""
