#!/bin/bash

# 合併單一失效場景的統計文件
# 用法: bash merge_failure_scenario.sh temp_grhr_failure_l1_k8

if [ $# -eq 0 ]; then
    echo "用法: $0 <temp_dir_name>"
    echo "範例: $0 temp_grhr_failure_l1_k8"
    exit 1
fi

TEMP_DIR="$1"
ANALYTIC_DIR="analytic_result"
TEMP_PATH="$ANALYTIC_DIR/$TEMP_DIR"

if [ ! -d "$TEMP_PATH" ]; then
    echo "錯誤：目錄 $TEMP_PATH 不存在"
    exit 1
fi

echo "=================================================="
echo "合併統計文件"
echo "=================================================="
echo "臨時目錄: $TEMP_PATH"
echo

# 從第一個統計文件提取元數據
FIRST_FILE=$(ls "$TEMP_PATH"/grhr_stats_*.json 2>/dev/null | head -1)

if [ -z "$FIRST_FILE" ]; then
    echo "錯誤：目錄中沒有統計文件"
    exit 1
fi

# 提取參數
GRID_DEG=$(python3 -c "import json; print(json.load(open('$FIRST_FILE'))['grid_deg'])")
K_BEST=$(python3 -c "import json; print(json.load(open('$FIRST_FILE'))['k_best_gateways'])")
SCENARIO=$(python3 -c "import json; print(json.load(open('$FIRST_FILE'))['scenario'])")

echo "grid_deg: $GRID_DEG"
echo "k_best: $K_BEST"
echo "scenario: $SCENARIO"
echo

# 構建輸出檔名
OUTPUT_NAME="hierarchical_gid_${GRID_DEG}deg"

if [ "$SCENARIO" != "baseline" ]; then
    OUTPUT_NAME="${OUTPUT_NAME}_${SCENARIO}"
fi

if [ -n "$K_BEST" ] && [ "$K_BEST" != "None" ]; then
    OUTPUT_NAME="${OUTPUT_NAME}_k${K_BEST}"
fi

OUTPUT_NAME="${OUTPUT_NAME}_signaling_stats.json"
OUTPUT_PATH="$ANALYTIC_DIR/$OUTPUT_NAME"

echo "輸出檔案: $OUTPUT_PATH"
echo

# 執行合併（使用 Python 腳本）
python3 << 'PYTHON_EOF'
import json
import sys
from pathlib import Path
from collections import defaultdict

def merge_stats(temp_dir, output_file):
    """合併統計文件"""
    temp_path = Path(temp_dir)
    temp_files = list(temp_path.glob("grhr_stats_*.json"))
    
    if not temp_files:
        print(f"錯誤：沒有找到統計文件")
        return False
    
    print(f"找到 {len(temp_files)} 個臨時文件")
    
    # 讀取所有文件
    all_events = []
    metadata = None
    
    for file_path in temp_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if metadata is None:
            metadata = {
                "algorithm": data["algorithm"],
                "algorithm_display_name": data["algorithm_display_name"],
                "grid_deg": data["grid_deg"],
                "k_best_gateways": data["k_best_gateways"],
                "scenario": data["scenario"]
            }
        
        # 收集所有事件
        for event in data["timeline"]:
            all_events.append(event)
    
    # 去重：使用 (snapshot, time_ms, event, detail) 作為唯一鍵
    unique_events = {}
    for event in all_events:
        detail_json = json.dumps(event.get("detail", {}), sort_keys=True) if "detail" in event else ''
        key = (event["snapshot"], event["time_ms"], event["event"], detail_json)
        
        if key not in unique_events:
            unique_events[key] = event
    
    # 排序事件
    sorted_events = sorted(unique_events.values(), key=lambda x: (x["snapshot"], x["time_ms"]))
    
    # 重新計算摘要
    by_type = defaultdict(lambda: {"count": 0, "bytes": 0})
    total_events = 0
    total_bytes = 0
    
    for event in sorted_events:
        event_type = event["event"]
        count = event.get("count", 1)
        bytes_val = event.get("bytes", 0)
        
        by_type[event_type]["count"] += count
        by_type[event_type]["bytes"] += bytes_val
        total_events += count
        total_bytes += bytes_val
    
    # 構建最終統計
    final_stats = {
        **metadata,
        "summary": {
            "total_events": total_events,
            "total_bytes": total_bytes,
            "by_type": dict(by_type),
            "time_window": {
                "start_ms": sorted_events[0]["time_ms"] if sorted_events else None,
                "end_ms": sorted_events[-1]["time_ms"] if sorted_events else None,
                "duration_ms": (sorted_events[-1]["time_ms"] - sorted_events[0]["time_ms"]) if sorted_events else None
            }
        },
        "timeline": sorted_events
    }
    
    # 保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_stats, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 合併完成")
    print(f"  - 原始事件: {len(all_events)}")
    print(f"  - 去重後: {len(sorted_events)}")
    print(f"  - 總事件數: {total_events}")
    
    return True

# 執行合併
import os
temp_dir = os.environ.get('TEMP_PATH')
output_file = os.environ.get('OUTPUT_PATH')

if merge_stats(temp_dir, output_file):
    sys.exit(0)
else:
    sys.exit(1)

PYTHON_EOF

# 檢查結果
if [ $? -eq 0 ]; then
    echo
    echo "=================================================="
    echo "✓ 合併成功！"
    echo "輸出: $OUTPUT_PATH"
    echo "=================================================="
    
    # 顯示統計摘要
    python3 << 'SUMMARY_EOF'
import json
import os

output_file = os.environ.get('OUTPUT_PATH')
with open(output_file, 'r') as f:
    stats = json.load(f)

summary = stats['summary']
print("\n統計摘要:")
print(f"  總事件數: {summary['total_events']}")
print(f"  總字節數: {summary['total_bytes']}")
print("\n各類型事件:")
for event_type, counts in summary['by_type'].items():
    print(f"  - {event_type}: {counts['count']} 次")

SUMMARY_EOF

else
    echo
    echo "=================================================="
    echo "✗ 合併失敗"
    echo "=================================================="
    exit 1
fi
