# The MIT License (MIT)
#
# Copyright (c) 2020 ETH Zurich
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from .fstate_calculation import *
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import json
import os
from datetime import datetime

# ===== 控制信令統計功能 (參考 algorithm_hierarchical_virtual_pid.py) =====

@dataclass
class EventRow:
    """單個控制信令事件記錄"""
    snapshot: int         # 快照索引
    sim_time_ms: int     # 模擬時間（毫秒） - 統一字段名稱
    event: str           # 事件類型 - 統一字段名稱
    count: int = 1       # 事件數量
    detail: Optional[Dict[str, Any]] = None  # 詳細信息
    bytes: int = 0       # 控制信令字節數

class ControlSignalingStats:
    """控制信令統計收集器 - 基線算法版本"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置所有統計數據"""
        self.routing_updates = 0
        self.topology_changes = 0
        self.total_messages = 0
        self.total_bytes = 0
        self.timeline: List[EventRow] = []
    
    def _append(self, event: EventRow):
        """添加事件到時間軸 - 統一邏輯，避免雙重累加"""
        self.timeline.append(event)
        self.total_messages += event.count
        self.total_bytes += event.bytes
    
    def record_routing_update(self, snapshot, sim_time_ms, 
                              changed_entries:int, total_entries:int,
                              bytes=None, base_bytes:int=32, per_entry_bytes:int=8):
        """記錄路由更新事件 - Floyd-Warshall 全網重計算"""
        self.routing_updates += 1
        if bytes is None:
            # Floyd-Warshall 需要全網路由矩陣交換
            b = base_bytes + changed_entries * per_entry_bytes
        else:
            b = bytes
        
        # 不再雙重累加 - _append 已經處理 count 增加
        self._append(EventRow(snapshot, sim_time_ms, "routing_update",
                              count=1,
                              detail={"changed_entries": changed_entries, 
                                     "total_entries": total_entries,
                                     "algorithm": "floyd_warshall"},
                              bytes=b))
    
    def record_topology_change(self, snapshot, sim_time_ms,
                               delta_isl:int, delta_gsl:int, per_edge_bytes:int=16):
        """記錄拓撲變化"""
        self.topology_changes += 1
        b = (abs(delta_isl) + abs(delta_gsl)) * per_edge_bytes
        self._append(EventRow(snapshot, sim_time_ms, "topology_change",
                              count=1,
                              detail={"delta_isl": delta_isl, "delta_gsl": delta_gsl,
                                     "algorithm": "baseline_floyd_warshall"},
                              bytes=b))
    
    def get_stats_summary(self, start_time_ms=None, end_time_ms=None):
        """獲取統計摘要"""
        events = self.timeline
        if start_time_ms is not None:
            events = [e for e in events if e.time_ms >= start_time_ms]
        if end_time_ms is not None:
            events = [e for e in events if e.time_ms <= end_time_ms]
        
        by_type = {}
        total_bytes = 0
        total_count = 0
        
        for event in events:
            if event.event not in by_type:
                by_type[event.event] = {"count": 0, "bytes": 0}
            by_type[event.event]["count"] += event.count
            by_type[event.event]["bytes"] += event.bytes
            total_bytes += event.bytes
            total_count += event.count
        
        return {
            "total_events": total_count,
            "total_bytes": total_bytes,
            "by_type": by_type,
            "algorithm": "baseline_floyd_warshall"
        }
    
    def get_timeline_csv(self):
        """獲取時間軸數據的CSV格式字符串"""
        import io
        output = io.StringIO()
        output.write("snapshot,time_ms,event_type,count,bytes,detail\n")
        for event in self.timeline:
            detail_str = str(event.detail) if event.detail else ""
            output.write(f"{event.snapshot},{event.sim_time_ms},{event.event},{event.count},{event.bytes},\"{detail_str}\"\n")
        return output.getvalue()
    
    def save_stats_to_file(self, filepath, include_timeline=True):
        """將統計數據保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=== 基線算法控制信令統計摘要 (Floyd-Warshall) ===\n")
            summary = self.get_stats_summary()
            f.write(f"總事件數: {summary['total_events']}\n")
            f.write(f"總字節數: {summary['total_bytes']}\n")
            f.write("\n各類型事件:\n")
            for event_type, stats in summary['by_type'].items():
                f.write(f"  {event_type}: {stats['count']} 次, {stats['bytes']} 字節\n")
            
            if include_timeline:
                f.write("\n=== 事件時間軸 ===\n")
                f.write(self.get_timeline_csv())

# 全局統計對象
_BASELINE_SIGNALING_STATS = ControlSignalingStats()

def get_baseline_signaling_stats():
    """獲取基線算法控制信令統計數據"""
    global _BASELINE_SIGNALING_STATS
    return _BASELINE_SIGNALING_STATS.get_stats_summary()

def save_baseline_signaling_stats(filepath):
    """保存基線算法控制信令統計數據到文件"""
    global _BASELINE_SIGNALING_STATS
    _BASELINE_SIGNALING_STATS.save_stats_to_file(filepath)


def algorithm_free_one_only_over_isls(
        output_dynamic_state_dir,
        time_since_epoch_ns,
        satellites,
        ground_stations,
        sat_net_graph_only_satellites_with_isls,
        ground_station_satellites_in_range,
        num_isls_per_sat,
        sat_neighbor_to_if,
        list_gsl_interfaces_info,
        prev_output,
        enable_verbose_logs
):
    """
    FREE-ONE ONLY OVER INTER-SATELLITE LINKS ALGORITHM WITH SIGNALING STATS

    "one"
    This algorithm assumes that every satellite and ground station has exactly 1 GSL interface.

    "free"
    This 1 interface is bound to a maximum outgoing bandwidth, but can send to any other
    GSL interface (well, satellite -> ground-station, and ground-station -> satellite) in
    range. ("free") There is no reciprocation of the bandwidth asserted.

    "only_over_isls"
    It calculates a forwarding state, which is essentially a single shortest path.
    It only considers paths which go over the inter-satellite network, and does not make use of ground
    stations relay. This means that every path looks like:
    (src gs) - (sat) - (sat) - ... - (sat) - (dst gs)

    控制信令統計：
    - 使用 Floyd-Warshall 算法，每次快照都需要全網路由矩陣重計算
    - 相比分層路由有更高的控制開銷
    """
    
    global _BASELINE_SIGNALING_STATS

    if enable_verbose_logs:
        print("\nALGORITHM: FREE ONE ONLY OVER ISLS (WITH SIGNALING STATS)")

    # 統計準備
    snapshot = getattr(_BASELINE_SIGNALING_STATS, '_current_snapshot', 0)
    sim_time_ms = time_since_epoch_ns // 1000000  # 轉換為毫秒
    _BASELINE_SIGNALING_STATS._current_snapshot = snapshot + 1

    # Check the graph
    if sat_net_graph_only_satellites_with_isls.number_of_nodes() != len(satellites):
        raise ValueError("Number of nodes in the graph does not match the number of satellites")
    for sid in range(len(satellites)):
        for n in sat_net_graph_only_satellites_with_isls.neighbors(sid):
            if n >= len(satellites):
                raise ValueError("Graph cannot contain satellite-to-ground-station links")

    #################################
    # BANDWIDTH STATE
    #

    # There is only one GSL interface for each node (pre-condition), which as-such will get the entire bandwidth
    output_filename = output_dynamic_state_dir + "/gsl_if_bandwidth_" + str(time_since_epoch_ns) + ".txt"
    if enable_verbose_logs:
        print("  > Writing interface bandwidth state to: " + output_filename)
    with open(output_filename, "w+") as f_out:
        if time_since_epoch_ns == 0:
            for node_id in range(len(satellites)):
                f_out.write("%d,%d,%f\n"
                            % (node_id, num_isls_per_sat[node_id],
                               list_gsl_interfaces_info[node_id]["aggregate_max_bandwidth"]))
            for node_id in range(len(satellites), len(satellites) + len(ground_stations)):
                f_out.write("%d,%d,%f\n"
                            % (node_id, 0, list_gsl_interfaces_info[node_id]["aggregate_max_bandwidth"]))

    #################################
    # FORWARDING STATE
    #

    # Previous forwarding state (to only write delta)
    prev_fstate = None
    if prev_output is not None:
        prev_fstate = prev_output["fstate"]

    # GID to satellite GSL interface index
    gid_to_sat_gsl_if_idx = [0] * len(ground_stations)  # (Only one GSL interface per satellite, so the first)

    # [統計記錄] Floyd-Warshall 全網路由重計算
    # 每次調用都需要重新計算所有節點對之間的最短路徑
    num_satellites = len(satellites)
    num_ground_stations = len(ground_stations)
    total_node_pairs = num_satellites * num_satellites  # Floyd-Warshall 計算量
    
    # 計算有多少路由條目會被更新
    if prev_fstate is None:
        # 首次計算，所有路由都是新的
        changed_entries = num_satellites * num_ground_stations * 2  # 上行+下行
    else:
        # 後續計算，估算變化量（基於拓撲變化）
        # Floyd-Warshall 特點：任何邊的變化都可能影響所有路徑
        edge_count = sat_net_graph_only_satellites_with_isls.number_of_edges()
        # 保守估計：每個邊的變化影響 10% 的路由
        changed_entries = int((num_satellites * num_ground_stations * 2) * 0.3)
    
    total_entries = num_satellites * num_ground_stations * 2
    
    # 記錄路由更新統計 - Floyd-Warshall 的控制開銷特別大
    _BASELINE_SIGNALING_STATS.record_routing_update(
        snapshot, sim_time_ms,
        changed_entries=changed_entries,
        total_entries=total_entries,
        base_bytes=64,  # Floyd-Warshall 需要更多控制信息
        per_entry_bytes=12  # 每個路由條目更大（包含距離矩陣信息）
    )

    if enable_verbose_logs:
        print(f"  > [SIGNALING] Floyd-Warshall 路由更新: {changed_entries}/{total_entries} 條目")

    # Forwarding state using shortest paths
    fstate = calculate_fstate_shortest_path_without_gs_relaying(
        output_dynamic_state_dir,
        time_since_epoch_ns,
        len(satellites),
        len(ground_stations),
        sat_net_graph_only_satellites_with_isls,
        num_isls_per_sat,
        gid_to_sat_gsl_if_idx,
        ground_station_satellites_in_range,
        sat_neighbor_to_if,
        prev_fstate,
        enable_verbose_logs
    )

    # [統計記錄] 檢測拓撲變化
    if snapshot > 0:  # 第一個快照沒有拓撲變化
        # 簡化的拓撲變化檢測 - 基於邊數變化
        current_edges = sat_net_graph_only_satellites_with_isls.number_of_edges()
        prev_edges = getattr(_BASELINE_SIGNALING_STATS, '_prev_edge_count', current_edges)
        
        delta_isl = current_edges - prev_edges
        delta_gsl = 0  # 這個算法不處理GSL變化
        
        if delta_isl != 0:
            _BASELINE_SIGNALING_STATS.record_topology_change(
                snapshot, sim_time_ms,
                delta_isl=delta_isl,
                delta_gsl=delta_gsl
            )
            if enable_verbose_logs:
                print(f"  > [SIGNALING] 拓撲變化: ISL {delta_isl:+}")
        
        _BASELINE_SIGNALING_STATS._prev_edge_count = current_edges

    if enable_verbose_logs:
        print("")
        # 輸出當前統計摘要
        stats_summary = _BASELINE_SIGNALING_STATS.get_stats_summary()
        print(f"  > [SIGNALING] 累計統計: {stats_summary['total_events']} 事件, {stats_summary['total_bytes']} 字節")

    # 統一輸出統計文件到 analytic_result 目錄
    stats_output_dir = "analytic_result"
    os.makedirs(stats_output_dir, exist_ok=True)
    stats_file = os.path.join(stats_output_dir, "baseline_floyd_warshall_signaling_stats.json")
    
    try:
        
        # 保存詳細統計到 JSON 文件
        detailed_stats = {
            "algorithm": "algorithm_free_one_only_over_isls_with_stats",
            "algorithm_display_name": "Floyd-Warshall Baseline",
            "timestamp": datetime.now().isoformat(),
            "summary": _BASELINE_SIGNALING_STATS.get_stats_summary(),
            "timeline": [
                {
                    "snapshot": row.snapshot,
                    "time_ms": row.sim_time_ms,
                    "event": row.event,
                    "count": row.count,
                    "bytes": row.bytes,
                    "detail": row.detail
                }
                for row in _BASELINE_SIGNALING_STATS.timeline
            ]
        }
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(detailed_stats, f, indent=2, ensure_ascii=False)
            
        if enable_verbose_logs:
            print(f"  > [STATS] Saved signaling stats to {stats_file}")
    except Exception as e:
        if enable_verbose_logs:
            print(f"  > [STATS-ERROR] Failed to save stats: {e}")

    return {
        "fstate": fstate,
        "signaling_stats": _BASELINE_SIGNALING_STATS.get_stats_summary()
    }
