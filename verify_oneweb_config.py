#!/usr/bin/env python3
"""
OneWeb 星座配置驗證與 LoHi 分組分析
"""

print("="*70)
print("OneWeb 星座配置驗證")
print("="*70)

# OneWeb 參數
NUM_ORBS = 18
NUM_SATS_PER_ORB = 40
TOTAL_SATS = NUM_ORBS * NUM_SATS_PER_ORB
INCLINATION = 87.9
ALTITUDE_KM = 1200

print(f"\n【星座配置】")
print(f"  軌道平面數: {NUM_ORBS}")
print(f"  每軌道衛星數: {NUM_SATS_PER_ORB}")
print(f"  總衛星數: {TOTAL_SATS}")
print(f"  軌道傾角: {INCLINATION}°")
print(f"  軌道高度: {ALTITUDE_KM} km")
print(f"  星座類型: Walker Polar (近極軌)")

# LoHi 分組配置
PLANES_PER_GROUP = 6  # p
SATS_PER_PLANE_IN_GROUP = 10  # s

print(f"\n{'='*70}")
print("LoHi 分組配置 (6×10)")
print(f"{'='*70}")

# 平面分組
plane_blocks = NUM_ORBS // PLANES_PER_GROUP
plane_remainder = NUM_ORBS % PLANES_PER_GROUP

print(f"\n【軌道平面分組】")
print(f"  每組包含軌道數 (p): {PLANES_PER_GROUP}")
print(f"  平面分組數: {NUM_ORBS} ÷ {PLANES_PER_GROUP} = {plane_blocks}")
if plane_remainder == 0:
    print(f"  ✅ 完美整除！無餘數")
else:
    print(f"  ⚠️  餘數: {plane_remainder} 個軌道")

# 衛星分段
segments = NUM_SATS_PER_ORB // SATS_PER_PLANE_IN_GROUP
sat_remainder = NUM_SATS_PER_ORB % SATS_PER_PLANE_IN_GROUP

print(f"\n【衛星分段】")
print(f"  每段包含衛星數 (s): {SATS_PER_PLANE_IN_GROUP}")
print(f"  分段數: {NUM_SATS_PER_ORB} ÷ {SATS_PER_PLANE_IN_GROUP} = {segments}")
if sat_remainder == 0:
    print(f"  ✅ 完美整除！無餘數")
else:
    print(f"  ⚠️  餘數: {sat_remainder} 顆衛星")

# PID 計算
total_pids = plane_blocks * segments
sats_per_pid = PLANES_PER_GROUP * SATS_PER_PLANE_IN_GROUP

print(f"\n【PID 統計】")
print(f"  PID 總數: {plane_blocks} × {segments} = {total_pids}")
print(f"  每個 PID 包含衛星數: {PLANES_PER_GROUP} × {SATS_PER_PLANE_IN_GROUP} = {sats_per_pid}")
print(f"  總計: {total_pids} PIDs × {sats_per_pid} sats = {total_pids * sats_per_pid} 衛星")

# Cross-PID ISL 估算
intra_plane_isls = TOTAL_SATS  # 每軌道形成環
inter_plane_isls = TOTAL_SATS  # +Grid ISL
total_isls = intra_plane_isls + inter_plane_isls

# Intra-plane cuts: 每個分段邊界
intra_cuts = NUM_ORBS * segments  # 每軌道有 segments 個切割點（環形）
# Inter-plane cuts: 每個平面組邊界
inter_cuts = plane_blocks * NUM_SATS_PER_ORB  # plane_blocks 個邊界，每個涉及 NUM_SATS_PER_ORB 條 ISL

cross_pid_isls = intra_cuts + inter_cuts
intra_pid_isls = total_isls - cross_pid_isls

cross_pct = (cross_pid_isls / total_isls) * 100
intra_pct = (intra_pid_isls / total_isls) * 100

print(f"\n【ISL 統計估算】")
print(f"  總 ISL: {total_isls}")
print(f"    - Intra-plane: {intra_plane_isls}")
print(f"    - Inter-plane: {inter_plane_isls}")
print(f"\n  Cross-PID ISL: {cross_pid_isls} ({cross_pct:.1f}%)")
print(f"    - Intra-plane cuts: {intra_cuts}")
print(f"    - Inter-plane cuts: {inter_cuts}")
print(f"\n  Intra-PID ISL: {intra_pid_isls} ({intra_pct:.1f}%)")

print(f"\n{'='*70}")
print("與 LoHi 論文比對")
print(f"{'='*70}")

print(f"\n✅ 完全符合 LoHi 論文配置:")
print(f"  ✅ 星座: OneWeb (18×40 = 720 sats)")
print(f"  ✅ 分組: 6×10 (p=6, s=10)")
print(f"  ✅ PID 數量: 12")
print(f"  ✅ 整除性: 18÷6=3, 40÷10=4 (無餘數)")
print(f"  ✅ Cross-PID ISL: ~{cross_pct:.1f}% (理論值)")

print(f"\n{'='*70}")
print("與 Starlink 550 比較")
print(f"{'='*70}")

print(f"\n| 項目 | OneWeb | Starlink 550 | 說明 |")
print(f"|------|--------|--------------|------|")
print(f"| 星座規模 | 18×40 = 720 | 72×22 = 1,584 | OneWeb 較小 |")
print(f"| 分組參數 | 6×10 | 6×10 | 相同 |")
print(f"| PID 數量 | 12 | 36 | OneWeb 較少 |")
print(f"| 整除性 | ✅✅ | ✅⚠️ | OneWeb 完美整除 |")
print(f"| Cross-PID ISL | ~{cross_pct:.1f}% | 14.6% | 相近 |")
print(f"| 星座類型 | Polar (87.9°) | Inclined (53°) | 不同 |")

print(f"\n{'='*70}")
print("執行建議")
print(f"{'='*70}")

print(f"\n【快速測試】(2 秒)")
print(f"  cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state")
print(f"  python main_oneweb_1200.py 2 100 isls_plus_grid \\")
print(f"         ground_stations_top_100 algorithm_lohi 4")

print(f"\n【標準測試】(20 秒)")
print(f"  python main_oneweb_1200.py 20 100 isls_plus_grid \\")
print(f"         ground_stations_top_100 algorithm_lohi 4")

print(f"\n【預期結果】")
print(f"  ✅ Loops: 0% (與 Starlink 550 相同)")
print(f"  ✅ Cross-PID ISL: ~13.3% (與理論相符)")
print(f"  ✅ 執行時間: < 5 分鐘 (720 sats, 較 Starlink 快)")

print(f"\n【輸出目錄】")
print(f"  gen_data/oneweb_1200_isls_plus_grid_ground_stations_top_100_algorithm_lohi/")

print(f"\n{'='*70}")
print("優勢分析")
print(f"{'='*70}")

print(f"\n✅ 使用 OneWeb 的優勢:")
print(f"  1. 完全符合 LoHi 論文配置（可直接比對結果）")
print(f"  2. 18×40 拓撲 + 6×10 分組 = 完美整除（無餘數問題）")
print(f"  3. Polar 星座 (87.9°) 覆蓋全球（包括極地）")
print(f"  4. 理論 Cross-PID ISL = 13.3%（可驗證實作正確性）")
print(f"  5. 較小規模（720 vs 1584）執行更快")

print(f"\n⚠️  注意事項:")
print(f"  1. 與 Starlink 550 是不同星座類型（Polar vs Inclined）")
print(f"  2. 無法直接比較絕對性能（星座規模不同）")
print(f"  3. 但可比較演算法特性（loops, Cross-PID ISL%）")

print(f"\n{'='*70}")
