#!/usr/bin/env python3
"""分析 algorithm_lohi.py 中未使用的函數"""

import re
from collections import defaultdict

file_path = "satgenpy/satgen/dynamic_state/algorithm_lohi.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 找出所有函數定義
func_defs = re.findall(r'^\s*def\s+(\w+)\s*\(', content, re.MULTILINE)

# 找出所有函數呼叫
func_calls = re.findall(r'(\w+)\s*\(', content)

# 統計使用次數
usage_count = defaultdict(int)
for call in func_calls:
    usage_count[call] += 1

print("="*70)
print("未使用或僅定義一次的函數")
print("="*70)
print()

unused = []
for func in func_defs:
    count = usage_count.get(func, 0)
    # 定義算一次，如果只有 1 次出現 = 未被呼叫
    if count <= 1:
        unused.append(func)
        print(f"❌ {func:40} (出現 {count} 次)")

print()
print(f"總計: {len(unused)} 個可能未使用的函數")
print()

# 特別檢查 _first_step
print("="*70)
print("特別檢查: _first_step")
print("="*70)
first_step_calls = [line for line in content.split('\n') if '_first_step' in line and 'def _first_step' not in line]
if first_step_calls:
    print(f"✅ _first_step 被使用 {len(first_step_calls)} 次:")
    for call in first_step_calls[:5]:
        print(f"  {call.strip()}")
else:
    print("❌ _first_step 未被使用")

print()
print("="*70)
print("重複的 import")
print("="*70)
print()

# 找出所有 import
imports = re.findall(r'^\s*(import .*|from .* import .*)', content, re.MULTILINE)
import_counts = defaultdict(list)
for i, imp in enumerate(imports, 1):
    import_counts[imp.strip()].append(i)

for imp, lines in import_counts.items():
    if len(lines) > 1:
        print(f"⚠️  重複 {len(lines)} 次: {imp}")
        print(f"   出現在行: {lines}")
        print()

