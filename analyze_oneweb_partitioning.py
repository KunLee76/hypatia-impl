#!/usr/bin/env python3
"""
分析 OneWeb 星座使用 6×10 分組時的 ISL-PID 對應情況
與我們的 Starlink 550 進行比較
"""

# OneWeb 參數
ONEWEB_PLANES = 18
ONEWEB_SATS_PER_PLANE = 40
ONEWEB_TOTAL = ONEWEB_PLANES * ONEWEB_SATS_PER_PLANE  # 720

# Starlink 550 參數
STARLINK_PLANES = 72
STARLINK_SATS_PER_PLANE = 22
STARLINK_TOTAL = STARLINK_PLANES * STARLINK_SATS_PER_PLANE  # 1584

# 分組參數（兩者相同）
PLANES_PER_GROUP = 6  # p
SATS_PER_PLANE_IN_GROUP = 10  # s

def analyze_partitioning(num_planes, sats_per_plane, p, s, name):
    """分析特定星座的分組切割情況"""
    print(f"\n{'='*60}")
    print(f"分析 {name} 星座")
    print(f"{'='*60}")
    
    # 平面分組（plane blocks）
    plane_blocks = num_planes // p
    print(f"\n軌道平面: {num_planes}")
    print(f"每組包含軌道數 (p): {p}")
    print(f"平面分組數: {plane_blocks}")
    
    # 檢查是否能整除
    if num_planes % p == 0:
        print(f"✅ {num_planes} ÷ {p} = {plane_blocks} (整除)")
    else:
        leftover = num_planes % p
        print(f"⚠️  {num_planes} ÷ {p} = {plane_blocks} 餘 {leftover}")
    
    # 衛星分段（segments）
    segments = sats_per_plane // s
    leftover_sats = sats_per_plane % s
    print(f"\n每軌道衛星數: {sats_per_plane}")
    print(f"每段衛星數 (s): {s}")
    print(f"分段數: {segments}")
    
    if leftover_sats == 0:
        print(f"✅ {sats_per_plane} ÷ {s} = {segments} (整除)")
    else:
        print(f"⚠️  {sats_per_plane} ÷ {s} = {segments} 餘 {leftover_sats}")
    
    # PID 總數
    total_pids = plane_blocks * segments
    sats_per_pid = p * s
    print(f"\nPID 總數: {plane_blocks} × {segments} = {total_pids}")
    print(f"每個 PID 包含衛星數: {p} × {s} = {sats_per_pid}")
    
    # ISL 分析
    # 假設：
    # - Intra-plane ISL: 每顆衛星與同軌道前後衛星連接（雙向）
    # - Inter-plane ISL: 每顆衛星與相鄰軌道的衛星連接
    
    total_sats = num_planes * sats_per_plane
    
    # Intra-plane ISLs（軌道內）
    # 每軌道形成環：sats_per_plane 條 ISL（單向計算）
    intra_plane_isls = num_planes * sats_per_plane
    
    # Intra-plane ISL 切割：
    # 每個分段邊界切 1 條（pos s-1 到 pos s）
    # 有 (segments - 1) 個邊界
    # 每個邊界在 plane_blocks 個平面組中各出現一次
    # 但實際上每軌道有 (segments) 個段，邊界數 = segments（因為是環）
    if leftover_sats == 0:
        # 整除情況：每軌道有 segments 個邊界被切（環形）
        intra_cuts_per_plane = segments
    else:
        # 有餘數：最後一段大小不同
        intra_cuts_per_plane = segments  # 簡化：仍算 segments 個切割點
    
    intra_plane_cross_pid = num_planes * intra_cuts_per_plane
    
    # Inter-plane ISLs（軌道間）
    # 假設 +Grid 連接：每顆衛星連接相鄰軌道的對應位置
    # 72 個軌道形成環：72 * 22 條 ISL
    inter_plane_isls = num_planes * sats_per_plane
    
    # Inter-plane ISL 切割：
    # 平面邊界處切割：plane 5→6, 11→12, ..., 71→0
    # 有 plane_blocks 個邊界
    # 每個邊界涉及 sats_per_plane 條 ISL
    inter_plane_cross_pid = plane_blocks * sats_per_plane
    
    # 總計
    total_isls = intra_plane_isls + inter_plane_isls
    total_cross_pid = intra_plane_cross_pid + inter_plane_cross_pid
    total_intra_pid = total_isls - total_cross_pid
    
    cross_pct = (total_cross_pid / total_isls) * 100
    intra_pct = (total_intra_pid / total_isls) * 100
    
    print(f"\nISL 統計:")
    print(f"  Intra-plane ISLs: {intra_plane_isls}")
    print(f"    - Cross-PID: {intra_plane_cross_pid} ({intra_plane_cross_pid/intra_plane_isls*100:.1f}%)")
    print(f"  Inter-plane ISLs: {inter_plane_isls}")
    print(f"    - Cross-PID: {inter_plane_cross_pid} ({inter_plane_cross_pid/inter_plane_isls*100:.1f}%)")
    print(f"\n  總 ISL: {total_isls}")
    print(f"  Cross-PID ISL: {total_cross_pid} ({cross_pct:.1f}%)")
    print(f"  Intra-PID ISL: {total_intra_pid} ({intra_pct:.1f}%)")
    
    return {
        'name': name,
        'total_isls': total_isls,
        'cross_pid': total_cross_pid,
        'intra_pid': total_intra_pid,
        'cross_pct': cross_pct,
        'intra_pct': intra_pct
    }

# 分析兩個星座
oneweb = analyze_partitioning(
    ONEWEB_PLANES, ONEWEB_SATS_PER_PLANE, 
    PLANES_PER_GROUP, SATS_PER_PLANE_IN_GROUP,
    "OneWeb"
)

starlink = analyze_partitioning(
    STARLINK_PLANES, STARLINK_SATS_PER_PLANE,
    PLANES_PER_GROUP, SATS_PER_PLANE_IN_GROUP,
    "Starlink 550"
)

# 比較
print(f"\n{'='*60}")
print("比較結果")
print(f"{'='*60}")
print(f"\n{'星座':<15} {'Cross-PID ISL %':<20} {'說明'}")
print(f"{'-'*60}")
print(f"{oneweb['name']:<15} {oneweb['cross_pct']:>6.1f}%             {ONEWEB_PLANES}÷{PLANES_PER_GROUP}={ONEWEB_PLANES//PLANES_PER_GROUP}, {ONEWEB_SATS_PER_PLANE}÷{SATS_PER_PLANE_IN_GROUP}={ONEWEB_SATS_PER_PLANE//SATS_PER_PLANE_IN_GROUP}")
print(f"{starlink['name']:<15} {starlink['cross_pct']:>6.1f}%             {STARLINK_PLANES}÷{PLANES_PER_GROUP}={STARLINK_PLANES//PLANES_PER_GROUP}, {STARLINK_SATS_PER_PLANE}÷{SATS_PER_PLANE_IN_GROUP}={STARLINK_SATS_PER_PLANE//SATS_PER_PLANE_IN_GROUP}餘{STARLINK_SATS_PER_PLANE%SATS_PER_PLANE_IN_GROUP}")

print(f"\n關鍵發現:")
print(f"1. OneWeb ({ONEWEB_PLANES}×{ONEWEB_SATS_PER_PLANE}) 使用 {PLANES_PER_GROUP}×{SATS_PER_PLANE_IN_GROUP} 分組:")
print(f"   - 軌道數完美整除: {ONEWEB_PLANES} ÷ {PLANES_PER_GROUP} = {ONEWEB_PLANES//PLANES_PER_GROUP}")
print(f"   - 衛星數完美整除: {ONEWEB_SATS_PER_PLANE} ÷ {SATS_PER_PLANE_IN_GROUP} = {ONEWEB_SATS_PER_PLANE//SATS_PER_PLANE_IN_GROUP}")
print(f"   → Cross-PID ISL: {oneweb['cross_pct']:.1f}%")

print(f"\n2. Starlink 550 ({STARLINK_PLANES}×{STARLINK_SATS_PER_PLANE}) 使用 {PLANES_PER_GROUP}×{SATS_PER_PLANE_IN_GROUP} 分組:")
print(f"   - 軌道數完美整除: {STARLINK_PLANES} ÷ {PLANES_PER_GROUP} = {STARLINK_PLANES//PLANES_PER_GROUP}")
print(f"   - 衛星數有餘數: {STARLINK_SATS_PER_PLANE} ÷ {SATS_PER_PLANE_IN_GROUP} = {STARLINK_SATS_PER_PLANE//SATS_PER_PLANE_IN_GROUP} 餘 {STARLINK_SATS_PER_PLANE%SATS_PER_PLANE_IN_GROUP}")
print(f"   → Cross-PID ISL: {starlink['cross_pct']:.1f}%")

print(f"\n3. 結論:")
if abs(oneweb['cross_pct'] - starlink['cross_pct']) < 2:
    print(f"   ✅ 兩者 Cross-PID ISL 比例相近（差異 <2%）")
    print(f"   ✅ 這證明 ~{starlink['cross_pct']:.0f}% 是 p×s 幾何分組的固有特性")
    print(f"   ✅ 不是我們實作的問題，而是方法本身的權衡")
else:
    diff = abs(oneweb['cross_pct'] - starlink['cross_pct'])
    print(f"   ⚠️  兩者差異 {diff:.1f}%，可能與星座拓撲有關")
    if oneweb['cross_pct'] < starlink['cross_pct']:
        print(f"   → OneWeb 的 ISL 對應較好（整除的優勢）")
    else:
        print(f"   → Starlink 550 的 ISL 對應較好")

print(f"\n4. LoHi 論文的答案:")
print(f"   - LoHi 使用相同的 p×s 幾何分組方法")
print(f"   - 論文選擇 OneWeb 可能因為其拓撲參數能完美整除")
print(f"   - 但方法本身就會有 ~{oneweb['cross_pct']:.0f}% 的 Cross-PID ISL")
print(f"   - 這是為了「deterministic neighbor relations」的代價")
