#!/bin/bash

# ============================================
# 修復不完整的網格數據
# ============================================

set -e

# 啟動正確的 conda 環境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 顏色輸出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "修復不完整的網格數據"
echo "============================================"
echo ""
echo "需要重新生成的網格："
echo "  ❌ Dijkstra 15° (181/201 files)"
echo "  ❌ Dijkstra 21° (181/201 files)"
echo "  ❌ Dijkstra 25° (190/201 files)"
echo ""
echo "預計時間：每個約 10-15 分鐘"
echo "總計：約 30-45 分鐘"
echo "============================================"
echo ""

# 詢問是否繼續
read -p "是否開始修復? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消執行"
    exit 0
fi

# 修復函數
fix_grid() {
    local grid_deg=$1
    local algo_name=$2
    
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}修復: $algo_name ${grid_deg}°${NC}"
    echo -e "${YELLOW}========================================${NC}"
    
    # 刪除不完整的數據
    local dir_name="starlink_550_isls_plus_grid_ground_stations_top_100_${algo_name}_${grid_deg}deg"
    if [ -d "gen_data/$dir_name" ]; then
        echo -e "${RED}刪除不完整的數據: gen_data/$dir_name${NC}"
        rm -rf "gen_data/$dir_name"
    fi
    
    # 重新生成
    echo -e "${GREEN}重新生成數據...${NC}"
    python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 $algo_name 10 $grid_deg
    
    # 驗證
    local fstate_count=$(ls "gen_data/$dir_name/dynamic_state_100ms_for_20s/fstate_"*.txt 2>/dev/null | wc -l)
    if [ $fstate_count -eq 201 ]; then
        echo -e "${GREEN}✅ 修復成功: ${grid_deg}° (201 files)${NC}"
    else
        echo -e "${RED}❌ 修復失敗: ${grid_deg}° ($fstate_count/201 files)${NC}"
    fi
}

# 開始修復
START_TIME=$(date +%s)

# 修復 Dijkstra 15°
fix_grid 15 "algorithm_hierarchical_virtual_pid_dijkstra"

# 修復 Dijkstra 21°
fix_grid 21 "algorithm_hierarchical_virtual_pid_dijkstra"

# 修復 Dijkstra 25°
fix_grid 25 "algorithm_hierarchical_virtual_pid_dijkstra"

# 計算總時間
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}🎉 修復完成！${NC}"
echo -e "${GREEN}============================================${NC}"
echo "總耗時: ${MINUTES} 分 ${SECONDS} 秒"
echo ""
echo "驗證結果："
for grid_deg in 15 21 25; do
    dir_name="gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_pid_dijkstra_${grid_deg}deg"
    if [ -d "$dir_name" ]; then
        count=$(ls "$dir_name/dynamic_state_100ms_for_20s/fstate_"*.txt 2>/dev/null | wc -l)
        if [ $count -eq 201 ]; then
            echo "  ✅ Dijkstra ${grid_deg}°: $count/201 files"
        else
            echo "  ❌ Dijkstra ${grid_deg}°: $count/201 files"
        fi
    fi
done
