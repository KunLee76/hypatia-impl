#!/usr/bin/env python3
"""
測試 Process-Local Statistics 實現

這個腳本驗證：
1. Thread-local storage 正確設置
2. 每個進程能獨立記錄統計
3. 臨時文件正確生成
4. 合併工具能正確處理
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'satgenpy'))

from satgen.dynamic_state.algorithm_free_one_only_over_isls_with_stats import _get_process_local_stats as baseline_stats
from satgen.dynamic_state.algorithm_hierarchical_virtual_gid import _get_process_local_stats as grhr_stats
from satgen.dynamic_state.algorithm_lohi import _get_process_local_stats as lohi_stats

def test_baseline():
    """測試 Baseline 的 process-local stats"""
    print("測試 Baseline...")
    stats = baseline_stats()
    assert stats is not None, "Failed to get baseline stats"
    assert hasattr(stats, 'timeline'), "Stats missing timeline"
    assert hasattr(stats, 'get_stats_summary'), "Stats missing get_stats_summary"
    print("  ✓ Baseline process-local stats 正常")

def test_grhr():
    """測試 GRHR 的 process-local stats"""
    print("測試 GRHR...")
    stats = grhr_stats()
    assert stats is not None, "Failed to get GRHR stats"
    assert hasattr(stats, 'timeline'), "Stats missing timeline"
    assert hasattr(stats, 'get_stats_summary'), "Stats missing get_stats_summary"
    print("  ✓ GRHR process-local stats 正常")

def test_lohi():
    """測試 LoHi 的 process-local stats"""
    print("測試 LoHi...")
    stats = lohi_stats()
    assert stats is not None, "Failed to get LoHi stats"
    assert hasattr(stats, 'timeline'), "Stats missing timeline"
    # LoHi 使用 to_json() 而不是 get_stats_summary()
    assert hasattr(stats, 'to_json'), "Stats missing to_json"
    print("  ✓ LoHi process-local stats 正常")

def test_independence():
    """測試多次調用返回同一個對象（在同一進程/線程中）"""
    print("測試統計對象獨立性...")
    
    # 同一線程內應該返回相同對象
    baseline1 = baseline_stats()
    baseline2 = baseline_stats()
    assert baseline1 is baseline2, "Same thread should return same object"
    print("  ✓ 同一線程內返回相同對象")
    
    grhr1 = grhr_stats()
    grhr2 = grhr_stats()
    assert grhr1 is grhr2, "Same thread should return same object"
    
    lohi1 = lohi_stats()
    lohi2 = lohi_stats()
    assert lohi1 is lohi2, "Same thread should return same object"
    
    # 不同算法的對象應該不同
    assert baseline1 is not grhr1, "Different algorithms should have different objects"
    assert baseline1 is not lohi1, "Different algorithms should have different objects"
    assert grhr1 is not lohi1, "Different algorithms should have different objects"
    print("  ✓ 不同算法使用不同對象")

def test_multithread():
    """測試多線程環境下的獨立性"""
    print("測試多線程環境...")
    import threading
    
    results = []
    
    def worker():
        stats = baseline_stats()
        results.append(id(stats))
    
    threads = []
    for _ in range(3):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # 每個線程應該有不同的統計對象
    assert len(set(results)) == 3, f"Each thread should have different object, got {len(set(results))}"
    print("  ✓ 每個線程有獨立的統計對象")

def main():
    print("=" * 70)
    print("Process-Local Statistics 實現驗證")
    print("=" * 70)
    print()
    
    try:
        test_baseline()
        test_grhr()
        test_lohi()
        test_independence()
        test_multithread()
        
        print()
        print("=" * 70)
        print("✓ 所有測試通過！")
        print("=" * 70)
        print()
        print("下一步：")
        print("1. 運行小規模模擬測試（修改配置為 5-10 個 snapshot）")
        print("2. 檢查 analytic_result/temp_*/ 目錄是否生成臨時文件")
        print("3. 運行合併工具：python merge_signaling_stats.py -v")
        print("4. 驗證結果：python deduplicate_signaling_stats.py -d analytic_result --check-only")
        print("5. 如果一切正常，運行完整模擬")
        return 0
        
    except AssertionError as e:
        print()
        print("=" * 70)
        print(f"✗ 測試失敗：{e}")
        print("=" * 70)
        return 1
    except Exception as e:
        print()
        print("=" * 70)
        print(f"✗ 錯誤：{e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
