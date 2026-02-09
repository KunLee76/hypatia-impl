#!/usr/bin/env python3
"""
合併 LoHi Dynamic 場景的暫存文件

用法: python3 merge_lohi_dynamic.py p1
     python3 merge_lohi_dynamic.py p5
     python3 merge_lohi_dynamic.py p10
"""

import json
import sys
import os
from collections import defaultdict

if len(sys.argv) != 2:
    print("用法: python3 merge_lohi_dynamic.py <scenario>")
    print("  scenario: p1, p5, p10")
    sys.exit(1)

scenario = sys.argv[1]
temp_dir = f"paper/satellite_networks_state/analytic_result/temp_lohi_dynamic_{scenario}"
output_file = f"paper/satellite_networks_state/analytic_result/lohi_dynamic_{scenario}_signaling_stats.json"

print(f"合併 LoHi Dynamic {scenario.upper()} 暫存文件")
print(f"  暫存目錄: {temp_dir}")
print(f"  輸出文件: {output_file}")

if not os.path.exists(temp_dir):
    print(f"錯誤: 暫存目錄不存在: {temp_dir}")
    sys.exit(1)

# 收集所有暫存文件
temp_files = sorted([
    os.path.join(temp_dir, f) 
    for f in os.listdir(temp_dir) 
    if f.endswith('.json')
])

if not temp_files:
    print(f"錯誤: 暫存目錄中沒有 JSON 文件")
    sys.exit(1)

print(f"  找到 {len(temp_files)} 個暫存文件")

# 使用去重鍵合併事件
all_events = []
seen_keys = set()

for temp_file in temp_files:
    with open(temp_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for event in data.get('timeline', []):
        # 去重鍵：(snapshot, time_ms, event_type, detail_json)
        detail_json = json.dumps(event.get('detail', {}), sort_keys=True)
        key = (event['snapshot'], event['time_ms'], event['event'], detail_json)
        
        if key not in seen_keys:
            seen_keys.add(key)
            all_events.append(event)

# 排序事件
all_events.sort(key=lambda e: (e['snapshot'], e['time_ms'], e['event']))

print(f"  去重後事件數: {len(all_events)}")

# 生成摘要統計
event_counts = defaultdict(int)
for e in all_events:
    event_counts[e['event']] += 1

print(f"  事件類型分佈:")
for event_type, count in sorted(event_counts.items()):
    print(f"    {event_type}: {count}")

# 保存合併結果
output_data = {
    "algorithm": "algorithm_lohi",
    "scenario": f"dynamic_{scenario}",
    "summary": {
        "total_events": len(all_events),
        "by_type": {
            event_type: {"count": count, "bytes": 0}
            for event_type, count in event_counts.items()
        }
    },
    "timeline": all_events
}

os.makedirs(os.path.dirname(output_file), exist_ok=True)
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output_data, f, indent=2, ensure_ascii=False)

print(f"✅ 合併完成: {output_file}")
print(f"   總事件數: {len(all_events)}")
