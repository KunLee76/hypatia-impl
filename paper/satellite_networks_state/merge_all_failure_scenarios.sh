#!/bin/bash

# 批量合併所有失效場景的統計文件

echo "=================================================="
echo "批量合併失效場景統計"
echo "=================================================="
echo

ANALYTIC_DIR="analytic_result"
COUNT=0
SUCCESS=0
FAILED=0

# 尋找所有 temp_grhr* 目錄
for TEMP_DIR in "$ANALYTIC_DIR"/temp_grhr*; do
    if [ -d "$TEMP_DIR" ]; then
        DIR_NAME=$(basename "$TEMP_DIR")
        echo "[$((COUNT + 1))] 處理: $DIR_NAME"
        
        if bash merge_failure_scenario.sh "$DIR_NAME" > /dev/null 2>&1; then
            echo "  ✓ 成功"
            SUCCESS=$((SUCCESS + 1))
        else
            echo "  ✗ 失敗"
            FAILED=$((FAILED + 1))
        fi
        
        COUNT=$((COUNT + 1))
        echo
    fi
done

echo "=================================================="
echo "合併摘要"
echo "=================================================="
echo "總數: $COUNT"
echo "成功: $SUCCESS"
echo "失敗: $FAILED"
echo "=================================================="

if [ $COUNT -eq 0 ]; then
    echo "警告：沒有找到任何 temp_grhr* 目錄"
    exit 1
fi

# 列出所有生成的統計文件
echo
echo "生成的統計文件:"
ls -lh "$ANALYTIC_DIR"/hierarchical_gid_*_signaling_stats.json 2>/dev/null | awk '{print "  ", $9, "("$5")"}'
