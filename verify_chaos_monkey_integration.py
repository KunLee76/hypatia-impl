#!/usr/bin/env python3
"""
驗證 Chaos Monkey 整合是否正確

檢查點：
1. Baseline 和 LoHi 源代碼中是否包含 ENABLE_CHAOS_MONKEY
2. 源代碼中是否包含 chaos_monkey_inject_failures 函數
3. 主函數中是否正確調用 Chaos Monkey
"""

import re

def check_file(filepath, algorithm_name):
    """檢查單個文件的 Chaos Monkey 整合"""
    print(f"\n{'='*60}")
    print(f"檢查 {algorithm_name} 算法")
    print(f"文件: {filepath}")
    print(f"{'='*60}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        "1. ENABLE_CHAOS_MONKEY 配置": r"ENABLE_CHAOS_MONKEY\s*=\s*os\.environ\.get\('ENABLE_CHAOS_MONKEY'",
        "2. CHAOS_FAILURE_RATE 配置": r"CHAOS_FAILURE_RATE\s*=\s*float\(os\.environ\.get\('CHAOS_FAILURE_RATE'",
        "3. CHAOS_INTERVAL_SNAPSHOTS 配置": r"CHAOS_INTERVAL_SNAPSHOTS\s*=\s*int\(os\.environ\.get\('CHAOS_INTERVAL_SNAPSHOTS'",
        "4. chaos_monkey_inject_failures 函數": r"def chaos_monkey_inject_failures\(",
        "5. Chaos Monkey 調用": r"if ENABLE_CHAOS_MONKEY and.*CHAOS_INTERVAL_SNAPSHOTS",
        "6. removed_isls 變量": r"removed_isls\s*=\s*chaos_monkey_inject_failures\(",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if re.search(pattern, content, re.MULTILINE | re.DOTALL):
            print(f"✅ {check_name}")
        else:
            print(f"❌ {check_name}")
            all_passed = False
    
    # 統計關鍵詞出現次數
    print(f"\n關鍵詞統計:")
    print(f"  ENABLE_CHAOS_MONKEY: {content.count('ENABLE_CHAOS_MONKEY')} 次")
    print(f"  chaos_monkey_inject_failures: {content.count('chaos_monkey_inject_failures')} 次")
    print(f"  CHAOS_FAILURE_RATE: {content.count('CHAOS_FAILURE_RATE')} 次")
    
    return all_passed

# 檢查兩個文件
baseline_file = "satgenpy/satgen/dynamic_state/algorithm_free_one_only_over_isls_with_stats.py"
lohi_file = "satgenpy/satgen/dynamic_state/algorithm_lohi.py"

baseline_ok = check_file(baseline_file, "Baseline")
lohi_ok = check_file(lohi_file, "LoHi")

print(f"\n{'='*60}")
print("總結")
print(f"{'='*60}")
print(f"Baseline: {'✅ 通過' if baseline_ok else '❌ 失敗'}")
print(f"LoHi: {'✅ 通過' if lohi_ok else '❌ 失敗'}")

if baseline_ok and lohi_ok:
    print("\n🎉 所有檢查通過！Chaos Monkey 整合成功！")
    print("\n下一步：")
    print("1. 設置環境變數啟用 Chaos Monkey：")
    print("   export ENABLE_CHAOS_MONKEY=true")
    print("   export CHAOS_FAILURE_RATE=0.01  # 1% 失效率")
    print("   export CHAOS_INTERVAL_SNAPSHOTS=20  # 每 20 snapshots 注入一次")
    print("\n2. 重新運行 Dynamic 場景：")
    print("   - Baseline: baseline_dynamic_p1/p5/p10")
    print("   - LoHi: lohi_dynamic_p1/p5/p10")
    print("\n3. 驗證結果：")
    print("   - 檢查 chaos_monkey_baseline.log 和 chaos_monkey_lohi.log")
    print("   - 確認 changed_entries 數值隨失效率增加")
else:
    print("\n❌ 部分檢查失敗，請檢查源代碼修改")
    exit(1)
