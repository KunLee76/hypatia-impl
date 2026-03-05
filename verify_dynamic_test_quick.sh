#!/bin/bash

# ========================================
# 快速驗證動態失效測試設定
# 時長：10 秒（只為驗證設定）
# ========================================

set -e

echo "========================================"
echo "快速驗證動態失效測試設定"
echo "========================================"
echo ""

# 啟動 conda 環境
echo "1️⃣  啟動 conda 環境..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia
echo "   ✅ Conda 環境：kun_hypatia"
echo ""

# 切換到工作目錄
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 設定環境變量
export ENABLE_CHAOS_MONKEY=true
export CHAOS_FAILURE_RATE=0.01  # 1% for P1
export CHAOS_INTERVAL_SNAPSHOTS=1  # 每個 snapshot 觸發
export SATGEN_GRID_DEG=27
export K_BEST_GATEWAYS=4
export CHAOS_LOG_FILE="../../logs/chaos_verify_test.log"

echo "2️⃣  環境變量設定："
echo "   ENABLE_CHAOS_MONKEY = $ENABLE_CHAOS_MONKEY"
echo "   CHAOS_FAILURE_RATE = $CHAOS_FAILURE_RATE (1%)"
echo "   CHAOS_INTERVAL_SNAPSHOTS = $CHAOS_INTERVAL_SNAPSHOTS"
echo "   K_BEST_GATEWAYS = $K_BEST_GATEWAYS"
echo "   SATGEN_GRID_DEG = $SATGEN_GRID_DEG"
echo "   CHAOS_LOG_FILE = $CHAOS_LOG_FILE"
echo ""

# 清理舊的測試文件
echo "3️⃣  清理舊的測試文件..."
rm -f "$CHAOS_LOG_FILE"
rm -f analytic_result/hierarchical_gid_27deg_random_p1_k4_signaling_stats.json
rm -rf analytic_result/temp_grhr_random_p1_k4
echo "   ✅ 清理完成"
echo ""

echo "4️⃣  執行 10 秒驗證測試..."
echo "   命令：python main_starlink_550.py 10 2000 isls_random_p1 ground_stations_top_100_with_hsinchu algorithm_hierarchical_virtual_gid 4 27 4"
echo ""

# 執行驗證測試
if python main_starlink_550.py 10 2000 isls_random_p1 ground_stations_top_100_with_hsinchu algorithm_hierarchical_virtual_gid 4 27 4; then
    echo ""
    echo "   ✅ 模擬執行成功"
    
    # 合併統計文件
    echo ""
    echo "5️⃣  合併統計文件..."
    cd ../..
    TEMP_DIR="paper/satellite_networks_state/analytic_result/temp_grhr_random_p1_k4"
    OUTPUT_FILE="paper/satellite_networks_state/analytic_result/hierarchical_gid_27deg_random_p1_k4_signaling_stats.json"
    
    if [ -d "$TEMP_DIR" ]; then
        python3 merge_random_stats_simple.py "$TEMP_DIR" "$OUTPUT_FILE"
        echo "   ✅ 統計文件合併完成"
    else
        echo "   ❌ 錯誤：臨時目錄不存在 $TEMP_DIR"
    fi
    cd paper/satellite_networks_state
else
    echo ""
    echo "   ❌ 模擬執行失敗"
    exit 1
fi

echo ""
echo "========================================"
echo "驗證結果"
echo "========================================"

# 檢查 Chaos Monkey 日誌
echo ""
echo "6️⃣  檢查 Chaos Monkey 日誌："
if [ -f "$CHAOS_LOG_FILE" ]; then
    INJECTION_COUNT=$(grep -c "\[CHAOS_MONKEY\]" "$CHAOS_LOG_FILE" || echo "0")
    echo "   ✅ 日誌文件已生成：$CHAOS_LOG_FILE"
    echo "   📊 ISL 失效注入次數：$INJECTION_COUNT"
    echo "   📈 預期注入次數：5 (10秒 / 2秒間隔)"
    
    if [ "$INJECTION_COUNT" -eq 5 ]; then
        echo "   ✅ 注入次數正確！"
    else
        echo "   ⚠️  注意：注入次數與預期不符"
    fi
    
    echo ""
    echo "   最近 3 次注入："
    grep "\[CHAOS_MONKEY\]" "$CHAOS_LOG_FILE" | tail -3
else
    echo "   ❌ 錯誤：Chaos Monkey 日誌未生成"
    echo "   可能原因："
    echo "     - ENABLE_CHAOS_MONKEY 環境變量未正確設置"
    echo "     - C++ 代碼中的 Chaos Monkey 邏輯未啟用"
    exit 1
fi

echo ""
echo "7️⃣  檢查 JSON 輸出："

# 找出生成的 JSON 文件（應該是 random_p1_k4）
JSON_FILE="analytic_result/hierarchical_gid_27deg_random_p1_k4_signaling_stats.json"

if [ -f "$JSON_FILE" ]; then
    echo "   ✅ JSON 文件已生成：$JSON_FILE"
    
    # 檢查 JSON 格式
    if grep -q '"by_type"' "$JSON_FILE"; then
        echo "   ✅ JSON 格式正確（包含 by_type）"
        
        # 顯示 summary 部分
        echo ""
        echo "   📊 Summary 統計："
        python3 << EOF
import json
with open("$JSON_FILE", 'r') as f:
    data = json.load(f)
summary = data.get('summary', {})
print(f"      total_events: {summary.get('total_events', 'N/A')}")
if 'by_type' in summary:
    print(f"      by_type 事件類型：")
    for event_type, stats in summary['by_type'].items():
        count = stats.get('count', 0)
        bytes_val = stats.get('bytes', 0)
        print(f"        - {event_type}: {count} 事件, {bytes_val} 字節")
else:
    print("      ⚠️  缺少 by_type 結構")
EOF
    else
        echo "   ⚠️  警告：JSON 格式可能不正確（缺少 by_type）"
    fi
else
    echo "   ❌ 錯誤：JSON 文件未生成"
    echo "   請檢查模擬是否正確執行"
fi

echo ""
echo "========================================"
echo "驗證結論"
echo "========================================"

if [ "$INJECTION_COUNT" -ge 4 ] && [ -f "$JSON_FILE" ] && grep -q '"by_type"' "$JSON_FILE" 2>/dev/null; then
    echo "✅ 所有驗證通過！可以執行完整的 200 秒批次測試。"
    echo ""
    echo "執行完整測試："
    echo "   bash rerun_grhr_dynamic_200s.sh"
    exit 0
else
    echo "❌ 驗證失敗！請檢查以下問題："
    echo "   1. Chaos Monkey 是否正確觸發？(當前: $INJECTION_COUNT 次)"
    echo "   2. JSON 文件格式是否正確？(by_type: $(grep -q '"by_type"' "$JSON_FILE" 2>/dev/null && echo "有" || echo "無"))"
    echo "   3. 環境變量是否正確設置？"
    exit 1
fi
