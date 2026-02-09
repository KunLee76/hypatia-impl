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
import threading
from datetime import datetime
import random
import sys

# ===== Chaos Monkey 配置（間歇性ISL失效）=====
ENABLE_CHAOS_MONKEY = os.environ.get('ENABLE_CHAOS_MONKEY', 'false').lower() == 'true'
CHAOS_FAILURE_RATE = float(os.environ.get('CHAOS_FAILURE_RATE', '0.01'))  # 預設1%
CHAOS_INTERVAL_SNAPSHOTS = int(os.environ.get('CHAOS_INTERVAL_SNAPSHOTS', '20'))  # 預設20 snapshots
CHAOS_LOG_FILE = os.environ.get('CHAOS_LOG_FILE', 'chaos_monkey_baseline.log')  # Chaos Monkey專用日誌

def chaos_monkey_inject_failures(G_sat_isls, snapshot_idx, failure_rate, log_file='chaos_monkey_baseline.log'):
    """
    Chaos Monkey: 在當前snapshot隨機移除指定比例的ISL
    
    Args:
        G_sat_isls: NetworkX圖，ISL拓撲
        snapshot_idx: 當前snapshot索引
        failure_rate: 失效率 (0.0-1.0)
        log_file: 日誌文件路徑
    
    Returns:
        removed_edges: 被移除的邊列表 [(u, v), ...]
    """
    if not G_sat_isls or G_sat_isls.number_of_edges() == 0:
        return []
    
    # 獲取所有ISL邊
    all_isls = [(u, v) for u, v in G_sat_isls.edges()]
    
    if not all_isls:
        return []
    
    # 計算要移除的數量
    num_to_remove = max(1, int(len(all_isls) * failure_rate))
    
    # 隨機選擇要移除的ISL
    edges_to_remove = random.sample(all_isls, num_to_remove)
    
    # 從圖中移除這些邊
    removed_count = 0
    for u, v in edges_to_remove:
        if G_sat_isls.has_edge(u, v):
            G_sat_isls.remove_edge(u, v)
            removed_count += 1
    
    # 記錄到日誌
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "Z"
    log_msg = (f"{timestamp} [CHAOS_MONKEY] Snapshot={snapshot_idx} "
               f"Total_ISLs={len(all_isls)} Removed={removed_count} Rate={failure_rate:.2%}\n")
    
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg)
            # 記錄每條被移除的ISL詳細信息
            for u, v in edges_to_remove:
                f.write(f"  - ISL removed: {u} <-> {v}\n")
    except Exception as e:
        print(f"Warning: Could not write to Chaos Monkey log: {e}", file=sys.stderr)
    
    return edges_to_remove

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
        self._recorded_snapshots: Set[int] = set()  # 追蹤已記錄的 snapshot（去重）
    
    def _append(self, event: EventRow):
        """添加事件到時間軸 - 統一邏輯，避免雙重累加"""
        self.timeline.append(event)
        self.total_messages += event.count
        self.total_bytes += event.bytes
    
    def record_routing_update(self, snapshot, sim_time_ms, 
                              changed_entries:int, total_entries:int,
                              bytes=None):
        """記錄路由更新事件 - Floyd-Warshall 全網重計算
        
        Note:
            bytes 計算交給 analyzer 統一處理（HDR + changed_entries*ENTRY）
            每個 snapshot 只記錄一次，避免重複計數
        """
        # 去重檢查：每個 snapshot 只記錄一次
        if snapshot in self._recorded_snapshots:
            return
        self._recorded_snapshots.add(snapshot)
        
        self.routing_updates += 1
        # bytes 設為提供值或 0（讓 analyzer 計算）
        b = bytes if bytes is not None else 0
        
        # 不再雙重累加 - _append 已經處理 count 增加
        self._append(EventRow(snapshot, sim_time_ms, "routing_update",
                              count=1,
                              detail={"changed_entries": changed_entries, 
                                     "total_entries": total_entries,
                                     "algorithm": "floyd_warshall"},
                              bytes=b))
    
    def record_topology_change(self, snapshot, sim_time_ms,
                               delta_isl:int, delta_gsl:int, bytes=None,
                               isl_removed:int=0, isl_added:int=0):
        """記錄拓撲變化
        
        Note:
            bytes 計算交給 analyzer 統一處理（HDR + (|delta_isl|+|delta_gsl|)*ENTRY）
        """
        self.topology_changes += 1
        b = bytes if bytes is not None else 0
        self._append(EventRow(snapshot, sim_time_ms, "topology_change",
                              count=1,
                              detail={"delta_isl": delta_isl, "delta_gsl": delta_gsl,
                                     "isl_removed": isl_removed, "isl_added": isl_added,
                                     "algorithm": "baseline_floyd_warshall"},
                              bytes=b))
    
    def get_stats_summary(self, start_time_ms=None, end_time_ms=None):
        """獲取統計摘要"""
        events = self.timeline
        if start_time_ms is not None:
            events = [e for e in events if e.sim_time_ms >= start_time_ms]
        if end_time_ms is not None:
            events = [e for e in events if e.sim_time_ms <= end_time_ms]
        
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

# Process-local 統計對象 (每個進程維護自己的統計)
_thread_local = threading.local()

def _get_process_local_stats():
    """獲取當前進程的統計對象"""
    if not hasattr(_thread_local, 'stats'):
        _thread_local.stats = ControlSignalingStats()
    return _thread_local.stats

def get_baseline_signaling_stats():
    """獲取基線算法控制信令統計數據"""
    return _get_process_local_stats().get_stats_summary()

def save_baseline_signaling_stats(filepath):
    """保存基線算法控制信令統計數據到文件"""
    _get_process_local_stats().save_stats_to_file(filepath)


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
        enable_verbose_logs,
        time_step_ns=None  # 新增：時間步長（納秒），用於計算 snapshot 索引
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

    if enable_verbose_logs:
        print("\nALGORITHM: FREE ONE ONLY OVER ISLS (WITH SIGNALING STATS)")

    # 統計準備：從 time_since_epoch_ns 計算正確的 snapshot 索引
    # 避免使用 process-local 計數器造成的並行執行問題
    sim_time_ms = time_since_epoch_ns // 1000000  # 轉換為毫秒
    if time_step_ns is not None and time_step_ns > 0:
        snapshot = int(time_since_epoch_ns / time_step_ns)
    else:
        # 預設 100ms per snapshot
        snapshot = int(time_since_epoch_ns / 100_000_000)  # 100ms = 100M ns

    # Check the graph
    if sat_net_graph_only_satellites_with_isls.number_of_nodes() != len(satellites):
        raise ValueError("Number of nodes in the graph does not match the number of satellites")
    for sid in range(len(satellites)):
        for n in sat_net_graph_only_satellites_with_isls.neighbors(sid):
            if n >= len(satellites):
                raise ValueError("Graph cannot contain satellite-to-ground-station links")
    
    # ========================================
    # 🐒 CHAOS MONKEY: 間歇性ISL失效注入
    # ========================================
    chaos_monkey_removed_count = 0
    if ENABLE_CHAOS_MONKEY and (snapshot % CHAOS_INTERVAL_SNAPSHOTS == 0):
        removed_isls = chaos_monkey_inject_failures(
            sat_net_graph_only_satellites_with_isls, 
            snapshot, 
            CHAOS_FAILURE_RATE,
            CHAOS_LOG_FILE
        )
        chaos_monkey_removed_count = len(removed_isls)
        if enable_verbose_logs:
            print(f"  > [CHAOS_MONKEY] Injected {chaos_monkey_removed_count} ISL failures at snapshot {snapshot}")
    # ========================================

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
    total_entries = num_satellites * num_ground_stations * 2  # 上行+下行

    # Forwarding state using shortest paths（先計算 fstate，再統計變化量）
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

    # [統計記錄] 計算實際的路由變化量（與 GRHR/LoHi 一致的方式）
    # 比較前後 fstate 的差異，計算實際變化的路由條目數
    flat_fstate = {(u, dst): nh[0] for (u, dst), nh in fstate.items()} if fstate else {}
    changed_entries = 0
    
    if hasattr(_get_process_local_stats(), '_prev_flat_fstate') and _get_process_local_stats()._prev_flat_fstate:
        prev_flat = _get_process_local_stats()._prev_flat_fstate
        all_keys = set(prev_flat.keys()) | set(flat_fstate.keys())
        for k in all_keys:
            if prev_flat.get(k) != flat_fstate.get(k):
                changed_entries += 1
    else:
        # 首次計算，所有路由都是新的
        changed_entries = len(flat_fstate)
    
    _get_process_local_stats()._prev_flat_fstate = flat_fstate
    
    # 記錄路由更新統計
    if changed_entries > 0:
        _get_process_local_stats().record_routing_update(
            snapshot, sim_time_ms,
            changed_entries=changed_entries,
            total_entries=total_entries
        )
        if enable_verbose_logs:
            print(f"  > [SIGNALING] Floyd-Warshall 路由更新: {changed_entries}/{total_entries} 條目變化")

    # [統計記錄] 檢測拓撲變化
    # 追蹤實際的拓撲變化（包括 Chaos Monkey 移除和自然重建）
    current_edges = sat_net_graph_only_satellites_with_isls.number_of_edges()
    prev_edges = getattr(_get_process_local_stats(), '_prev_edge_count', None)
    
    if prev_edges is not None:
        # 淨變化 = 當前邊數 - 前一個邊數
        delta_isl = current_edges - prev_edges
        delta_gsl = 0  # 這個算法不處理GSL變化
        
        # 計算實際的添加和移除數量
        # 淨變化 = 添加 - 移除，因此：添加 = 移除 + 淨變化
        isl_removed = chaos_monkey_removed_count
        isl_added = isl_removed + delta_isl
        
        # 只要有任何變化就記錄（移除或添加）
        if isl_removed > 0 or isl_added > 0 or delta_isl != 0:
            _get_process_local_stats().record_topology_change(
                snapshot, sim_time_ms,
                delta_isl=delta_isl,
                delta_gsl=delta_gsl,
                isl_removed=isl_removed,
                isl_added=isl_added
            )
            if enable_verbose_logs:
                print(f"  > [SIGNALING] 拓撲變化: ISL 淨變化={delta_isl:+}, 移除={isl_removed}, 添加={isl_added}")
    
    _get_process_local_stats()._prev_edge_count = current_edges

    if enable_verbose_logs:
        print("")
        # 輸出當前統計摘要
        stats_summary = _get_process_local_stats().get_stats_summary()
        print(f"  > [SIGNALING] 累計統計: {stats_summary['total_events']} 事件, {stats_summary['total_bytes']} 字節")

    # Process-local 輸出：使用臨時文件，帶進程/線程ID
    import threading
    thread_id = threading.get_ident()
    pid = os.getpid()
    
    # 統計輸出目錄 - 總是使用當前工作目錄下的 analytic_result
    # 腳本運行在 paper/satellite_networks_state/ 目錄
    # 避免路徑重複問題（如 paper/satellite_networks_state/paper/satellite_networks_state/...）
    stats_output_dir = os.path.abspath("analytic_result")
    os.makedirs(stats_output_dir, exist_ok=True)
    
    # 從 output_dynamic_state_dir 或環境變數提取場景資訊，避免不同實驗混淆
    import re
    output_dir = output_dynamic_state_dir if output_dynamic_state_dir else ""
    scenario_info = ""
    
    # 優先從路徑提取場景資訊
    if "isls_failure_" in output_dir:
        match = re.search(r'isls_failure_(l\d+)', output_dir)
        if match:
            scenario_info = f"_failure_{match.group(1)}"
    elif "isls_random_" in output_dir:
        match = re.search(r'isls_random_(p\d+)', output_dir)
        if match:
            scenario_info = f"_random_{match.group(1)}"
    elif "isls_dynamic_" in output_dir:
        match = re.search(r'isls_dynamic_(p\d+)', output_dir)
        if match:
            scenario_info = f"_dynamic_{match.group(1)}"
    
    # 如果啟用了 Chaos Monkey 但沒有從路徑識別出場景，從失效率推斷
    if not scenario_info and ENABLE_CHAOS_MONKEY:
        rate = CHAOS_FAILURE_RATE
        if rate == 0.01:
            scenario_info = "_dynamic_p1"
        elif rate == 0.05:
            scenario_info = "_dynamic_p5"
        elif rate == 0.10 or rate == 0.1:
            scenario_info = "_dynamic_p10"
    
    # 臨時文件：用於收集各進程的統計數據
    temp_dir_name = f"temp_baseline{scenario_info}"
    temp_dir = os.path.join(stats_output_dir, temp_dir_name)
    os.makedirs(temp_dir, exist_ok=True)
    stats_file = os.path.join(temp_dir, f"baseline_stats_pid{pid}_tid{thread_id}.json")
    
    # 強制輸出調試信息（不依賴 verbose 設置）
    print(f"  > [BASELINE-STATS] scenario_info='{scenario_info}', temp_dir={temp_dir}")
    
    if enable_verbose_logs:
        print(f"  > [DEBUG] output_dir: {output_dir}")
        print(f"  > [DEBUG] scenario_info: '{scenario_info}'")
        print(f"  > [DEBUG] temp_dir_name: {temp_dir_name}")
    
    try:
        
        # 保存詳細統計到 JSON 文件
        detailed_stats = {
            "algorithm": "algorithm_free_one_only_over_isls_with_stats",
            "algorithm_display_name": "Floyd-Warshall Baseline",
            "timestamp": datetime.now().isoformat(),
            "summary": _get_process_local_stats().get_stats_summary(),
            "timeline": [
                {
                    "snapshot": row.snapshot,
                    "time_ms": row.sim_time_ms,
                    "event": row.event,
                    "count": row.count,
                    "bytes": row.bytes,
                    "detail": row.detail
                }
                for row in _get_process_local_stats().timeline
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
        "signaling_stats": _get_process_local_stats().get_stats_summary()
    }
