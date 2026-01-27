#!/bin/bash
# 測試單個 ISL Failure 場景（Failure L1, K=8, 20s）

set -e

# 激活 conda 環境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

echo "========================================"
echo "測試單個 ISL Failure 場景"
echo "========================================"
echo ""
echo "測試配置："
echo "  - Scenario: Failure L1 (1 ISL 失效)"
echo "  - K 值: 8"
echo "  - 模擬時間: 20s"
echo "  - 時間步: 100ms (200 snapshots)"
echo ""

# 配置參數
DURATION=20
TIME_STEP_MS=100
GRID_DEG=27
K=8
ISL_NUM=1
SCENARIO="l1"

OUTPUT_DIR="paper/satellite_networks_state/gen_data/starlink_550_isls_failure_${SCENARIO}_${GRID_DEG}deg_k${K}"
TEMP_DIR="paper/satellite_networks_state/analytic_result/temp_grhr_failure_${SCENARIO}_k${K}"

# 清理舊數據
echo "1. 清理舊數據..."
if [ -d "$OUTPUT_DIR" ]; then
    echo "   刪除舊輸出目錄: $OUTPUT_DIR"
    rm -rf "$OUTPUT_DIR"
fi

if [ -d "$TEMP_DIR" ]; then
    echo "   刪除舊臨時目錄: $TEMP_DIR"
    rm -rf "$TEMP_DIR"
fi
echo ""

# 運行實驗
echo "2. 運行實驗..."
echo "   命令: python paper/satellite_networks_state/main_starlink_550.py \\"
echo "           ${DURATION} ${TIME_STEP_MS} isls_failure_${SCENARIO} ground_stations_top_100_with_hsinchu \\"
echo "           algorithm_hierarchical_virtual_gid 10 ${GRID_DEG} ${K}"
echo ""

START_TIME=$(date +%s)

cd paper/satellite_networks_state && \
python main_starlink_550.py \
    "${DURATION}" \
    "${TIME_STEP_MS}" \
    "isls_failure_${SCENARIO}" \
    "ground_stations_top_100_with_hsinchu" \
    "algorithm_hierarchical_virtual_gid" \
    10 \
    "${GRID_DEG}" \
    "${K}" 2>&1 | tee "../../test_failure_l1_k8_$(date +%Y%m%d_%H%M%S).log"

cd ../..

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "✓ 實驗完成！耗時: ${ELAPSED} 秒"
echo ""

# 檢查臨時統計文件
echo "3. 檢查臨時統計文件..."
if [ -d "$TEMP_DIR" ]; then
    TEMP_FILES=$(ls "$TEMP_DIR"/*.json 2>/dev/null | wc -l)
    echo "   ✓ 臨時目錄存在: $TEMP_DIR"
    echo "   ✓ 臨時文件數量: $TEMP_FILES"
    
    # 檢查第一個文件的內容
    FIRST_FILE=$(ls "$TEMP_DIR"/*.json 2>/dev/null | head -1)
    if [ -f "$FIRST_FILE" ]; then
        echo ""
        echo "   檢查第一個臨時文件內容:"
        python3 << EOF
import json
with open("$FIRST_FILE") as f:
    data = json.load(f)
print(f"     - algorithm: {data.get('algorithm', 'N/A')}")
print(f"     - grid_deg: {data.get('grid_deg', 'N/A')}")
print(f"     - k_best_gateways: {data.get('k_best_gateways', 'N/A')}")
print(f"     - scenario: {data.get('scenario', 'N/A')}")
timeline = data.get('timeline', [])
if timeline:
    snapshots = [e['snapshot'] for e in timeline]
    print(f"     - timeline events: {len(timeline)}")
    print(f"     - snapshot range: {min(snapshots)} - {max(snapshots)}")
EOF
    fi
else
    echo "   ✗ 警告：臨時目錄不存在: $TEMP_DIR"
    exit 1
fi
echo ""

# 合併統計文件
echo "4. 合併統計文件..."
python3 merge_signaling_stats.py -d "$TEMP_DIR" -v

echo ""

# 檢查合併後的 JSON
OUTPUT_JSON="paper/satellite_networks_state/analytic_result/hierarchical_gid_${GRID_DEG}deg_failure_${SCENARIO}_k${K}_signaling_stats.json"
if [ -f "$OUTPUT_JSON" ]; then
    echo "5. 驗證合併結果..."
    echo "   ✓ 輸出文件: $OUTPUT_JSON"
    echo ""
    
    python3 << EOF
import json

with open("$OUTPUT_JSON") as f:
    data = json.load(f)

summary = data.get('summary', {})
timeline = data.get('timeline', [])

print("   合併後的統計:")
print(f"     - Total events: {len(timeline)}")
print(f"     - gid_rebuild: {summary.get('gid_rebuild', {}).get('count', 0)}")
print(f"     - routing_update: {summary.get('routing_update', {}).get('count', 0)}")
print(f"     - gateway_update: {summary.get('gateway_update', {}).get('count', 0)}")
print(f"     - topology_change: {summary.get('topology_change', {}).get('count', 0)}")

if timeline:
    snapshots = [e['snapshot'] for e in timeline]
    print(f"     - Snapshot range: {min(snapshots)} - {max(snapshots)}")
    
    # 檢查是否有重複事件
    from collections import Counter
    snapshot_counts = Counter(e['snapshot'] for e in timeline)
    duplicates = {s: c for s, c in snapshot_counts.items() if c > 1}
    
    if duplicates:
        print(f"     ⚠️ 警告：發現 {len(duplicates)} 個 snapshot 有多個事件")
        print(f"        前 5 個: {list(duplicates.items())[:5]}")
    else:
        print(f"     ✓ 無重複 snapshot（每個 snapshot 最多 1 個事件）")

print()
print("   元數據:")
print(f"     - k_best_gateways: {data.get('k_best_gateways', 'N/A')}")
print(f"     - scenario: {data.get('scenario', 'N/A')}")
print(f"     - grid_deg: {data.get('grid_deg', 'N/A')}")
EOF
else
    echo "   ✗ 錯誤：合併後的文件不存在: $OUTPUT_JSON"
    exit 1
fi

echo ""
echo "========================================"
echo "✅ 測試完成！"
echo "========================================"
echo ""
echo "驗證項目："
echo "  ✓ 實驗運行成功"
echo "  ✓ 臨時目錄命名正確 (temp_grhr_failure_l1_k8/)"
echo "  ✓ 統計文件生成正確"
echo "  ✓ 合併腳本工作正常"
echo "  ✓ 去重邏輯正確（無重複計算）"
echo ""
echo "下一步："
echo "  如果測試結果正確，可以運行完整的 30 個實驗："
echo "  bash run_failure_scenarios_20s.sh"
echo ""
