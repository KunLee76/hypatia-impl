#!/bin/bash
# 簡單測試：手動運行一次 Baseline P1 來看實際發生了什麼

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

export ENABLE_CHAOS_MONKEY=true
export CHAOS_FAILURE_RATE=0.01
export CHAOS_INTERVAL_SNAPSHOTS=20  
export CHAOS_LOG_FILE="test_chaos.log"

echo "環境變數:"
echo "  ENABLE_CHAOS_MONKEY = $ENABLE_CHAOS_MONKEY"
echo "  CHAOS_FAILURE_RATE = $CHAOS_FAILURE_RATE"
echo ""

# 清除舊文件
rm -f test_chaos.log
rm -rf analytic_result/temp_baseline*
rm -f analytic_result/baseline_signaling_stats.json

echo "運行 Baseline 模擬..."
python main_starlink_550.py \
    200 \
    2000 \
    isls_plus_grid \
    ground_stations_top_100_with_hsinchu \
    algorithm_free_one_only_over_isls_with_stats \
    4

echo ""
echo "檢查結果:"
echo ""

if [ -f "test_chaos.log" ]; then
    echo "✅ Chaos Monkey 日誌已生成"
    echo "   總行數: $(wc -l < test_chaos.log)"
else
    echo "❌ Chaos Monkey 日誌未生成"
fi

echo ""
echo "暫存目錄:"
ls -la analytic_result/ | grep temp_baseline

echo ""
echo "輸出文件:"
ls -la analytic_result/baseline*.json

echo ""
echo "如果看到 temp_baseline_dynamic_p1，則修復成功！"
