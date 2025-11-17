#!/usr/bin/env python3
"""
分析 Kuiper 630 和 Telesat 1015 的星座類型
判斷哪個是 Polar 星座（與 OneWeb 相同）
"""

import math

print("="*70)
print("星座類型分析：OneWeb vs Kuiper 630 vs Telesat 1015")
print("="*70)

# OneWeb (from LoHi paper)
print("\n【OneWeb】(LoHi 論文使用)")
print("-" * 70)
print("衛星總數: 720")
print("軌道平面數: 18")
print("每軌道衛星數: 40")
print("軌道傾角: 87.9°")
print("軌道高度: ~1,200 km")
print("星座類型: Walker Polar (近極軌)")
print("  → 傾角 87.9° ≈ 90° (Polar)")
print("  → 覆蓋範圍: 全球（包括極地）")

# Kuiper 630 (from main_kuiper_630.py)
print("\n【Kuiper 630】")
print("-" * 70)
print("衛星總數: 34 × 34 = 1,156")
print("軌道平面數: 34")
print("每軌道衛星數: 34")
print("軌道傾角: 51.9°")
print("軌道高度: 630 km")
print("Mean motion: 14.80 rev/day")
kuiper_is_polar = abs(51.9 - 90) < 10
print(f"星座類型: {'Walker Polar' if kuiper_is_polar else 'Walker Delta (傾斜軌道)'}")
print(f"  → 傾角 51.9° {'≈' if kuiper_is_polar else '≠'} 90°")
print(f"  → 覆蓋範圍: 中低緯度地區（±51.9° 以內）")
if not kuiper_is_polar:
    print(f"  ❌ 不是 Polar 星座！")

# Telesat 1015 (from main_telesat_1015.py)
print("\n【Telesat 1015】")
print("-" * 70)
print("衛星總數: 27 × 13 = 351")
print("軌道平面數: 27")
print("每軌道衛星數: 13")
print("軌道傾角: 98.98°")
print("軌道高度: 1,015 km")
print("Mean motion: 13.66 rev/day")
telesat_is_polar = abs(98.98 - 90) < 10
print(f"星座類型: {'Walker Polar' if telesat_is_polar else 'Walker Delta'}")
print(f"  → 傾角 98.98° ≈ 90° (實際上是 retrograde polar orbit)")
print(f"  → 覆蓋範圍: 全球（包括極地）")
if telesat_is_polar:
    print(f"  ✅ 是 Polar 星座！（逆行軌道）")

# 比較分析
print("\n" + "="*70)
print("比較分析")
print("="*70)

print("\n【軌道傾角分類】")
print("-" * 70)
print("Polar orbit (極軌): 80°-100° (接近垂直於赤道)")
print("  - OneWeb: 87.9° ✅ Polar")
print("  - Telesat: 98.98° ✅ Polar (retrograde)")
print("  - Kuiper 630: 51.9° ❌ Inclined (傾斜)")
print()
print("Inclined orbit (傾斜軌): < 80° (不經過極地)")
print("  - Starlink 550: 53° (傾斜)")
print("  - Kuiper 630: 51.9° (傾斜)")

print("\n【與 OneWeb 的相似度】")
print("-" * 70)

# Telesat vs OneWeb
print("\n✅ Telesat 1015 vs OneWeb:")
telesat_orbit_similarity = 100 - abs(98.98 - 87.9) / 90 * 100
print(f"  軌道傾角相似度: {telesat_orbit_similarity:.1f}%")
print(f"  都是 Polar orbit: ✅")
print(f"  都覆蓋全球（含極地）: ✅")
print(f"  軌道高度接近: {abs(1015 - 1200) / 1200 * 100:.1f}% 差異")
print(f"  星座規模: 351 vs 720 (小一半)")

# Kuiper vs OneWeb
print("\n❌ Kuiper 630 vs OneWeb:")
kuiper_orbit_similarity = 100 - abs(51.9 - 87.9) / 90 * 100
print(f"  軌道傾角相似度: {kuiper_orbit_similarity:.1f}%")
print(f"  都是 Polar orbit: ❌ (Kuiper 是傾斜軌道)")
print(f"  覆蓋範圍不同: Kuiper 不覆蓋極地")
print(f"  軌道高度: {abs(630 - 1200) / 1200 * 100:.1f}% 差異")
print(f"  星座規模: 1,156 vs 720 (大 60%)")

# 建議
print("\n" + "="*70)
print("建議")
print("="*70)

print("\n【選項 1: 使用 Telesat 1015】✅ 推薦")
print("-" * 70)
print("優勢:")
print("  ✅ Polar orbit (98.98°) - 與 OneWeb (87.9°) 類型相同")
print("  ✅ 全球覆蓋（包括極地）")
print("  ✅ 已有現成的 main_telesat_1015.py")
print("  ✅ 可直接測試 LoHi 在 Polar 星座的表現")
print()
print("劣勢:")
print("  ⚠️  星座規模較小 (351 vs 720)")
print("  ⚠️  拓撲結構不同 (27×13 vs 18×40)")
print("  ⚠️  需要調整 p×s 分組參數")

print("\n【選項 2: 使用 Kuiper 630】❌ 不推薦")
print("-" * 70)
print("優勢:")
print("  ✅ 星座規模大 (1,156)")
print("  ✅ 已有現成的 main_kuiper_630.py")
print()
print("劣勢:")
print("  ❌ 不是 Polar orbit (51.9° 傾斜軌道)")
print("  ❌ 與 OneWeb 的星座類型不同")
print("  ❌ 覆蓋範圍不含極地")
print("  ❌ 無法比較 Polar orbit 特性")

print("\n【選項 3: 建立 main_oneweb.py】⭐ 最佳但需要額外工作")
print("-" * 70)
print("優勢:")
print("  ⭐ 完全符合 LoHi 論文配置")
print("  ⭐ 可直接複現論文結果")
print("  ⭐ 18×40 拓撲更適合 6×10 分組")
print("  ⭐ 理論 Cross-PID ISL = 13.3%")
print()
print("需要的參數（從 LoHi 論文）:")
print("  - 軌道平面數: 18")
print("  - 每軌道衛星數: 40")
print("  - 軌道傾角: 87.9°")
print("  - 軌道高度: ~1,200 km")
print("  - Mean motion: 需要計算")
print()
print("工作量:")
print("  ⚠️  需要計算 mean motion (from altitude)")
print("  ⚠️  需要確認其他軌道參數")
print("  ✅ 程式碼可直接複製 main_telesat_1015.py 修改")

# 計算 OneWeb 的 mean motion
print("\n" + "="*70)
print("OneWeb Mean Motion 計算")
print("="*70)

EARTH_RADIUS = 6378135.0  # WGS72
ONEWEB_ALTITUDE = 1200000  # 1200 km
MU = 3.986004418e14  # Earth's gravitational parameter (m^3/s^2)

# Semi-major axis
a = EARTH_RADIUS + ONEWEB_ALTITUDE

# Orbital period (seconds)
T = 2 * math.pi * math.sqrt(a**3 / MU)

# Mean motion (revolutions per day)
mean_motion = 86400 / T  # 86400 seconds in a day

print(f"\n計算結果:")
print(f"  軌道半長軸 (a): {a/1000:.1f} km")
print(f"  軌道週期 (T): {T:.1f} seconds = {T/60:.1f} minutes")
print(f"  Mean motion: {mean_motion:.2f} rev/day")
print(f"\n  → 可用於 main_oneweb.py 的參數！")

print("\n" + "="*70)
print("最終建議")
print("="*70)

print("\n【短期測試】→ 選項 1: Telesat 1015")
print("  ✅ 立即可用，最接近 OneWeb 的 Polar 特性")
print("  ✅ 快速驗證 LoHi 在 Polar 星座的表現")
print("  ⚠️  需調整分組參數（27×13 vs 18×40）")

print("\n【完整複現】→ 選項 3: 建立 OneWeb")
print("  ⭐ 完全符合論文，結果最可信")
print("  ⭐ 18×40 拓撲 + 6×10 分組 = 完美整除")
print("  ⏱️  額外 30-60 分鐘建立檔案")

print("\n【不建議】→ 選項 2: Kuiper 630")
print("  ❌ 星座類型不同（Inclined vs Polar）")
print("  ❌ 無法驗證 Polar orbit 特性")

print("\n" + "="*70)
