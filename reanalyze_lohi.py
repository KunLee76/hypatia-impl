#!/usr/bin/env python3
"""重新分析未使用的函數"""

import re

file_path = "satgenpy/satgen/dynamic_state/algorithm_lohi.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    content = ''.join(lines)

# 需要檢查的函數
funcs_to_check = [
    '_dijkstra_in_pid',
    '_first_step', 
    '_build_intra_group_tree',
    '_geo_greedy_next_hop',
    '_noop_log'
]

print("="*70)
print("函數使用情況分析")
print("="*70)
print()

for func in funcs_to_check:
    # 找定義
    def_pattern = rf'^\s*def {func}\s*\('
    def_matches = list(re.finditer(def_pattern, content, re.MULTILINE))
    
    # 找使用（排除定義行）
    use_pattern = rf'{func}\s*\('
    all_matches = list(re.finditer(use_pattern, content))
    
    def_lines = [content[:m.start()].count('\n') + 1 for m in def_matches]
    use_lines = [content[:m.start()].count('\n') + 1 for m in all_matches]
    
    # 排除定義行本身
    real_uses = [line for line in use_lines if line not in def_lines]
    
    if real_uses:
        print(f"✅ {func:30} 被使用 (定義: 行{def_lines}, 使用: 行{real_uses})")
    else:
        print(f"❌ {func:30} 未使用 (定義: 行{def_lines})")
        
print()
