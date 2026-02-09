#!/bin/bash
# 快速測試：驗證 Chaos Monkey 是否正確工作
# 只運行 20 秒的模擬來快速驗證

set -e

echo "======================================================================="
echo "快速測試：Chaos Monkey 整合驗證"
echo "======================================================================="
echo ""

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

# 啟用 Chaos Monkey
export ENABLE_CHAOS_MONKEY=true
export CHAOS_FAILURE_RATE=0.05  # 5% 失效率
export CHAOS_INTERVAL_SNAPSHOTS=20
export CHAOS_LOG_FILE="chaos_monkey_test.log"

echo "測試參數："
echo "  模擬時長: 20 秒 (10 snapshots @ 2000ms)"
echo "  時間步長: 2000ms"
echo "  失效率: 5%"
echo "  注入間隔: 每 20 snapshots"
echo ""
echo "注意：這只是快速測試，正式運行會用 200 秒"
echo ""

# 清除舊日誌
rm -f "$CHAOS_LOG_FILE"

echo "-----------------------------------------------------------------------"
echo "測試 1/2: Baseline 算法"
echo "-----------------------------------------------------------------------"
echo "開始時間: $(date '+%Y-%m-%d %H:%M:%S')"

python main_starlink_550.py \
    20 \
    2000 \
    isls_plus_grid \
    ground_stations_top_100_with_hsinchu \
    algorithm_free_one_only_over_isls_with_stats \
    4 > /dev/null 2>&1

if [ -f "$CHAOS_LOG_FILE" ]; then
    echo "✅ Baseline Chaos Monkey 日誌已生成"
    echo ""
    cat "$CHAOS_LOG_FILE"
    mv "$CHAOS_LOG_FILE" "chaos_monkey_baseline_test.log"
else
    echo "❌ Baseline Chaos Monkey 日誌未生成 - 可能失敗"
fi

# 檢查統計文件
if [ -f "analytic_result/baseline_signaling_stats.json" ]; then
    echo ""
    echo "檢查 Baseline 統計數據："
    python3 << 'EOF'
import json
with open('analytic_result/baseline_signaling_stats.json', 'r') as f:
    data = json.load(f)
events = data['timeline']
print(f"  總事件數: {len(events)}")
print(f"  事件類型: {set(e['event'] for e in events)}")
# 檢查是否有 topology_change 事件
topo_changes = [e for e in events if e['event'] == 'topology_change']
print(f"  topology_change 事件: {len(topo_changes)}")
if len(topo_changes) > 0:
    print("  ✅ Baseline 正確偵測到拓撲變化！")
else:
    print("  ⚠️  Baseline 沒有偵測到拓撲變化")
EOF
    mv "analytic_result/baseline_signaling_stats.json" "analytic_result/baseline_test.json"
fi

echo ""
echo "-----------------------------------------------------------------------"
echo "測試 2/2: LoHi 算法"
echo "-----------------------------------------------------------------------"
echo "開始時間: $(date '+%Y-%m-%d %H:%M:%S')"

export CHAOS_LOG_FILE="chaos_monkey_test.log"
rm -f "$CHAOS_LOG_FILE"

python main_starlink_550.py \
    20 \
    2000 \
    isls_plus_grid \
    ground_stations_top_100_with_hsinchu \
    algorithm_lohi \
    4 > /dev/null 2>&1

if [ -f "$CHAOS_LOG_FILE" ]; then
    echo "✅ LoHi Chaos Monkey 日誌已生成"
    echo ""
    cat "$CHAOS_LOG_FILE"
    mv "$CHAOS_LOG_FILE" "chaos_monkey_lohi_test.log"
else
    echo "❌ LoHi Chaos Monkey 日誌未生成 - 可能失敗"
fi

# 檢查統計文件
if [ -f "analytic_result/lohi_signaling_stats.json" ]; then
    echo ""
    echo "檢查 LoHi 統計數據："
    python3 << 'EOF'
import json
with open('analytic_result/lohi_signaling_stats.json', 'r') as f:
    data = json.load(f)
events = data['timeline']
print(f"  總事件數: {len(events)}")
print(f"  事件類型: {set(e['event'] for e in events)}")
# 檢查 topology_change 事件
topo_changes = [e for e in events if e['event'] == 'topology_change']
print(f"  topology_change 事件: {len(topo_changes)}")
if len(topo_changes) > 0:
    print("  ✅ LoHi 正確偵測到拓撲變化！")
else:
    print("  ⚠️  LoHi 沒有偵測到拓撲變化")
EOF
    mv "analytic_result/lohi_signaling_stats.json" "analytic_result/lohi_test.json"
fi

echo ""
echo "======================================================================="
echo "快速測試完成"
echo "======================================================================="
echo ""
echo "結果檢查："
echo "  1. 查看 Chaos Monkey 日誌："
echo "     - chaos_monkey_baseline_test.log"
echo "     - chaos_monkey_lohi_test.log"
echo ""
echo "  2. 如果兩個算法都顯示 '✅ 正確偵測到拓撲變化'"
echo "     表示修復成功，可以運行完整測試："
echo "     ./rerun_baseline_lohi_dynamic.sh"
echo ""
