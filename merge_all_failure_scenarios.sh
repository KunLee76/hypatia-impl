#!/bin/bash
# 合併所有 ISL Failure 場景的統計文件

set -e

# 激活 conda 環境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

echo "========================================"
echo "合併所有 ISL Failure 場景統計文件"
echo "========================================"
echo ""

ANALYTIC_DIR="paper/satellite_networks_state/analytic_result"

# 查找所有臨時目錄
TEMP_DIRS=$(find "$ANALYTIC_DIR" -type d -name "temp_grhr*" | sort)

if [ -z "$TEMP_DIRS" ]; then
    echo "❌ 未找到任何臨時統計目錄！"
    echo "請先運行 run_failure_scenarios_20s.sh 生成統計數據"
    exit 1
fi

echo "找到以下臨時統計目錄："
echo "$TEMP_DIRS" | nl
echo ""

TOTAL=$(echo "$TEMP_DIRS" | wc -l)
CURRENT=0

for TEMP_DIR in $TEMP_DIRS; do
    CURRENT=$((CURRENT + 1))
    DIR_NAME=$(basename "$TEMP_DIR")
    
    echo "========================================="
    echo "合併 ${CURRENT}/${TOTAL}: ${DIR_NAME}"
    echo "========================================="
    
    # 統計臨時文件數量
    TEMP_FILES=$(ls "$TEMP_DIR"/*.json 2>/dev/null | wc -l)
    echo "  臨時文件數：${TEMP_FILES}"
    
    if [ "$TEMP_FILES" -eq 0 ]; then
        echo "  ⚠️ 跳過（無文件）"
        echo ""
        continue
    fi
    
    # 運行合併腳本
    echo "  開始合併..."
    python3 merge_signaling_stats.py -d "$TEMP_DIR" -v
    
    echo ""
done

echo ""
echo "========================================"
echo "所有統計文件合併完成！"
echo "========================================"
echo ""

# 列出生成的統計文件
echo "生成的統計文件："
ls -lh "$ANALYTIC_DIR"/*signaling_stats.json | awk '{print $9, "(" $5 ")"}'
echo ""

echo "下一步："
echo "運行 python analyze_failure_scenarios.py 生成分析圖表"
echo ""
