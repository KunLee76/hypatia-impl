#!/usr/bin/env python3
"""
簡單測試 algorithm_lohi 核心功能
"""
import sys
import networkx as nx
sys.path.insert(0, 'satgenpy')

from satgen.dynamic_state.algorithm_lohi import (
    VirtualPIDRouterPlaneBlock,
    GroupPlanner,
    BorderSelector,
    _infer_constellation_config,
    PLANES_PER_GROUP,
    SATS_PER_PLANE_IN_GROUP
)

def test_constellation_inference():
    """測試星座配置推斷"""
    print("=" * 60)
    print("測試 1: 星座配置推斷")
    print("=" * 60)
    
    # Starlink-550: 72 × 22 = 1584
    config = _infer_constellation_config(1584)
    print(f"1584 顆衛星 -> {config}")
    assert config == (72, 22), f"Expected (72, 22), got {config}"
    
    # Kuiper-630: 34 × 34 = 1156
    config = _infer_constellation_config(1156)
    print(f"1156 顆衛星 -> {config}")
    assert config == (34, 34), f"Expected (34, 34), got {config}"
    
    print("✓ 星座配置推斷測試通過\n")

def test_plane_block_grouping():
    """測試 p×s 分群邏輯"""
    print("=" * 60)
    print("測試 2: Plane-Block 分群 (p=6, s=10)")
    print("=" * 60)
    
    # 建立一個小型測試圖：72 orbits × 22 sats = 1584 sats
    # 簡化：只測試前 60 顆（確保跨多個群）
    G = nx.Graph()
    for sid in range(60):
        plane = sid // 22  # 72 orbits, 22 sats per orbit
        pos = sid % 22
        G.add_node(sid, plane=plane, pos_in_plane=pos)
    
    # 添加一些邊（簡化：只連接同軌道前後衛星）
    for sid in range(59):
        if (sid % 22) < 21:  # 不是最後一顆
            G.add_edge(sid, sid + 1, geo_len_m=1000.0, weight=1000.0)
    
    router = VirtualPIDRouterPlaneBlock()
    sat_to_pid = router.refresh_pid_members_and_subgraphs(list(range(60)), G)
    
    print(f"總群數: {len(router.pid_members)}")
    print(f"前 10 顆衛星的群分配: {[sat_to_pid.get(i, None) for i in range(10)]}")
    
    # 驗證分群邏輯
    # plane_block_id = plane // 6
    # seg_id = pos // 10
    # 衛星 0: plane=0, pos=0 -> (0, 0)
    # 衛星 22: plane=1, pos=0 -> (0, 0) (同群)
    # 衛星 10: plane=0, pos=10 -> (0, 1) (不同群)
    
    pid_0 = sat_to_pid[0]
    pid_22 = sat_to_pid[22]
    pid_10 = sat_to_pid[10]
    
    print(f"衛星 0 (plane=0, pos=0) -> PID {pid_0}")
    print(f"衛星 22 (plane=1, pos=0) -> PID {pid_22}")
    print(f"衛星 10 (plane=0, pos=10) -> PID {pid_10}")
    
    assert pid_0 == pid_22, f"衛星 0 和 22 應在同一群 (plane_block=0, seg=0)"
    assert pid_0 != pid_10, f"衛星 0 和 10 應在不同群 (不同 seg)"
    
    # 檢查管理衛星選擇
    print(f"\n各群管理衛星:")
    for pid, mgmt in router.pid_mgmt_sat.items():
        members = router.pid_members[pid]
        print(f"  PID {pid}: 管理衛星={mgmt}, 成員數={len(members)}")
    
    print("✓ Plane-Block 分群測試通過\n")

def test_group_graph():
    """測試群圖建構"""
    print("=" * 60)
    print("測試 3: 群圖建構")
    print("=" * 60)
    
    # 建立測試圖：3 個群，每群 10 顆衛星
    G = nx.Graph()
    sat_to_pid = {}
    
    for pid in range(3):
        for i in range(10):
            sid = pid * 10 + i
            G.add_node(sid)
            sat_to_pid[sid] = pid
            # 群內連接
            if i > 0:
                G.add_edge(sid - 1, sid, geo_len_m=1000.0)
    
    # 添加跨群連接
    # PID 0 <-> PID 1: 2 條 ISL
    G.add_edge(9, 10, geo_len_m=5000.0)   # (PID 0, sat 9) -> (PID 1, sat 10)
    G.add_edge(8, 11, geo_len_m=5200.0)   # (PID 0, sat 8) -> (PID 1, sat 11)
    
    # PID 1 <-> PID 2: 1 條 ISL
    G.add_edge(19, 20, geo_len_m=4800.0)  # (PID 1, sat 19) -> (PID 2, sat 20)
    
    gplanner = GroupPlanner()
    gplanner.build_group_graph(G, sat_to_pid, cost_mode='hop')
    
    print(f"群圖節點數: {gplanner.group_graph.number_of_nodes()}")
    print(f"群圖邊數: {gplanner.group_graph.number_of_edges()}")
    
    # 檢查邊的元數據
    print(f"\n群間連接:")
    for (a, b), meta in gplanner.edge_meta.items():
        links = meta['links']
        pid_id = meta['pid_id']
        isls = meta['isl_pairs']
        print(f"  PID {a} <-> PID {b}: {links} 條 ISL, 邏輯 PID={pid_id}")
        print(f"    實體 ISL: {isls}")
    
    assert gplanner.group_graph.has_edge(0, 1), "應有 PID 0-1 邊"
    assert gplanner.group_graph.has_edge(1, 2), "應有 PID 1-2 邊"
    assert not gplanner.group_graph.has_edge(0, 2), "不應有 PID 0-2 邊（無直接連接）"
    
    # 測試最短群路徑
    path = gplanner.shortest_group_path(0, 2)
    print(f"\nPID 0 到 PID 2 的群路徑: {path}")
    assert path == [0, 1, 2], f"Expected [0, 1, 2], got {path}"
    
    print("✓ 群圖建構測試通過\n")

def test_border_selection():
    """測試邊界衛星選擇"""
    print("=" * 60)
    print("測試 4: 邊界衛星選擇")
    print("=" * 60)
    
    # 建立測試場景
    G = nx.Graph()
    sat_to_pid = {0: 0, 1: 0, 2: 1, 3: 1}
    
    # 添加節點和跨群邊
    for sid in range(4):
        G.add_node(sid)
    
    G.add_edge(0, 2, geo_len_m=5000.0)  # PID 0 <-> PID 1
    G.add_edge(1, 3, geo_len_m=4500.0)  # PID 0 <-> PID 1 (更短)
    
    # 建立群圖
    gplanner = GroupPlanner()
    gplanner.build_group_graph(G, sat_to_pid, cost_mode='hop')
    
    # 選擇邊界對
    border = BorderSelector.pick_border_pair(G, gplanner, 0, 1, sat_to_pid)
    print(f"PID 0 -> PID 1 的邊界對: {border}")
    
    # 應選擇最短的邊 (1, 3)
    assert border == (1, 3), f"Expected (1, 3), got {border}"
    
    # 驗證方向
    u, v = border
    assert sat_to_pid[u] == 0, "u 應在 src_pid"
    assert sat_to_pid[v] == 1, "v 應在 next_pid"
    
    print("✓ 邊界衛星選擇測試通過\n")

def main():
    print("\n" + "=" * 60)
    print("LoHi Algorithm 單元測試")
    print("=" * 60 + "\n")
    
    try:
        test_constellation_inference()
        test_plane_block_grouping()
        test_group_graph()
        test_border_selection()
        
        print("\n" + "=" * 60)
        print("✓ 所有測試通過！")
        print("=" * 60 + "\n")
        print(f"配置參數:")
        print(f"  - PLANES_PER_GROUP = {PLANES_PER_GROUP}")
        print(f"  - SATS_PER_PLANE_IN_GROUP = {SATS_PER_PLANE_IN_GROUP}")
        print(f"  - 每群大小 = {PLANES_PER_GROUP} × {SATS_PER_PLANE_IN_GROUP} = {PLANES_PER_GROUP * SATS_PER_PLANE_IN_GROUP} 顆衛星")
        
        return 0
    except Exception as e:
        print(f"\n✗ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
