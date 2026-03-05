#!/bin/bash

################################################################################
# 動態失效場景分析腳本
################################################################################
# 用途：在 GRHR 動態失效實驗完成後執行 K 參數分析
# 功能：分析不同失效率下 K 值對控制信令的影響
################################################################################

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================================================================${NC}"
echo -e "${BLUE}動態失效場景 K 參數分析${NC}"
echo -e "${BLUE}================================================================================================${NC}"
echo "分析時間: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 檢查必要的數據文件
echo -e "${YELLOW}[步驟 1/2] 檢查數據文件...${NC}"

ANALYTIC_DIR="paper/satellite_networks_state/analytic_result"
MISSING_FILES=0

# 檢查 GRHR 數據（18 個文件）
echo "檢查 GRHR 數據："
for scenario in p1 p5 p10; do
    for k in 1 2 4 6 8 999; do
        file="${ANALYTIC_DIR}/hierarchical_gid_27deg_random_${scenario}_k${k}_signaling_stats.json"
        if [ ! -f "$file" ]; then
            echo -e "  ${RED}✗${NC} 缺少: $(basename $file)"
            MISSING_FILES=$((MISSING_FILES + 1))
        else
            echo -e "  ${GREEN}✓${NC} $(basename $file)"
        fi
    done
done

echo ""
if [ $MISSING_FILES -gt 0 ]; then
    echo -e "${RED}錯誤：缺少 $MISSING_FILES 個 GRHR 數據文件${NC}"
    echo "請先完成 GRHR 實驗（18 個）"
    exit 1
else
    echo -e "${GREEN}✓ 所有 GRHR 數據文件完整（18 個文件）${NC}"
fi

echo ""
echo -e "${YELLOW}[步驟 2/2] 分析 GRHR K 參數影響...${NC}"
echo "輸出目錄: random_failure_analysis/"

# 執行 K 參數分析
python3 analyze_random_failure_scenarios.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ K 參數分析完成${NC}"
    echo ""
    echo "生成的文件："
    ls -lh random_failure_analysis/*.png random_failure_analysis/*.txt 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
else
    echo -e "${RED}✗ K 參數分析失敗${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}================================================================================================${NC}"
echo -e "${GREEN}分析完成！${NC}"
echo -e "${BLUE}================================================================================================${NC}"
echo ""

echo "分析結果："
echo ""
echo "GRHR K 參數分析："
echo "  目錄: random_failure_analysis/"
echo "  - k_comparison_random_p1.png   (1% 失效率)"
echo "  - k_comparison_random_p5.png   (5% 失效率)"
echo "  - k_comparison_random_p10.png  (10% 失效率)"
echo "  - random_failure_scenarios_comparison_report.txt"
echo ""
echo "原始數據："
echo "  目錄: ${ANALYTIC_DIR}/"
echo "  - 18 個 GRHR JSON 統計文件"
echo ""

echo "下一步："
echo "  - 查看圖表: open random_failure_analysis/*.png"
echo "  - 查看報告: cat random_failure_analysis/random_failure_scenarios_comparison_report.txt"
echo ""
echo "注意："
echo "  - Baseline 和 LoHi 數據需要另外分析"
echo "  - 靜態場景的多算法比較使用 hypatia_multi_algorithm_analyzer.py"
echo ""
