#!/usr/bin/env python3
"""
測試 Dijkstra 優化版演算法是否正確註冊和可調用
"""

import sys
sys.path.append("satgenpy")

def test_import():
    """測試是否可以正常導入"""
    print("=" * 60)
    print("測試 1: 導入模組")
    print("=" * 60)
    
    try:
        from satgen.dynamic_state.algorithm_hierarchical_virtual_pid_dijkstra import algorithm_hierarchical_virtual_pid
        print("✅ 成功導入 algorithm_hierarchical_virtual_pid_dijkstra")
        return True
    except Exception as e:
        print(f"❌ 導入失敗: {e}")
        return False

def test_generate_dynamic_state_import():
    """測試 generate_dynamic_state 是否包含新演算法"""
    print("\n" + "=" * 60)
    print("測試 2: 檢查 generate_dynamic_state.py 註冊")
    print("=" * 60)
    
    try:
        from satgen.dynamic_state import generate_dynamic_state
        import inspect
        
        # 讀取源碼檢查
        source = inspect.getsource(generate_dynamic_state.generate_dynamic_state_at)
        
        if "algorithm_hierarchical_virtual_pid_dijkstra" in source:
            print("✅ generate_dynamic_state.py 已包含 Dijkstra 演算法分支")
            return True
        else:
            print("❌ generate_dynamic_state.py 未找到 Dijkstra 演算法分支")
            return False
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")
        return False

def test_fstate_calculation():
    """測試新的 fstate 計算函數"""
    print("\n" + "=" * 60)
    print("測試 3: 檢查 calculate_fstate_dijkstra_based 函數")
    print("=" * 60)
    
    try:
        from satgen.dynamic_state.fstate_calculation import calculate_fstate_dijkstra_based
        import inspect
        
        sig = inspect.signature(calculate_fstate_dijkstra_based)
        print(f"✅ 成功導入 calculate_fstate_dijkstra_based")
        print(f"   函數簽名: {sig}")
        return True
    except Exception as e:
        print(f"❌ 導入失敗: {e}")
        return False

def test_algorithm_list():
    """列出所有可用的演算法"""
    print("\n" + "=" * 60)
    print("測試 4: 列出所有可用演算法")
    print("=" * 60)
    
    try:
        from satgen.dynamic_state import generate_dynamic_state
        import inspect
        
        source = inspect.getsource(generate_dynamic_state.generate_dynamic_state_at)
        
        # 提取所有 elif dynamic_state_algorithm == 的行
        algorithms = []
        for line in source.split('\n'):
            if 'dynamic_state_algorithm ==' in line and 'elif' in line:
                # 提取演算法名稱
                parts = line.split('"')
                if len(parts) >= 2:
                    algorithms.append(parts[1])
        
        print("可用的演算法:")
        for i, algo in enumerate(algorithms, 1):
            marker = "🌟" if "dijkstra" in algo.lower() else "  "
            print(f"{marker} {i}. {algo}")
        
        if any("dijkstra" in algo.lower() for algo in algorithms):
            print("\n✅ Dijkstra 演算法已在列表中")
            return True
        else:
            print("\n❌ Dijkstra 演算法未在列表中")
            return False
            
    except Exception as e:
        print(f"❌ 檢查失敗: {e}")
        return False

def main():
    """運行所有測試"""
    print("\n" + "🔍 Dijkstra 優化演算法註冊測試\n")
    
    results = []
    results.append(("導入模組", test_import()))
    results.append(("generate_dynamic_state 註冊", test_generate_dynamic_state_import()))
    results.append(("fstate_dijkstra_based 函數", test_fstate_calculation()))
    results.append(("演算法列表檢查", test_algorithm_list()))
    
    # 總結
    print("\n" + "=" * 60)
    print("測試總結")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{status}: {name}")
    
    print(f"\n總計: {passed}/{total} 測試通過")
    
    if passed == total:
        print("\n🎉 所有測試通過！Dijkstra 演算法已正確註冊。")
        print("\n下一步:")
        print("  cd paper/satellite_networks_state")
        print("  python main_25x25_fast.py algorithm_hierarchical_virtual_pid_dijkstra")
        return 0
    else:
        print("\n⚠️  部分測試失敗，請檢查上述錯誤。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
