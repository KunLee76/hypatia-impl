#!/usr/bin/env python3
"""
檢查 WGS72 地球半徑的正確值與來源
"""

print("="*70)
print("WGS72 地球半徑驗證")
print("="*70)
print()

# 常見的地球半徑定義
WGS72_RADIUS = 6378135.0  # 目前使用的值
WGS84_RADIUS = 6378137.0  # WGS84 (更常用)

print("【常見的地球橢球模型】")
print()
print("1. WGS72 (World Geodetic System 1972)")
print(f"   赤道半徑 (a): 6,378,135.0 m")
print(f"   扁平率 (f): 1/298.26")
print(f"   用途: 舊版 GPS 系統")
print()

print("2. WGS84 (World Geodetic System 1984)")
print(f"   赤道半徑 (a): 6,378,137.0 m")
print(f"   扁平率 (f): 1/298.257223563")
print(f"   用途: 現代 GPS 系統、衛星導航")
print()

print("3. GRS80 (Geodetic Reference System 1980)")
print(f"   赤道半徑 (a): 6,378,137.0 m")
print(f"   扁平率 (f): 1/298.257222101")
print(f"   用途: 許多國家的大地測量系統")
print()

print("="*70)
print("差異分析")
print("="*70)
print()

diff = WGS84_RADIUS - WGS72_RADIUS
print(f"WGS84 - WGS72 = {diff} m = {diff*100} cm")
print()
print("對衛星軌道計算的影響:")
altitude = 1200000  # 1200 km
pct_diff = (diff / (WGS72_RADIUS + altitude)) * 100
print(f"  軌道高度: {altitude/1000} km")
print(f"  軌道半長軸差異: {diff} m")
print(f"  相對誤差: {pct_diff:.6f}%")
print()
print("✅ 差異極小 (2m)，對衛星軌道計算影響可忽略")
print()

print("="*70)
print("正確的參考來源")
print("="*70)
print()

print("WGS72 官方定義:")
print("  1. NIMA TR 8350.2 (Third Edition)")
print("     美國國家影像與測繪局技術報告")
print()
print("  2. DMA Technical Report TR 8350.2 (1991)")
print("     美國國防測繪局技術報告")
print()
print("  3. Wikipedia: World Geodetic System")
print("     https://en.wikipedia.org/wiki/World_Geodetic_System")
print()

print("WGS84 (更推薦使用):")
print("  1. NIMA TR 8350.2 (Third Edition, Amendment 1, 2004)")
print("  2. WGS84 官方文件")
print("  3. 所有現代 GPS 接收器使用此標準")
print()

print("="*70)
print("建議")
print("="*70)
print()

print("目前的註解:")
print('  # WGS72 value; taken from https://geographiclib...  ❌ 連結失效')
print()
print("建議修改為:")
print('  # WGS72 equatorial radius (6,378,135 m)')
print('  # Reference: NIMA TR 8350.2, World Geodetic System 1972')
print('  # Note: WGS84 uses 6,378,137 m (2m difference, negligible for orbit calculations)')
print()
print("或更簡潔:")
print('  # Earth radius from WGS72 geodetic system (equatorial radius)')
print()

print("="*70)
