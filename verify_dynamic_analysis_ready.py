#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
驗證動態失效分析工具是否準備就緒
"""

import json
import os
import sys

ANALYTIC_DIR = "paper/satellite_networks_state/analytic_result"
SCENARIOS = ["p1", "p5", "p10"]
K_VALUES = [1, 2, 4, 6, 8, 999]

print("=" * 80)
print("驗證動態失效分析工具")
print("=" * 80)

print("\n1️⃣  檢查數據文件是否存在...")
print("-" * 80)

missing_files = []
old_format_files = []
new_format_files = []

for scenario in SCENARIOS:
    for k in K_VALUES:
        # 嘗試兩種命名模式
        found = False
        for prefix in ['dynamic', 'random']:
            filename = f"hierarchical_gid_27deg_{prefix}_{scenario}_k{k}_signaling_stats.json"
            filepath = os.path.join(ANALYTIC_DIR, filename)
            
            if os.path.exists(filepath):
                found = True
                
                # 檢查格式
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    
                    if 'summary' in data and 'by_type' in data.get('summary', {}):
                        new_format_files.append((scenario, k, prefix))
                        status = "✅ 新格式"
                    elif 'summary' in data:
                        new_format_files.append((scenario, k, prefix))
                        status = "⚠️  過渡格式"
                    else:
                        old_format_files.append((scenario, k, prefix))
                        status = "❌ 舊格式"
                    
                    print(f"  {scenario.upper()} K={k:3d} ({prefix}): {status}")
                except Exception as e:
                    print(f"  {scenario.upper()} K={k:3d} ({prefix}): ❌ 讀取錯誤 - {e}")
                break
        
        if not found:
            missing_files.append((scenario, k))
            print(f"  {scenario.upper()} K={k:3d}: ❌ 缺少文件")

print("\n" + "=" * 80)
print("驗證結果摘要")
print("=" * 80)

total = len(SCENARIOS) * len(K_VALUES)
found = len(new_format_files) + len(old_format_files)

print(f"\n總文件數: {total}")
print(f"找到文件: {found}")
print(f"缺少文件: {len(missing_files)}")
print(f"新格式: {len(new_format_files)}")
print(f"舊格式: {len(old_format_files)}")

if missing_files:
    print("\n❌ 缺少的文件：")
    for scenario, k in missing_files:
        print(f"   - {scenario.upper()} K={k}")

if old_format_files:
    print("\n⚠️  舊格式文件（需要重新執行）：")
    for scenario, k, prefix in old_format_files:
        print(f"   - {scenario.upper()} K={k} ({prefix})")

print("\n" + "=" * 80)
print("下一步操作")
print("=" * 80)

if len(old_format_files) > 0 or len(missing_files) > 0:
    print("\n❌ 數據文件不完整或格式過舊，需要重新執行動態失效測試")
    print("\n執行步驟：")
    print("  1. 快速驗證: bash verify_dynamic_test_quick.sh")
    print("  2. 完整測試: bash rerun_grhr_dynamic_200s.sh")
    print("  3. 分析結果: python3 analyze_random_failure_scenarios.py")
else:
    print("\n✅ 所有數據文件就緒，可以直接執行分析")
    print("\n執行分析：")
    print("  python3 analyze_random_failure_scenarios.py")
    print("\n輸出位置：")
    print("  - 報告: k_parameter_analysis/random_failure_scenarios_comparison_report.txt")
    print("  - 圖表: k_parameter_analysis/k_comparison_random_{p1|p5|p10}.png")

print("=" * 80)

# 返回狀態碼
if len(old_format_files) > 0 or len(missing_files) > 0:
    sys.exit(1)
else:
    sys.exit(0)
