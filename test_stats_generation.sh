#!/bin/bash

# 測試統計資料生成（單一失效場景）
# 驗證修改後的算法和合併腳本是否能正確識別場景和 K 值

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

echo "======================================================"
echo "測試統計資料生成（K=1, Failure L1）"
echo "======================================================"
echo ""

# 清理舊的臨時檔案
echo "清理舊的臨時檔案..."
rm -rf analytic_result/temp_grhr/*
echo ""

# 激活 conda 環境
source /home/kun/miniconda3/bin/activate kun_hypatia

# 執行單一場景（20s 快速測試）
echo "執行測試場景..."
python main_starlink_550.py 20 100 \
    isls_failure_l1 \
    ground_stations_top_100_with_hsinchu \
    algorithm_hierarchical_virtual_gid 10 27 1

echo ""
echo "======================================================"
echo "檢查生成的臨時檔案..."
echo "======================================================"

# 檢查臨時檔案
if [ -d "analytic_result/temp_grhr" ]; then
    TEMP_COUNT=$(ls analytic_result/temp_grhr/*.json 2>/dev/null | wc -l)
    echo "找到 ${TEMP_COUNT} 個臨時檔案"
    
    if [ $TEMP_COUNT -gt 0 ]; then
        echo ""
        echo "檢查第一個臨時檔案的內容："
        FIRST_FILE=$(ls analytic_result/temp_grhr/*.json 2>/dev/null | head -1)
        python3 -c "
import json
with open('$FIRST_FILE') as f:
    data = json.load(f)
    print(f'  Algorithm: {data.get(\"algorithm\")}')
    print(f'  Display name: {data.get(\"algorithm_display_name\")}')
    print(f'  Grid deg: {data.get(\"grid_deg\")}')
    print(f'  K: {data.get(\"k_best_gateways\")}')
    print(f'  Scenario: {data.get(\"scenario\")}')
    print(f'  Total events: {data[\"summary\"][\"total_events\"]}')
"
    fi
else
    echo "❌ 臨時目錄不存在"
fi

echo ""
echo "======================================================"
echo "合併統計檔案..."
echo "======================================================"

cd /home/kun/ssd2t/Leo/kun_hypatia
python3 merge_signaling_stats.py -d paper/satellite_networks_state/analytic_result -v

echo ""
echo "======================================================"
echo "檢查最終統計檔案..."
echo "======================================================"

cd paper/satellite_networks_state
# 查找新生成的統計檔案
STATS_FILES=$(ls analytic_result/*failure*k1*.json 2>/dev/null)

if [ -n "$STATS_FILES" ]; then
    echo "✓ 找到統計檔案："
    for file in $STATS_FILES; do
        echo "  - $(basename $file)"
        python3 -c "
import json
with open('$file') as f:
    data = json.load(f)
    print(f'    Display name: {data.get(\"algorithm_display_name\")}')
    print(f'    K: {data.get(\"k_best_gateways\")}')
    print(f'    Scenario: {data.get(\"scenario\")}')
    print(f'    Total events: {data[\"summary\"][\"total_events\"]}')
"
    done
else
    echo "❌ 未找到統計檔案"
fi

echo ""
echo "======================================================"
echo "測試完成！"
echo "======================================================"
