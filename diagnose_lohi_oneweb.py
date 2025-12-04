#!/usr/bin/env python3
"""
診斷 LoHi 在 OneWeb 上的分群問題
"""

def analyze_grouping(num_orbs, num_sats_per_orb, p, s, name="Constellation"):
    """分析分群結果"""
    plane_blocks = num_orbs // p
    segments_per_plane = (num_sats_per_orb + s - 1) // s
    total_pids = plane_blocks * segments_per_plane
    
    # 計算每個 segment 的實際衛星數
    segment_sizes = []
    for seg_id in range(segments_per_plane):
        start_pos = seg_id * s
        end_pos = min((seg_id + 1) * s, num_sats_per_orb)
        seg_size = end_pos - start_pos
        segment_sizes.append(seg_size)
    
    # 每個 PID 的實際衛星數 = p planes × segment_size
    pid_sizes = [p * seg_size for seg_size in segment_sizes]
    
    print(f"\n{'='*60}")
    print(f"{name} ({num_orbs}×{num_sats_per_orb}) with p={p}, s={s}")
    print(f"{'='*60}")
    print(f"Plane blocks: {plane_blocks}")
    print(f"Segments per plane: {segments_per_plane}")
    print(f"Total PIDs: {total_pids}")
    print(f"Segment sizes: {segment_sizes}")
    print(f"PID sizes (sats per PID): {pid_sizes}")
    print(f"Min PID size: {min(pid_sizes)}")
    print(f"Max PID size: {max(pid_sizes)}")
    print(f"Avg PID size: {sum(pid_sizes) / len(pid_sizes):.1f}")
    
    # 評估
    max_pid_size = max(pid_sizes)
    if max_pid_size > 100:
        print(f"❌ WARNING: PID 過大 ({max_pid_size} sats)，可能導致路徑計算問題")
    elif max_pid_size > 60:
        print(f"⚠️  CAUTION: PID 稍大 ({max_pid_size} sats)，可能影響性能")
    else:
        print(f"✅ OK: PID 大小合理 ({max_pid_size} sats)")
    
    if total_pids < 15:
        print(f"❌ WARNING: 群數過少 ({total_pids} PIDs)，路由多樣性不足")
    elif total_pids < 25:
        print(f"⚠️  CAUTION: 群數偏少 ({total_pids} PIDs)")
    else:
        print(f"✅ OK: 群數充足 ({total_pids} PIDs)")
    
    return total_pids, max_pid_size

if __name__ == "__main__":
    print("\n" + "="*60)
    print("LoHi 分群診斷工具")
    print("="*60)
    
    # 測試 OneWeb
    print("\n## OneWeb 測試 ##")
    analyze_grouping(18, 40, 6, 10, "OneWeb (原始 p=6, s=10)")
    analyze_grouping(18, 40, 3, 10, "OneWeb (建議 p=3, s=10)")
    analyze_grouping(18, 40, 6, 5, "OneWeb (替代 p=6, s=5)")
    analyze_grouping(18, 40, 2, 10, "OneWeb (激進 p=2, s=10)")
    
    # 測試 Starlink
    print("\n## Starlink 測試 ##")
    analyze_grouping(72, 22, 6, 10, "Starlink (原始 p=6, s=10)")
    
    print("\n" + "="*60)
    print("建議：")
    print("  - OneWeb: 使用 p=3, s=10 (30 sats/PID, 24 PIDs)")
    print("  - Starlink: 保持 p=6, s=10 (60 sats/PID, 36 PIDs)")
    print("="*60 + "\n")
