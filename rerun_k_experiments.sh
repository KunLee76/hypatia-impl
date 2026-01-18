#!/bin/bash

# 重新運行 K=1,2,4,6,999 的實驗（20秒）
# 只有 K=8 已經有正確的數據

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

echo "=================================================="
echo "重新運行 K 參數實驗 (K=1,2,4,6,999)"
echo "配置: 20秒, 100ms步長, Grid=27°"
echo "=================================================="
echo ""

for K in 1 2 4 6 999; do
    echo "=========================================="
    echo "運行 K=$K 實驗..."
    echo "開始時間: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    
    START_TIME=$(date +%s)
    
    python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100_with_hsinchu algorithm_hierarchical_virtual_gid 10 27 $K
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    if [ $? -eq 0 ]; then
        echo "✓ K=$K 完成！耗時: ${DURATION}秒"
    else
        echo "✗ K=$K 失敗！"
        exit 1
    fi
    
    echo ""
done

echo "=================================================="
echo "所有實驗完成！"
echo "完成時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="
