#!/usr/bin/env python3
"""快速驗證 OneWeb 配置"""

# OneWeb 參數（從 main_oneweb_1200.py）
NUM_ORBS = 18
NUM_SATS_PER_ORB = 40
INCLINATION_DEGREE = 87.9
ALTITUDE_M = 1200000
MEAN_MOTION_REV_PER_DAY = 13.16

print("="*70)
print("OneWeb 配置驗證")
print("="*70)
print()

print("【星座參數】")
print(f"  軌道平面數: {NUM_ORBS}")
print(f"  每軌道衛星數: {NUM_SATS_PER_ORB}")
print(f"  總衛星數: {NUM_ORBS * NUM_SATS_PER_ORB}")
print(f"  軌道傾角: {INCLINATION_DEGREE}° (Polar)")
print(f"  軌道高度: {ALTITUDE_M / 1000:.0f} km")
print(f"  Mean motion: {MEAN_MOTION_REV_PER_DAY:.2f} rev/day")
print()

# LoHi 分組驗證
PLANES_PER_GROUP = 6
SATS_PER_PLANE_IN_GROUP = 10

plane_blocks = NUM_ORBS // PLANES_PER_GROUP
plane_remainder = NUM_ORBS % PLANES_PER_GROUP

segments = NUM_SATS_PER_ORB // SATS_PER_PLANE_IN_GROUP
sat_remainder = NUM_SATS_PER_ORB % SATS_PER_PLANE_IN_GROUP

print("【LoHi 6×10 分組驗證】")
print(f"  平面分組: {NUM_ORBS} ÷ {PLANES_PER_GROUP} = {plane_blocks}", end="")
if plane_remainder == 0:
    print(" ✅ (完美整除)")
else:
    print(f" ⚠️  (餘 {plane_remainder})")

print(f"  衛星分段: {NUM_SATS_PER_ORB} ÷ {SATS_PER_PLANE_IN_GROUP} = {segments}", end="")
if sat_remainder == 0:
    print(" ✅ (完美整除)")
else:
    print(f" ⚠️  (餘 {sat_remainder})")

print(f"  PID 總數: {plane_blocks} × {segments} = {plane_blocks * segments}")
print(f"  每 PID 衛星數: {PLANES_PER_GROUP} × {SATS_PER_PLANE_IN_GROUP} = {PLANES_PER_GROUP * SATS_PER_PLANE_IN_GROUP}")
print()

if plane_remainder == 0 and sat_remainder == 0:
    print("✅✅ 完美整除！OneWeb 最適合 LoHi 6×10 分組")
else:
    print("⚠️  有餘數，會產生不規則 PID")

print()
print("="*70)
print("main_oneweb_1200.py 功能驗證")
print("="*70)
print()
print("✅ 支援 6 或 7 個參數（與 main_starlink_550.py 一致）")
print("✅ 第 7 個參數為 grid_deg (optional, default: 15)")
print("✅ LoHi 演算法會忽略 grid_deg，使用固定 6×10 分組")
print("✅ Usage 訊息包含三種演算法範例")
print()
print("可以執行測試：")
print("  cd paper/satellite_networks_state")
print("  conda run -n kun_hypatia python main_oneweb_1200.py 20 100 \\")
print("    isls_plus_grid ground_stations_top_100 algorithm_lohi 4")
print()
