#!/usr/bin/env python3
"""
測試 LoHi 統計輸出格式
"""
import sys
import json
import os
import tempfile
sys.path.insert(0, 'satgenpy')

from satgen.dynamic_state.algorithm_lohi import ControlSignalingStats

def test_stats_output():
    print("=" * 60)
    print("測試 LoHi 統計輸出格式")
    print("=" * 60)
    
    stats = ControlSignalingStats()
    
    # 記錄一些事件
    stats.record_pid_rebuild(0, 0, changed_pids=5)
    stats.record_topology_change(1, 100, delta_group_edges=3)
    stats.record_routing_update(2, 200, changed=100, total=500)
    
    # 轉換為 JSON
    output = stats.to_json()
    
    print("\nJSON 輸出:")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    
    # 驗證結構
    assert 'summary' in output
    assert 'timeline' in output
    
    summary = output['summary']
    assert 'total_events' in summary
    assert 'total_bytes' in summary
    assert 'pid_rebuilds' in summary
    assert 'routing_updates' in summary
    assert 'topology_changes' in summary
    
    assert summary['total_events'] == 3
    assert summary['pid_rebuilds'] == 1
    assert summary['routing_updates'] == 1
    assert summary['topology_changes'] == 1
    
    timeline = output['timeline']
    assert len(timeline) == 3
    
    # 檢查事件詳情
    event0 = timeline[0]
    assert event0['event'] == 'pid_rebuild'
    assert event0['snapshot'] == 0
    assert event0['sim_time_ms'] == 0
    assert 'detail' in event0
    
    print("\n✓ 統計輸出格式測試通過")
    print("\n欄位說明:")
    print("  - pid_rebuilds: PID/群重建次數（對應 LoHi 的 group 變動）")
    print("  - routing_updates: 路由表更新次數")
    print("  - topology_changes: 拓撲變化次數（群間連接變化）")
    print("  - total_events: 總事件數")
    print("  - total_bytes: 總控制信令字節數")
    
    # 測試與 GID 格式的相容性
    print("\n與 GID 演算法統計格式比較:")
    print("  LoHi               GID")
    print("  ----------         ----------")
    print("  pid_rebuilds       gid_rebuilds")
    print("  routing_updates    routing_updates  ✓")
    print("  topology_changes   topology_changes ✓")
    print("  (無 gateway_updates)")
    
    print("\n注意：LoHi 使用 'pid_rebuilds' 是因為文獻中就是這樣稱呼分群的。")
    print("      這是文獻 baseline 的忠實實作。")

if __name__ == "__main__":
    test_stats_output()
