#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
檢查隨機失效場景中哪些 ISL 被移除

用途：
  對比完整 ISL 拓撲與隨機失效後的拓撲，找出被移除的 ISL
  分析失效 ISL 的分布特徵

執行方式：
  python check_failed_isls.py [scenario]
  
  scenario: p1, p5, p10 (預設: p10)
  
範例：
  python check_failed_isls.py p10
"""

import sys
import os
import json
from collections import defaultdict

def read_isls(filepath):
    """讀取 ISL 文件，返回 ISL 集合"""
    isls = set()
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            a, b = int(parts[0]), int(parts[1])
            # 標準化：小的 ID 在前
            isl = tuple(sorted([a, b]))
            isls.add(isl)
    return isls

def analyze_isl_distribution(failed_isls, n_orbits=72, n_sats_per_orbit=22):
    """分析失效 ISL 的分布"""
    # 按類型分類
    intra_orbit = []  # 軌道內
    inter_orbit = []  # 軌道間
    
    for (a, b) in failed_isls:
        orbit_a = a // n_sats_per_orbit
        orbit_b = b // n_sats_per_orbit
        
        if orbit_a == orbit_b:
            intra_orbit.append((a, b))
        else:
            inter_orbit.append((a, b))
    
    # 按軌道統計
    orbit_stats = defaultdict(int)
    for (a, b) in failed_isls:
        orbit_a = a // n_sats_per_orbit
        orbit_b = b // n_sats_per_orbit
        orbit_stats[orbit_a] += 1
        orbit_stats[orbit_b] += 1
    
    return {
        'intra_orbit': intra_orbit,
        'inter_orbit': inter_orbit,
        'orbit_stats': dict(orbit_stats)
    }

def main():
    # 解析參數
    scenario = sys.argv[1] if len(sys.argv) > 1 else 'p10'
    
    print("=" * 70)
    print(f"檢查隨機失效場景: {scenario}")
    print("=" * 70)
    print()
    
    # Starlink-550 參數
    n_orbits = 72
    n_sats_per_orbit = 22
    total_sats = n_orbits * n_sats_per_orbit
    
    print(f"星座參數:")
    print(f"  - 軌道數: {n_orbits}")
    print(f"  - 每軌衛星數: {n_sats_per_orbit}")
    print(f"  - 總衛星數: {total_sats}")
    print()
    
    # 找到對應的場景目錄（任意 K 值都可以，因為 ISL 拓撲相同）
    base_dir = "paper/satellite_networks_state/gen_data"
    pattern = f"starlink_550_isls_random_{scenario}_ground_stations_top_100_algorithm_hierarchical_virtual_gid_27deg_k1"
    
    scenario_dir = os.path.join(base_dir, pattern)
    
    if not os.path.exists(scenario_dir):
        print(f"✗ 場景目錄不存在: {scenario_dir}")
        print()
        print("可用的場景目錄:")
        if os.path.exists(base_dir):
            for d in sorted(os.listdir(base_dir)):
                if f"isls_random_{scenario}" in d:
                    print(f"  - {d}")
        return
    
    # 讀取隨機失效場景的 ISL
    random_isl_file = os.path.join(scenario_dir, "isls.txt")
    
    if not os.path.exists(random_isl_file):
        print(f"✗ ISL 文件不存在: {random_isl_file}")
        return
    
    print(f"讀取隨機失效 ISL: {random_isl_file}")
    random_isls = read_isls(random_isl_file)
    
    # 生成完整 ISL 拓撲作為基準
    print(f"生成完整 ISL 拓撲作為基準...")
    
    # 使用 satgenpy 生成完整拓撲
    sys.path.insert(0, 'satgenpy')
    from satgen.isls.generate_plus_grid_isls import generate_plus_grid_isls_original
    
    temp_complete_file = "/tmp/complete_isls.txt"
    complete_isl_list = generate_plus_grid_isls_original(
        temp_complete_file,
        n_orbits,
        n_sats_per_orbit,
        isl_shift=0,
        idx_offset=0
    )
    complete_isls = set(tuple(sorted([a, b])) for (a, b) in complete_isl_list)
    
    # 對比
    print()
    print("=" * 70)
    print("ISL 拓撲對比")
    print("=" * 70)
    print()
    
    print(f"完整 ISL 數量: {len(complete_isls)}")
    print(f"隨機失效後 ISL 數量: {len(random_isls)}")
    
    # 找出被移除的 ISL
    failed_isls = complete_isls - random_isls
    unexpected_isls = random_isls - complete_isls  # 不應該有
    
    print(f"失效 ISL 數量: {len(failed_isls)}")
    print(f"失效率: {len(failed_isls)/len(complete_isls)*100:.2f}%")
    
    if unexpected_isls:
        print(f"⚠️  異常 ISL 數量: {len(unexpected_isls)} (這些 ISL 不在完整拓撲中)")
    
    print()
    
    # 分析失效 ISL 分布
    if failed_isls:
        print("=" * 70)
        print("失效 ISL 分布分析")
        print("=" * 70)
        print()
        
        analysis = analyze_isl_distribution(failed_isls, n_orbits, n_sats_per_orbit)
        
        print(f"按 ISL 類型分類:")
        print(f"  - 軌道內 ISL (intra-orbit): {len(analysis['intra_orbit'])} ({len(analysis['intra_orbit'])/len(failed_isls)*100:.1f}%)")
        print(f"  - 軌道間 ISL (inter-orbit): {len(analysis['inter_orbit'])} ({len(analysis['inter_orbit'])/len(failed_isls)*100:.1f}%)")
        print()
        
        # 顯示軌道統計（失效數量最多的前 10 個軌道）
        orbit_stats = analysis['orbit_stats']
        if orbit_stats:
            print(f"失效 ISL 影響的軌道統計 (前 10):")
            sorted_orbits = sorted(orbit_stats.items(), key=lambda x: x[1], reverse=True)[:10]
            for orbit, count in sorted_orbits:
                print(f"  - 軌道 {orbit:2d}: {count} 條 ISL 受影響")
            print()
        
        # 顯示部分失效 ISL 樣本
        print(f"失效 ISL 樣本 (前 20):")
        for i, (a, b) in enumerate(sorted(failed_isls)[:20], 1):
            orbit_a = a // n_sats_per_orbit
            orbit_b = b // n_sats_per_orbit
            sat_a_in_orbit = a % n_sats_per_orbit
            sat_b_in_orbit = b % n_sats_per_orbit
            
            isl_type = "intra" if orbit_a == orbit_b else "inter"
            print(f"  {i:2d}. ISL {a:4d}-{b:4d}  "
                  f"(軌道 {orbit_a:2d}[{sat_a_in_orbit:2d}] ↔ 軌道 {orbit_b:2d}[{sat_b_in_orbit:2d}])  "
                  f"[{isl_type}]")
        
        if len(failed_isls) > 20:
            print(f"  ... (還有 {len(failed_isls) - 20} 條)")
        
        print()
    
    # 保存詳細列表到文件
    output_file = f"failed_isls_{scenario}_detail.json"
    output_data = {
        'scenario': scenario,
        'total_complete_isls': len(complete_isls),
        'total_random_isls': len(random_isls),
        'total_failed_isls': len(failed_isls),
        'failure_rate': len(failed_isls) / len(complete_isls),
        'failed_isls': sorted([list(isl) for isl in failed_isls]),
        'distribution': {
            'intra_orbit_count': len(analysis['intra_orbit']) if failed_isls else 0,
            'inter_orbit_count': len(analysis['inter_orbit']) if failed_isls else 0,
            'orbit_stats': analysis['orbit_stats'] if failed_isls else {}
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print("=" * 70)
    print(f"✓ 詳細數據已保存到: {output_file}")
    print("=" * 70)
    print()
    
    # 清理臨時文件
    if os.path.exists(temp_complete_file):
        os.remove(temp_complete_file)


if __name__ == "__main__":
    main()
