#!/bin/bash

# K 參數實驗 RTT 分析腳本
# 對每個 K 值運行路由和 RTT 分析

cd /home/kun/ssd2t/Leo/kun_hypatia/satgenpy

echo "======================================================"
echo "K 參數實驗 RTT 分析"
echo "分析路徑: 1584 -> 1585, 1584 -> 1593"
echo "======================================================"
echo ""

# K 值列表
K_VALUES=(1 2 4 6 8 999)

# 目標節點列表
TARGETS=(1585 1593)

for K in "${K_VALUES[@]}"; do
    echo "======================================================"
    echo "分析 K=$K"
    echo "開始時間: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "======================================================"
    
    # 設置目錄路徑
    DATA_DIR="../paper/satellite_networks_state/gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_with_hsinchu_algorithm_hierarchical_virtual_gid_27deg_k${K}"
    
    # 檢查目錄是否存在
    if [ ! -d "$DATA_DIR" ]; then
        echo "❌ 錯誤: 目錄不存在 - $DATA_DIR"
        echo ""
        continue
    fi
    
    echo "📁 數據目錄: $DATA_DIR"
    echo ""
    
    # 對每個目標節點進行分析
    for TARGET in "${TARGETS[@]}"; do
        echo "------------------------------------------------------"
        echo "分析路徑: 1584 -> $TARGET"
        echo "------------------------------------------------------"
        
        # 1. 運行文字版路由和 RTT 分析
        echo "🔍 步驟 1/2: 文字版路由和 RTT 分析 (1584->$TARGET)..."
        python -m satgen.post_analysis.main_print_routes_and_rtt \
            ../paper/satgenpy_analysis/data \
            "$DATA_DIR" \
            100 20 1584 $TARGET
        
        if [ $? -eq 0 ]; then
            echo "✓ 文字版分析完成"
        else
            echo "✗ 文字版分析失敗"
        fi
        echo ""
        
        # 2. 運行圖形化路由和 RTT 分析
        echo "📊 步驟 2/2: 圖形化路由和 RTT 分析 (1584->$TARGET)..."
        python -m satgen.post_analysis.main_print_graphical_routes_and_rtt \
            ../paper/satgenpy_analysis/data \
            "$DATA_DIR" \
            100 20 1584 $TARGET
        
        if [ $? -eq 0 ]; then
            echo "✓ 圖形化分析完成"
        else
            echo "✗ 圖形化分析失敗"
        fi
        echo ""
    done
    
    echo "✓ K=$K 分析完成！"
    echo ""
done

echo "======================================================"
echo "所有 K 值 RTT 分析完成！"
echo "完成時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================"
echo ""
echo "結果保存在: ../paper/satgenpy_analysis/data/"
