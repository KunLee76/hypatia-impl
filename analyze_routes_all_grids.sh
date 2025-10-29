#!/bin/bash

# ============================================
# 分析不同網格大小的路由路徑和RTT
# 執行 satgen.post_analysis.main_print_routes_and_rtt
# ============================================

set -e

# 配置參數
GRID_SIZES=(15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30)
TIME_STEP_MS=100
DURATION_S=20
SRC_GS=1584  # 東京

# 目標地面站列表
declare -A DST_GS_MAP
DST_GS_MAP[1585]="Delhi"
DST_GS_MAP[1586]="Shanghai"
DST_GS_MAP[1593]="New_York"

# 路徑設定
DATA_DIR="../paper/satgenpy_analysis/data"
GEN_DATA_BASE="../paper/satellite_networks_state/gen_data"
SATGENPY_DIR="/home/kun/ssd2t/Leo/kun_hypatia/satgenpy"

# 顏色輸出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "============================================"
echo "路徑和RTT分析腳本"
echo "時間參數: ${TIME_STEP_MS}ms, ${DURATION_S}s"
echo "源地面站: ${SRC_GS} (Tokyo)"
echo "目標地面站: 1585 (Delhi), 1586 (Shanghai), 1593 (New York)"
echo "網格範圍: 15° - 30°"
echo "============================================"
echo ""

# 切換到 satgenpy 目錄
cd "$SATGENPY_DIR"

# 計算總任務數
TOTAL_TASKS=$((${#GRID_SIZES[@]} * 2 * ${#DST_GS_MAP[@]}))
CURRENT_TASK=0

# 遍歷兩種算法
for ALGORITHM in "algorithm_hierarchical_virtual_pid" "algorithm_hierarchical_virtual_pid_dijkstra"; do
    if [ "$ALGORITHM" = "algorithm_hierarchical_virtual_pid" ]; then
        ALGO_NAME="Floyd-Warshall"
    else
        ALGO_NAME="Dijkstra"
    fi
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}算法: ${ALGO_NAME}${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # 遍歷網格大小
    for GRID_DEG in "${GRID_SIZES[@]}"; do
        echo -e "${GREEN}--- 網格大小: ${GRID_DEG}° ---${NC}"
        
        # 構建 satellite_network_dir 路徑
        SATELLITE_NETWORK_DIR="${GEN_DATA_BASE}/starlink_550_isls_plus_grid_ground_stations_top_100_${ALGORITHM}_${GRID_DEG}deg"
        
        # 檢查目錄是否存在
        if [ ! -d "$SATELLITE_NETWORK_DIR" ]; then
            echo -e "${RED}⚠️  目錄不存在，跳過: ${SATELLITE_NETWORK_DIR}${NC}"
            CURRENT_TASK=$((CURRENT_TASK + ${#DST_GS_MAP[@]}))
            continue
        fi
        
        # 檢查 dynamic_state 目錄是否存在
        DYNAMIC_STATE_DIR="${SATELLITE_NETWORK_DIR}/dynamic_state_${TIME_STEP_MS}ms_for_${DURATION_S}s"
        if [ ! -d "$DYNAMIC_STATE_DIR" ]; then
            echo -e "${RED}⚠️  Dynamic state 目錄不存在，跳過: ${DYNAMIC_STATE_DIR}${NC}"
            CURRENT_TASK=$((CURRENT_TASK + ${#DST_GS_MAP[@]}))
            continue
        fi
        
        # 遍歷目標地面站
        for DST_GS in "${!DST_GS_MAP[@]}"; do
            CURRENT_TASK=$((CURRENT_TASK + 1))
            DST_NAME="${DST_GS_MAP[$DST_GS]}"
            
            echo -e "${YELLOW}[${CURRENT_TASK}/${TOTAL_TASKS}] Tokyo → ${DST_NAME} (${GRID_DEG}°, ${ALGO_NAME})${NC}"
            
            # 執行分析
            python -m satgen.post_analysis.main_print_routes_and_rtt \
                "$DATA_DIR" \
                "$SATELLITE_NETWORK_DIR" \
                "$TIME_STEP_MS" "$DURATION_S" \
                "$SRC_GS" "$DST_GS" || {
                    echo -e "${RED}❌ 執行失敗: ${ALGO_NAME} ${GRID_DEG}° Tokyo→${DST_NAME}${NC}"
                    continue
                }
            
            echo -e "${GREEN}✅ 完成: ${ALGO_NAME} ${GRID_DEG}° Tokyo→${DST_NAME}${NC}"
            echo ""
        done
        
        echo ""
    done
    
    echo ""
done

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}🎉 所有路徑和RTT分析完成！${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "結果保存在:"
echo "  ${DATA_DIR}/starlink_550_isls_plus_grid_ground_stations_top_100_*/100ms_for_20s/manual/"
echo ""
echo "檢查輸出:"
echo "  - data/networkx_path_${SRC_GS}_to_*.txt (路徑變化記錄)"
echo "  - data/networkx_rtt_${SRC_GS}_to_*.txt (RTT 數據)"
echo "  - pdf/time_vs_networkx_rtt_${SRC_GS}_to_*.pdf (RTT 曲線圖)"
