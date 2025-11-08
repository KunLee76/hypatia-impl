#!/bin/bash
# LoHi 演算法快速測試腳本

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

echo "======================================"
echo "LoHi Algorithm Quick Test"
echo "======================================"
echo ""
echo "參數配置："
echo "  - Duration: 20 秒"
echo "  - Time step: 100 ms"
echo "  - ISL: isls_plus_grid"
echo "  - Ground stations: top_100"
echo "  - Algorithm: algorithm_lohi"
echo "  - Threads: 10"
echo "  - Grid deg: N/A (LoHi 不需要此參數)"
echo ""
echo "注意：LoHi 使用固定 6×10 平面區塊分群"
echo "======================================"
echo ""

# 運行 LoHi
echo "[Running] python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10"
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================"
    echo "✓ LoHi 演算法執行成功！"
    echo "======================================"
    echo ""
    
    # 檢查輸出
    OUTPUT_DIR="gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_lohi"
    STATS_FILE="analytic_result/lohi_signaling_stats_pure_p6_s10.json"
    
    if [ -d "$OUTPUT_DIR" ]; then
        echo "輸出目錄: $OUTPUT_DIR"
        echo "檔案列表:"
        ls -lh "$OUTPUT_DIR" | head -20
        echo ""
    fi
    
    if [ -f "$STATS_FILE" ]; then
        echo "統計檔案: $STATS_FILE"
        echo "檔案大小: $(du -h "$STATS_FILE" | cut -f1)"
        echo ""
        echo "統計摘要 (前 30 行):"
        head -30 "$STATS_FILE"
        echo ""
    fi
    
    echo "完整檔案路徑："
    echo "  動態狀態: $(pwd)/$OUTPUT_DIR"
    echo "  統計檔案: $(pwd)/$STATS_FILE"
    
else
    echo ""
    echo "======================================"
    echo "✗ LoHi 演算法執行失敗"
    echo "======================================"
    exit 1
fi
