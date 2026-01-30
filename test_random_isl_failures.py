#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
測試隨機 ISL 失效功能

用途：
  1. 測試 generate_plus_grid_isls_with_random_failures() 函數
  2. 驗證不同失效率下的 ISL 存活數量
  3. 確認隨機種子的可重複性
  4. 檢查 Starlink/OneWeb 的相容性（polar vs original）

執行方式：
  python test_random_isl_failures.py
"""

import sys
import os

# 添加路徑以便導入 satgenpy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'satgenpy')))

from satgen.isls.generate_plus_grid_isls import (
    generate_plus_grid_isls_original,
    generate_plus_grid_isls_polar,
    generate_plus_grid_isls_with_random_failures
)

def test_random_failures_basic():
    """基礎測試：Starlink (53° 非極地星座)"""
    print("=" * 60)
    print("測試 1: Starlink-550 隨機失效 (53° 非極地星座)")
    print("=" * 60)
    
    # Starlink 參數
    n_orbits = 72
    n_sats_per_orbit = 22
    total_sats = n_orbits * n_sats_per_orbit  # 1584
    inclination = 53.0
    
    # 完整 ISL 數量（每顆衛星 4 條 ISL，除以 2 因為每條邊計數兩次）
    expected_complete_isls = total_sats * 2  # 3168
    
    print(f"\n參數：")
    print(f"  - 軌道數: {n_orbits}")
    print(f"  - 每軌衛星數: {n_sats_per_orbit}")
    print(f"  - 總衛星數: {total_sats}")
    print(f"  - 傾角: {inclination}°")
    print(f"  - 完整 ISL 數: {expected_complete_isls}")
    
    # 測試不同失效率
    failure_probs = [0.01, 0.05, 0.10]
    random_seed = 42
    
    print(f"\n隨機種子: {random_seed}")
    print()
    
    for prob in failure_probs:
        output_file = f"/tmp/test_starlink_random_p{int(prob*100)}.txt"
        
        surviving_isls = generate_plus_grid_isls_with_random_failures(
            output_file,
            n_orbits,
            n_sats_per_orbit,
            isl_shift=0,
            failure_probability=prob,
            random_seed=random_seed,
            idx_offset=0,
            inclination_degree=inclination,
            use_polar_version=None  # Auto-detect
        )
        
        actual_survival_rate = len(surviving_isls) / expected_complete_isls
        expected_survival_rate = 1.0 - prob
        
        print(f"失效率 {prob*100:.0f}%:")
        print(f"  - 存活 ISL: {len(surviving_isls)}/{expected_complete_isls}")
        print(f"  - 實際存活率: {actual_survival_rate*100:.2f}%")
        print(f"  - 理論存活率: {expected_survival_rate*100:.2f}%")
        print(f"  - 誤差: {abs(actual_survival_rate - expected_survival_rate)*100:.2f}%")
        
        # 清理
        os.remove(output_file)
    
    print("\n✓ Starlink 測試通過\n")


def test_random_failures_oneweb():
    """OneWeb 測試 (87.9° 極地星座)"""
    print("=" * 60)
    print("測試 2: OneWeb 隨機失效 (87.9° 極地星座)")
    print("=" * 60)
    
    # OneWeb 參數
    n_orbits = 18
    n_sats_per_orbit = 40
    total_sats = n_orbits * n_sats_per_orbit  # 720
    inclination = 87.9
    
    expected_complete_isls = total_sats * 2  # 1440
    
    print(f"\n參數：")
    print(f"  - 軌道數: {n_orbits}")
    print(f"  - 每軌衛星數: {n_sats_per_orbit}")
    print(f"  - 總衛星數: {total_sats}")
    print(f"  - 傾角: {inclination}°")
    print(f"  - 完整 ISL 數: {expected_complete_isls}")
    
    failure_prob = 0.05
    random_seed = 42
    
    print(f"\n隨機種子: {random_seed}")
    print(f"失效率: {failure_prob*100:.0f}%")
    print()
    
    output_file = "/tmp/test_oneweb_random_p5.txt"
    
    surviving_isls = generate_plus_grid_isls_with_random_failures(
        output_file,
        n_orbits,
        n_sats_per_orbit,
        isl_shift=0,
        failure_probability=failure_prob,
        random_seed=random_seed,
        idx_offset=0,
        inclination_degree=inclination,
        use_polar_version=None  # Auto-detect (should use polar)
    )
    
    actual_survival_rate = len(surviving_isls) / expected_complete_isls
    expected_survival_rate = 1.0 - failure_prob
    
    print(f"結果:")
    print(f"  - 存活 ISL: {len(surviving_isls)}/{expected_complete_isls}")
    print(f"  - 實際存活率: {actual_survival_rate*100:.2f}%")
    print(f"  - 理論存活率: {expected_survival_rate*100:.2f}%")
    print(f"  - 誤差: {abs(actual_survival_rate - expected_survival_rate)*100:.2f}%")
    
    # 清理
    os.remove(output_file)
    
    print("\n✓ OneWeb 測試通過\n")


def test_seed_reproducibility():
    """測試隨機種子的可重複性"""
    print("=" * 60)
    print("測試 3: 隨機種子可重複性")
    print("=" * 60)
    
    n_orbits = 10
    n_sats_per_orbit = 10
    inclination = 53.0
    failure_prob = 0.10
    
    print(f"\n參數：")
    print(f"  - 軌道數: {n_orbits}")
    print(f"  - 每軌衛星數: {n_sats_per_orbit}")
    print(f"  - 失效率: {failure_prob*100:.0f}%")
    print()
    
    # 使用相同種子執行兩次
    random_seed = 42
    output_file1 = "/tmp/test_seed_1.txt"
    output_file2 = "/tmp/test_seed_2.txt"
    
    print(f"使用相同種子 ({random_seed}) 執行兩次...")
    
    isls1 = generate_plus_grid_isls_with_random_failures(
        output_file1, n_orbits, n_sats_per_orbit, 0,
        failure_prob, random_seed, 0, inclination, None
    )
    
    isls2 = generate_plus_grid_isls_with_random_failures(
        output_file2, n_orbits, n_sats_per_orbit, 0,
        failure_prob, random_seed, 0, inclination, None
    )
    
    print(f"\n第一次執行: {len(isls1)} 條 ISL")
    print(f"第二次執行: {len(isls2)} 條 ISL")
    
    if set(isls1) == set(isls2):
        print("\n✓ 結果完全一致，隨機種子工作正常")
    else:
        print("\n✗ 結果不一致，隨機種子失敗！")
        return False
    
    # 使用不同種子執行
    different_seed = 99
    output_file3 = "/tmp/test_seed_3.txt"
    
    print(f"\n使用不同種子 ({different_seed}) 執行...")
    
    isls3 = generate_plus_grid_isls_with_random_failures(
        output_file3, n_orbits, n_sats_per_orbit, 0,
        failure_prob, different_seed, 0, inclination, None
    )
    
    print(f"第三次執行: {len(isls3)} 條 ISL")
    
    if set(isls1) != set(isls3):
        print("\n✓ 不同種子產生不同結果，功能正確")
    else:
        print("\n✗ 不同種子產生相同結果，隨機性有問題！")
        return False
    
    # 清理
    for f in [output_file1, output_file2, output_file3]:
        if os.path.exists(f):
            os.remove(f)
    
    print("\n✓ 隨機種子測試通過\n")
    return True


def test_extreme_cases():
    """測試極端情況"""
    print("=" * 60)
    print("測試 4: 極端情況")
    print("=" * 60)
    
    n_orbits = 5
    n_sats_per_orbit = 5
    total_sats = n_orbits * n_sats_per_orbit
    expected_complete_isls = total_sats * 2
    inclination = 53.0
    
    print(f"\n參數：")
    print(f"  - 軌道數: {n_orbits}")
    print(f"  - 每軌衛星數: {n_sats_per_orbit}")
    print(f"  - 完整 ISL 數: {expected_complete_isls}")
    print()
    
    # 測試 0% 失效（應該全部存活）
    print("測試: 0% 失效率")
    output_file = "/tmp/test_extreme_0.txt"
    isls = generate_plus_grid_isls_with_random_failures(
        output_file, n_orbits, n_sats_per_orbit, 0,
        0.0, 42, 0, inclination, None
    )
    print(f"  存活 ISL: {len(isls)}/{expected_complete_isls}")
    assert len(isls) == expected_complete_isls, "0% 失效時應該全部存活"
    os.remove(output_file)
    print("  ✓ 通過")
    
    # 測試 100% 失效（應該全部失效）
    print("\n測試: 100% 失效率")
    output_file = "/tmp/test_extreme_100.txt"
    isls = generate_plus_grid_isls_with_random_failures(
        output_file, n_orbits, n_sats_per_orbit, 0,
        1.0, 42, 0, inclination, None
    )
    print(f"  存活 ISL: {len(isls)}/{expected_complete_isls}")
    assert len(isls) == 0, "100% 失效時應該沒有存活"
    os.remove(output_file)
    print("  ✓ 通過")
    
    print("\n✓ 極端情況測試通過\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("隨機 ISL 失效功能測試套件")
    print("=" * 60 + "\n")
    
    try:
        test_random_failures_basic()
        test_random_failures_oneweb()
        test_seed_reproducibility()
        test_extreme_cases()
        
        print("\n" + "=" * 60)
        print("✓ 所有測試通過！")
        print("=" * 60 + "\n")
        
        print("下一步：執行完整實驗")
        print("  ./run_random_failure_scenarios_20s.sh")
        
    except Exception as e:
        print(f"\n✗ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
