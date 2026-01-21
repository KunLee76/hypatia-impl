#!/bin/bash

# ISL 失效場景測試腳本（單一實驗）
# 用於驗證批次腳本邏輯是否正確

# 激活 conda 環境
source /home/kun/miniconda3/bin/activate kun_hypatia

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

echo "======================================================"
echo "ISL 失效場景測試實驗"
echo "======================================================"
echo ""
echo "測試配置："
echo "  時長: 20 秒（快速測試）"
echo "  時間步: 100 毫秒"
echo "  網格度數: 27°"
echo "  並行執行緒: 10"
echo "  測試場景: failure_l1 (輕度失效)"
echo "  測試 K 值: 1"
echo ""
echo "開始時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================"
echo ""

# 測試參數
SCENARIO="failure_l1"
K=1
ISL_PARAM="isls_${SCENARIO}"

echo "🚀 執行指令:"
echo "   python main_starlink_550.py 20 100 \\"
echo "     ${ISL_PARAM} \\"
echo "     ground_stations_top_100_with_hsinchu \\"
echo "     algorithm_hierarchical_virtual_gid 10 27 ${K}"
echo ""

# 記錄開始時間
START_TIME=$(date +%s)

# 執行
python main_starlink_550.py 20 100 \
    ${ISL_PARAM} \
    ground_stations_top_100_with_hsinchu \
    algorithm_hierarchical_virtual_gid 10 27 ${K}

EXIT_CODE=$?

# 計算執行時間
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "======================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 測試成功！耗時: ${MINUTES}分${SECONDS}秒"
    echo ""
    echo "生成的目錄："
    ls -d gen_data/starlink_550_isls_failure_l1_*_k${K}/ 2>/dev/null || echo "  (目錄未找到)"
    echo ""
    echo "✅ 驗證通過，可以運行完整批次實驗："
    echo "   bash run_failure_experiments.sh"
else
    echo "❌ 測試失敗！退出碼: ${EXIT_CODE}"
    echo ""
    echo "請檢查："
    echo "1. main_helper.py 的修改是否正確"
    echo "2. input_data/failure_scenarios/isls_failure_l1.txt 是否存在"
fi
echo "======================================================"
echo "結束時間: $(date '+%Y-%m-%d %H:%M:%S')"
