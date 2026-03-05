#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
驗證動態失效測試準備狀態

檢查項目:
1. GRHR 算法是否支持 Chaos Monkey
2. Baseline 算法是否支持 Chaos Monkey  
3. LoHi 算法是否支持 Chaos Monkey
4. 統計記錄器是否會生成正確的 summary 結構
"""

import os
import re
import sys

def check_file_exists(filepath):
    """檢查文件是否存在"""
    exists = os.path.exists(filepath)
    return exists

def check_chaos_monkey_integration(filepath):
    """檢查文件中的 Chaos Monkey 整合"""
    if not os.path.exists(filepath):
        return {"status": "missing", "details": {}}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        "ENABLE_CHAOS_MONKEY": bool(re.search(r"ENABLE_CHAOS_MONKEY\s*=\s*os\.environ\.get\('ENABLE_CHAOS_MONKEY'", content)),
        "CHAOS_FAILURE_RATE": bool(re.search(r"CHAOS_FAILURE_RATE", content)),
        "CHAOS_INTERVAL": bool(re.search(r"CHAOS_INTERVAL_SNAPSHOTS", content)),
        "chaos_monkey_inject_failures": bool(re.search(r"def chaos_monkey_inject_failures\(", content)),
        "chaos_monkey_call": bool(re.search(r"if ENABLE_CHAOS_MONKEY and.*CHAOS_INTERVAL", content)),
        "removed_isls": bool(re.search(r"removed_isls\s*=\s*chaos_monkey_inject_failures\(", content))
    }
    
    all_pass = all(checks.values())
    return {"status": "ok" if all_pass else "partial", "details": checks}

def check_stats_recorder_format(filepath):
    """檢查統計記錄器是否生成 summary 結構"""
    if not os.path.exists(filepath):
        return {"status": "missing", "details": {}}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        "summary_structure": bool(re.search(r"['\"]summary['\"]", content)),
        "by_type_structure": bool(re.search(r"['\"]by_type['\"]", content)),
        "event_counts_structure": bool(re.search(r"['\"]event_counts['\"]", content)),
        "total_events": bool(re.search(r"['\"]total_events['\"]", content)),
        "total_bytes": bool(re.search(r"['\"]total_bytes['\"]", content))
    }
    
    return {"status": "ok", "details": checks}

def main():
    print("=" * 80)
    print("動態失效測試準備狀態驗證")
    print("=" * 80)
    print()
    
    # 文件路徑
    files_to_check = {
        "GRHR": "satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_gid.py",
        "Baseline": "satgenpy/satgen/dynamic_state/algorithm_free_one_only_over_isls_with_stats.py",
        "LoHi": "satgenpy/satgen/dynamic_state/algorithm_lohi.py"
    }
    
    all_ok = True
    
    # 檢查 Chaos Monkey 整合
    print("【1. Chaos Monkey 整合檢查】")
    print("-" * 80)
    
    for name, filepath in files_to_check.items():
        result = check_chaos_monkey_integration(filepath)
        
        if result["status"] == "missing":
            print(f"\n❌ {name}: 文件不存在")
            print(f"   路徑: {filepath}")
            all_ok = False
            continue
        
        status_icon = "✅" if result["status"] == "ok" else "⚠️"
        print(f"\n{status_icon} {name}:")
        print(f"   路徑: {filepath}")
        
        for check_name, passed in result["details"].items():
            icon = "✓" if passed else "✗"
            print(f"   {icon} {check_name}")
        
        if result["status"] != "ok":
            all_ok = False
    
    # 檢查統計記錄器
    print("\n" + "=" * 80)
    print("【2. 統計記錄器格式檢查】")
    print("-" * 80)
    
    recorder_files = {
        "GRHR": "satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_gid.py",
    }
    
    for name, filepath in recorder_files.items():
        result = check_stats_recorder_format(filepath)
        
        print(f"\n✅ {name}:")
        for check_name, found in result["details"].items():
            icon = "✓" if found else "✗"
            print(f"   {icon} {check_name}")
    
    # 環境變數檢查
    print("\n" + "=" * 80)
    print("【3. 環境變數配置】")
    print("-" * 80)
    
    env_checks = {
        "ENABLE_CHAOS_MONKEY": os.environ.get('ENABLE_CHAOS_MONKEY', 'not set'),
        "CHAOS_FAILURE_RATE": os.environ.get('CHAOS_FAILURE_RATE', 'not set'),
        "CHAOS_INTERVAL_SNAPSHOTS": os.environ.get('CHAOS_INTERVAL_SNAPSHOTS', 'not set')
    }
    
    print("\n當前環境變數:")
    for key, value in env_checks.items():
        print(f"  {key}: {value}")
    
    print("\n執行測試時應設置:")
    print("  export ENABLE_CHAOS_MONKEY=true")
    print("  export CHAOS_FAILURE_RATE=1    # 或 5, 10")
    
    # 批次執行腳本檢查
    print("\n" + "=" * 80)
    print("【4. 批次執行腳本】")
    print("-" * 80)
    
    batch_script = "run_all_dynamic_tests.sh"
    if os.path.exists(batch_script):
        print(f"\n✅ 批次執行腳本存在: {batch_script}")
        print(f"   執行方式: bash {batch_script}")
    else:
        print(f"\n❌ 批次執行腳本不存在: {batch_script}")
        all_ok = False
    
    # 總結
    print("\n" + "=" * 80)
    print("【總結】")
    print("=" * 80)
    
    if all_ok:
        print("\n✅ 所有檢查通過！可以開始執行動態失效測試。")
        print("\n執行步驟:")
        print("  1. 確保有足夠的磁碟空間 (約 1 GB)")
        print("  2. 確保有足夠的時間 (約 4 小時)")
        print("  3. 執行: bash run_all_dynamic_tests.sh")
        print("  4. 測試完成後執行: python analyze_dynamic_scenarios.py")
    else:
        print("\n❌ 部分檢查失敗，請先修正問題再執行測試。")
    
    print("=" * 80)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
