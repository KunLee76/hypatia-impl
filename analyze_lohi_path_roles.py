#!/usr/bin/env python3
"""
LoHi 路徑分析：衛星角色分類
分析三條路徑中的管理衛星、邊界衛星、一般衛星
"""

NUM_PLANES = 72
SATS_PER_PLANE = 22
PLANES_PER_GROUP = 6
SATS_PER_PLANE_IN_GROUP = 10

def get_pid(sat_id):
    """計算衛星所屬的 PID"""
    if sat_id >= 1584:
        return None
    plane = sat_id // SATS_PER_PLANE
    pos = sat_id % SATS_PER_PLANE
    plane_block_id = plane // PLANES_PER_GROUP
    seg_id_in_plane = pos // SATS_PER_PLANE_IN_GROUP
    return plane_block_id * 3 + seg_id_in_plane

def get_sat_info(sat_id):
    """返回衛星的詳細資訊"""
    if sat_id >= 1584:
        return None, None, None
    plane = sat_id // SATS_PER_PLANE
    pos = sat_id % SATS_PER_PLANE
    pid = get_pid(sat_id)
    return plane, pos, pid

def get_management_sat(pid):
    """計算 PID 的管理衛星"""
    if pid is None:
        return None
    plane_block_id = pid // 3
    seg_id = pid % 3
    first_plane_in_block = plane_block_id * PLANES_PER_GROUP
    first_pos_in_seg = seg_id * SATS_PER_PLANE_IN_GROUP + 1
    return first_plane_in_block * SATS_PER_PLANE + first_pos_in_seg

def analyze_path(name, path, dst):
    """分析單條路徑"""
    print(f"{'─'*80}")
    print(f"📍 {name}")
    print(f"{'─'*80}")
    print(f"目的地: {dst}")
    print(f"總跳數: {len(path)-1} 跳")
    print(f"路徑節點數: {len(path)} （含起點/終點）")
    print()
    
    # 統計 PID
    pids = [get_pid(s) for s in path if s < 1584]
    unique_pids = sorted(set(pids))
    print(f"🔷 經過的 PID: {unique_pids} （共 {len(unique_pids)} 個 PID）")
    
    # 顯示各 PID 的管理衛星
    print(f"🔹 各 PID 的管理衛星:")
    for pid in unique_pids:
        mgmt_sat = get_management_sat(pid)
        plane, pos, _ = get_sat_info(mgmt_sat)
        print(f"   PID {pid}: Sat {mgmt_sat} (plane={plane}, pos={pos})")
    print()
    
    # 分析衛星角色
    management_sats = []
    border_sats = []
    normal_sats = []
    
    # 檢查路徑中是否有管理衛星
    for sat in path:
        if sat >= 1584:
            continue
        pid = get_pid(sat)
        mgmt = get_management_sat(pid)
        if sat == mgmt:
            management_sats.append(sat)
    
    # 檢查邊界衛星
    for i, sat in enumerate(path):
        if sat >= 1584:
            continue
        pid_current = get_pid(sat)
        is_border = False
        
        # 檢查前一跳
        if i > 0 and path[i-1] < 1584:
            pid_prev = get_pid(path[i-1])
            if pid_prev != pid_current:
                is_border = True
        
        # 檢查下一跳
        if i < len(path) - 1 and path[i+1] < 1584:
            pid_next = get_pid(path[i+1])
            if pid_next != pid_current:
                is_border = True
        
        if is_border:
            border_sats.append(sat)
        elif sat not in management_sats:
            normal_sats.append(sat)
    
    # 統計輸出
    print(f"📈 衛星角色統計:")
    print(f"   ✓ 管理衛星: {len(management_sats)} 顆")
    if management_sats:
        print(f"      {management_sats}")
    else:
        print(f"      (無管理衛星在路徑上)")
    
    print(f"   ✓ 邊界衛星: {len(border_sats)} 顆")
    if border_sats:
        print(f"      {border_sats}")
        # 顯示邊界衛星的詳細資訊
        for border_sat in border_sats:
            plane, pos, pid = get_sat_info(border_sat)
            print(f"      - Sat {border_sat}: plane={plane}, pos={pos}, PID={pid}")
    else:
        print(f"      (無跨 PID 路由)")
    
    print(f"   ✓ 一般衛星: {len(normal_sats)} 顆")
    print()
    
    # 跨 PID 跳躍分析
    print(f"🔄 跨 PID 跳躍:")
    cross_pid_hops = []
    for i in range(len(path)-1):
        if path[i] < 1584 and path[i+1] < 1584:
            p1 = get_pid(path[i])
            p2 = get_pid(path[i+1])
            if p1 != p2:
                cross_pid_hops.append((i, path[i], p1, path[i+1], p2))
    
    if cross_pid_hops:
        print(f"   共 {len(cross_pid_hops)} 次跨 PID 跳躍:")
        for hop_idx, sat1, pid1, sat2, pid2 in cross_pid_hops:
            plane1, pos1, _ = get_sat_info(sat1)
            plane2, pos2, _ = get_sat_info(sat2)
            print(f"   - Hop {hop_idx}: Sat {sat1} (plane={plane1}, pos={pos1}, PID {pid1})")
            print(f"              → Sat {sat2} (plane={plane2}, pos={pos2}, PID {pid2})")
    else:
        print(f"   無跨 PID 跳躍（全部在同一 PID 內）")
    print()

def main():
    # 路徑資料
    paths_data = [
        {
            'name': '路徑 1: GS 0 → GS 1',
            'path': [1584,382,381,380,379,357,335,313,291,269,247,225,203,181,159,137,115,116,117,118,119,97,75,53,1585],
            'dst': 'GS 1 (1585)'
        },
        {
            'name': '路徑 2: GS 0 → GS 2',
            'path': [1584,382,383,361,339,317,295,273,1586],
            'dst': 'GS 2 (1586)'
        },
        {
            'name': '路徑 3: GS 0 → GS 9',
            'path': [1584,382,381,380,379,357,335,313,291,269,247,225,203,181,159,137,115,114,113,91,69,47,25,3,1593],
            'dst': 'GS 9 (1593)'
        }
    ]
    
    print("="*80)
    print("📊 LoHi 路由演算法 - 三條路徑衛星角色分析報告")
    print("="*80)
    print()
    
    for path_info in paths_data:
        analyze_path(path_info['name'], path_info['path'], path_info['dst'])
    
    print("="*80)
    print("✅ 分析完成")
    print("="*80)
    print()
    print("📌 重要發現:")
    print("   1. 路徑上的衛星主要是一般衛星和邊界衛星")
    print("   2. 管理衛星不在資料面路徑上（控制面 vs 資料面分離）")
    print("   3. 邊界衛星負責跨 PID 的 ISL 跳躍")
    print("   4. 同 PID 內的路由不需要邊界衛星")
    print()

if __name__ == '__main__':
    main()
