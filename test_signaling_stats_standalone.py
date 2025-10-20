#!/usr/bin/env python3
"""
獨立的控制信令統計功能測試

這個腳本直接導入和測試 ControlSignalingStats 類，
不依賴完整的satgenpy模塊。
"""

import sys
import os
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

# 直接定義統計類（從算法文件中復制）
@dataclass
class EventRow:
    """單個控制信令事件記錄"""
    snapshot: int         # 快照索引
    time_ms: int         # 模擬時間（毫秒）
    event_type: str      # 事件類型
    count: int = 1       # 事件數量
    detail: Optional[Dict[str, Any]] = None  # 詳細信息
    bytes: int = 0       # 控制信令字節數

class ControlSignalingStats:
    """控制信令統計收集器"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置所有統計數據"""
        self.routing_updates = 0
        self.gateway_updates = 0
        self.pid_rebuilds = 0
        self.topology_changes = 0
        self.total_messages = 0
        self.total_bytes = 0
        self.timeline: List[EventRow] = []
    
    def _append(self, event: EventRow):
        """添加事件到時間軸"""
        self.timeline.append(event)
        self.total_messages += event.count
        self.total_bytes += event.bytes
    
    def record_routing_update(self, snapshot, sim_time_ms, 
                              changed_entries:int, total_entries:int,
                              bytes=None, base_bytes:int=32, per_entry_bytes:int=8):
        """
        記錄路由更新事件
        
        Args:
            snapshot: 快照索引
            sim_time_ms: 模擬時間（毫秒）
            changed_entries: 改變的路由條目數
            total_entries: 總路由條目數
            bytes: 預計算的字節數（如果提供則直接使用）
            base_bytes: 基礎開銷字節數
            per_entry_bytes: 每個條目的字節數
        """
        self.routing_updates += 1
        if bytes is None:
            b = base_bytes + changed_entries * per_entry_bytes
        else:
            b = bytes
        
        self._append(EventRow(snapshot, sim_time_ms, "routing_update",
                              count=1,
                              detail={"changed_entries": changed_entries, 
                                     "total_entries": total_entries},
                              bytes=b))
    
    def record_gateway_update(self, snapshot, sim_time_ms,
                              num_gateways:int, num_pids:int,
                              bytes=None, base_bytes:int=24, per_gateway_bytes:int=12):
        """記錄網關更新事件"""
        self.gateway_updates += 1
        if bytes is None:
            b = base_bytes + num_gateways * per_gateway_bytes
        else:
            b = bytes
        
        self._append(EventRow(snapshot, sim_time_ms, "gateway_update",
                              count=1,
                              detail={"num_gateways": num_gateways, "num_pids": num_pids},
                              bytes=b))
    
    def record_pid_rebuild(self, snapshot, sim_time_ms,
                           num_pids:int, changed_pids:int, per_pid_bytes:int=20):
        """記錄PID重建事件"""
        self.pid_rebuilds += 1
        b = changed_pids * per_pid_bytes
        self._append(EventRow(snapshot, sim_time_ms, "pid_rebuild",
                              count=1,
                              detail={"num_pids": num_pids, "changed_pids": changed_pids},
                              bytes=b))
    
    def record_topology_change(self, snapshot, sim_time_ms,
                               delta_isl:int, delta_gsl:int, per_edge_bytes:int=16):
        """記錄拓撲變化"""
        self.topology_changes += 1
        b = (abs(delta_isl) + abs(delta_gsl)) * per_edge_bytes
        self._append(EventRow(snapshot, sim_time_ms, "topology_change",
                              count=1,
                              detail={"delta_isl": delta_isl, "delta_gsl": delta_gsl},
                              bytes=b))
    
    def record_event(self, event_type, snapshot, sim_time_ms, count=1, bytes=0, detail=None):
        """通用事件記錄器"""
        # 更新對應的計數器
        if event_type == "routing_update":
            self.routing_updates += count
        elif event_type == "gateway_update":
            self.gateway_updates += count
        elif event_type == "pid_rebuild":
            self.pid_rebuilds += count
        elif event_type == "topology_change":
            self.topology_changes += count
        
        self._append(EventRow(snapshot, sim_time_ms, event_type, count, detail, bytes))
    
    def get_stats_summary(self, start_time_ms=None, end_time_ms=None):
        """獲取統計摘要"""
        # 如果指定時間窗口，則過濾事件
        events = self.timeline
        if start_time_ms is not None:
            events = [e for e in events if e.time_ms >= start_time_ms]
        if end_time_ms is not None:
            events = [e for e in events if e.time_ms <= end_time_ms]
        
        # 計算統計數據
        by_type = {}
        total_bytes = 0
        total_count = 0
        
        for event in events:
            if event.event_type not in by_type:
                by_type[event.event_type] = {"count": 0, "bytes": 0}
            by_type[event.event_type]["count"] += event.count
            by_type[event.event_type]["bytes"] += event.bytes
            total_bytes += event.bytes
            total_count += event.count
        
        return {
            "total_events": total_count,
            "total_bytes": total_bytes,
            "by_type": by_type,
            "time_window": {
                "start_ms": start_time_ms,
                "end_ms": end_time_ms,
                "duration_ms": (end_time_ms - start_time_ms) if start_time_ms and end_time_ms else None
            }
        }
    
    def get_timeline_csv(self):
        """獲取時間軸數據的CSV格式字符串"""
        import io
        output = io.StringIO()
        output.write("snapshot,time_ms,event_type,count,bytes,detail\n")
        for event in self.timeline:
            detail_str = str(event.detail) if event.detail else ""
            output.write(f"{event.snapshot},{event.time_ms},{event.event_type},{event.count},{event.bytes},\"{detail_str}\"\n")
        return output.getvalue()
    
    def save_stats_to_file(self, filepath, include_timeline=True):
        """將統計數據保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=== 控制信令統計摘要 ===\n")
            summary = self.get_stats_summary()
            f.write(f"總事件數: {summary['total_events']}\n")
            f.write(f"總字節數: {summary['total_bytes']}\n")
            f.write("\n各類型事件:\n")
            for event_type, stats in summary['by_type'].items():
                f.write(f"  {event_type}: {stats['count']} 次, {stats['bytes']} 字節\n")
            
            if include_timeline:
                f.write("\n=== 事件時間軸 ===\n")
                f.write(self.get_timeline_csv())
    
    def get_stats(self):
        """獲取基本統計數據（向後兼容）"""
        return {
            "routing_updates": self.routing_updates,
            "gateway_updates": self.gateway_updates,
            "pid_rebuilds": self.pid_rebuilds,
            "topology_changes": self.topology_changes,
            "total_messages": self.total_messages,
            "total_bytes": self.total_bytes
        }

def test_basic_functionality():
    """測試基本功能"""
    print("測試 ControlSignalingStats 基本功能...")
    
    # 創建統計對象
    stats = ControlSignalingStats()
    
    # 測試各種記錄方法
    print("1. 測試路由更新記錄...")
    stats.record_routing_update(0, 100, changed_entries=50, total_entries=1000)
    stats.record_routing_update(1, 200, changed_entries=30, total_entries=1000)
    
    print("2. 測試網關更新記錄...")
    stats.record_gateway_update(0, 150, num_gateways=5, num_pids=25)
    stats.record_gateway_update(1, 250, num_gateways=7, num_pids=25, bytes=200)
    
    print("3. 測試PID重建記錄...")
    stats.record_pid_rebuild(1, 300, num_pids=25, changed_pids=5)
    
    print("4. 測試拓撲變化記錄...")
    stats.record_topology_change(1, 350, delta_isl=10, delta_gsl=-2)
    
    print("5. 測試通用事件記錄...")
    stats.record_event("custom_event", 2, 400, count=3, bytes=120, 
                      detail={"source": "test", "type": "custom"})
    
    # 獲取基本統計
    basic_stats = stats.get_stats()
    print(f"\n基本統計: {basic_stats}")
    
    # 獲取詳細摘要
    summary = stats.get_stats_summary()
    print(f"\n詳細摘要: {summary}")
    
    # 測試時間窗口過濾
    window_summary = stats.get_stats_summary(start_time_ms=150, end_time_ms=350)
    print(f"\n時間窗口摘要 (150-350ms): {window_summary}")
    
    # 獲取CSV數據
    csv_data = stats.get_timeline_csv()
    print(f"\nCSV數據樣本:\n{csv_data[:500]}...")
    
    print("✓ 基本功能測試完成")
    return stats

def generate_sample_data():
    """生成示例數據用於演示"""
    print("\n生成示例統計數據...")
    
    # 模擬兩個不同的算法
    algos = {
        "hierarchical_pid": ControlSignalingStats(),
        "baseline_shortest_path": ControlSignalingStats()
    }
    
    # 模擬100個時間點的數據
    for snapshot in range(100):
        sim_time_ms = snapshot * 100  # 每100ms一個快照
        
        # 算法1 (hierarchical_pid) - 較少的路由更新，但更多的網關管理
        if snapshot % 5 == 0:  # 每5個快照更新一次路由
            algos["hierarchical_pid"].record_routing_update(
                snapshot, sim_time_ms, 
                changed_entries=20 + snapshot % 30,  # 變化的條目數
                total_entries=1000
            )
        
        if snapshot % 10 == 0:  # 每10個快照更新網關
            algos["hierarchical_pid"].record_gateway_update(
                snapshot, sim_time_ms,
                num_gateways=5 + snapshot % 10,
                num_pids=25
            )
        
        if snapshot % 25 == 0:  # 每25個快照重建PID
            algos["hierarchical_pid"].record_pid_rebuild(
                snapshot, sim_time_ms,
                num_pids=25,
                changed_pids=3 + snapshot % 5
            )
        
        # 算法2 (baseline) - 更頻繁的路由更新，無網關管理
        if snapshot % 2 == 0:  # 每2個快照更新路由
            algos["baseline_shortest_path"].record_routing_update(
                snapshot, sim_time_ms,
                changed_entries=80 + snapshot % 50,  # 更多變化
                total_entries=1000
            )
        
        # 兩個算法都有拓撲變化
        if snapshot % 20 == 0:
            for algo_name in algos:
                algos[algo_name].record_topology_change(
                    snapshot, sim_time_ms,
                    delta_isl=5 + snapshot % 10,
                    delta_gsl=-(snapshot % 3)
                )
    
    # 保存統計數據
    output_dir = "test_log_output"
    os.makedirs(output_dir, exist_ok=True)
    
    for algo_name, stats in algos.items():
        filepath = os.path.join(output_dir, f"{algo_name}_signaling_stats.txt")
        stats.save_stats_to_file(filepath)
        print(f"✓ 保存 {algo_name} 統計數據到: {filepath}")
        
        # 顯示摘要統計
        summary = stats.get_stats_summary()
        print(f"  {algo_name}: {summary['total_events']} 事件, {summary['total_bytes']} 字節")
    
    return algos

def show_comparison_summary(algos):
    """顯示算法比較摘要"""
    print(f"\n=== 算法比較摘要 ===")
    
    algo_names = list(algos.keys())
    if len(algo_names) >= 2:
        algo1, algo2 = algo_names[0], algo_names[1]
        stats1 = algos[algo1].get_stats_summary()
        stats2 = algos[algo2].get_stats_summary()
        
        bytes_diff = stats2['total_bytes'] - stats1['total_bytes']
        events_diff = stats2['total_events'] - stats1['total_events']
        
        print(f"{algo1}:")
        print(f"  總事件: {stats1['total_events']}")
        print(f"  總字節: {stats1['total_bytes']:,}")
        
        print(f"\n{algo2}:")
        print(f"  總事件: {stats2['total_events']}")
        print(f"  總字節: {stats2['total_bytes']:,}")
        
        print(f"\n差異:")
        print(f"  事件差異: {events_diff:+}")
        print(f"  字節差異: {bytes_diff:+} ({bytes_diff/stats1['total_bytes']*100:+.1f}%)")
        
        # 按事件類型比較
        print(f"\n按事件類型:")
        all_types = set(stats1['by_type'].keys()) | set(stats2['by_type'].keys())
        for event_type in sorted(all_types):
            count1 = stats1['by_type'].get(event_type, {}).get('count', 0)
            count2 = stats2['by_type'].get(event_type, {}).get('count', 0)
            bytes1 = stats1['by_type'].get(event_type, {}).get('bytes', 0)
            bytes2 = stats2['by_type'].get(event_type, {}).get('bytes', 0)
            
            print(f"  {event_type}:")
            print(f"    {algo1}: {count1} 次, {bytes1} 字節")
            print(f"    {algo2}: {count2} 次, {bytes2} 字節")
            print(f"    差異: {count2-count1:+} 次, {bytes2-bytes1:+} 字節")

def main():
    print("=== 控制信令統計功能測試 ===\n")
    
    # 測試基本功能
    stats = test_basic_functionality()
    
    # 生成示例數據
    algos = generate_sample_data()
    
    # 顯示比較摘要
    show_comparison_summary(algos)
    
    print(f"\n=== 測試完成 ===")
    print("生成的文件:")
    print("- test_log_output/hierarchical_pid_signaling_stats.txt")
    print("- test_log_output/baseline_shortest_path_signaling_stats.txt")
    print("\n下一步：")
    print("1. 運行 'python analyze_signaling_stats.py --algo1 hierarchical_pid --plot' 查看可視化")
    print("2. 運行 'python analyze_signaling_stats.py --algo1 hierarchical_pid --algo2 baseline_shortest_path --plot' 比較算法")
    print("3. 在實際的Hypatia模擬中集成統計收集")

if __name__ == '__main__':
    main()