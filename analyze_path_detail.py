#!/usr/bin/env python3
"""
從算法中直接分析Virtual PID路徑中衛星的群組歸屬
"""

import sys
import os
import math
import ephem
from datetime import datetime, timezone
from astropy.time import Time
import numpy as np

# 重現VirtualPIDRouter的邏輯
class VirtualPIDRouter:
    def __init__(self, grid_deg: int = 10, lon_min: int = -180, lon_max: int = 180,
                 lat_min: int = -90, lat_max: int = 90, allow_diagonal_neighbor: bool = True):
        self.grid_deg = grid_deg
        self.lon_min, self.lon_max = lon_min, lon_max
        self.lat_min, self.lat_max = lat_min, lat_max
        self.allow_diag = allow_diagonal_neighbor
        
        # Static
        self.pids = []
        self.pid_index = {}
        self.pid_neighbors = {}
        
        # Dynamic
        self.pid_agent_sat = {}
        self.pid_members = {}
        
        self._build_static_pid_grid()

    def _build_static_pid_grid(self):
        lat_bins = list(range(self.lat_min, self.lat_max, self.grid_deg))
        lon_bins = list(range(self.lon_min, self.lon_max, self.grid_deg))
        for i, lat in enumerate(lat_bins):
            for j, lon in enumerate(lon_bins):
                pid = (i, j)
                idx = len(self.pids)
                self.pids.append(pid)
                self.pid_index[pid] = idx
        for (i, j), u in self.pid_index.items():
            nbrs = []
            dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if self.allow_diag:
                dirs += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            for di, dj in dirs:
                ii, jj = i + di, j + dj
                if (ii, jj) in self.pid_index:
                    nbrs.append(self.pid_index[(ii, jj)])
            self.pid_neighbors[u] = set(nbrs)

    def latlon_to_pid(self, lat, lon):
        if not (self.lat_min <= lat < self.lat_max and self.lon_min <= lon < self.lon_max):
            return None
        gi = int((lat - self.lat_min) // self.grid_deg)
        gj = int((lon - self.lon_min) // self.grid_deg)
        return self.pid_index.get((gi, gj))

def simulate_satellite_positions():
    """模擬衛星位置來獲得PID分配"""
    
    # 讀取TLE數據
    tle_file = "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_fast/tles.txt"
    
    if not os.path.exists(tle_file):
        print("找不到TLE文件，使用網格估計方法")
        return estimate_satellite_pids()
    
    print("讀取TLE文件進行精確分析...")
    satellites = []
    
    with open(tle_file, 'r') as f:
        lines = f.readlines()
        
    for i in range(0, len(lines), 3):
        if i + 2 < len(lines):
            name = lines[i].strip()
            tle1 = lines[i + 1].strip()
            tle2 = lines[i + 2].strip()
            
            if tle1.startswith('1') and tle2.startswith('2'):
                sat = ephem.readtle(name, tle1, tle2)
                satellites.append(sat)
    
    print(f"讀取了 {len(satellites)} 顆衛星的TLE數據")
    
    # 設定時間（2018-06-10 14:19:34.624 UTC）
    epoch = ephem.Date('2018/6/10 14:19:34.624')
    
    # 初始化路由器
    router = VirtualPIDRouter(grid_deg=10)
    
    # 計算每顆衛星在t=0時的位置和PID
    sat_to_pid = {}
    pid_to_sats = {u: set() for u in range(len(router.pids))}
    
    for sat_id, sat in enumerate(satellites):
        if sat_id >= 1584:  # 只處理前1584顆衛星
            break
            
        sat.compute(epoch)
        lat = float(sat.sublat) * 180.0 / math.pi
        lon = float(sat.sublong) * 180.0 / math.pi
        
        if lon >= 180: 
            lon -= 360
        if lon < -180: 
            lon += 360
            
        pid = router.latlon_to_pid(lat, lon)
        if pid is not None:
            sat_to_pid[sat_id] = pid
            pid_to_sats[pid].add(sat_id)
    
    # 確定每個PID的agent（最小衛星ID）
    pid_to_agent = {}
    for pid, members in pid_to_sats.items():
        if members:
            pid_to_agent[pid] = min(members)
    
    return sat_to_pid, pid_to_agent, pid_to_sats

def estimate_satellite_pids():
    """基於已知衛星ID估計PID分配"""
    print("使用估計方法分析...")
    
    # 基於25x25網格的典型分配模式
    # 這是一個簡化的估計，實際需要TLE數據
    sat_to_pid = {}
    pid_to_agent = {}
    
    # 從路徑中觀察到的模式進行估計
    known_agents = {
        189: "Group_A",  # 經常出現在路徑開始
        188: "Group_B",  # t=30.6s時的替代agent
        163: "Group_C",
        164: "Group_D", 
        138: "Group_E",
        139: "Group_F",
        137: "Group_G",
        112: "Group_H",
        111: "Group_I",
    }
    
    return known_agents, {}, {}

def analyze_path_satellites():
    # 路徑數據
    paths = {
        "625→626 (t=0)": [625, 189, 163, 137, 111, 85, 86, 60, 61, 62, 63, 64, 626],
        "625→626 (t=30.6s)": [625, 188, 189, 163, 164, 138, 112, 86, 60, 61, 62, 63, 64, 626],
        "625→627 (t=0)": [625, 189, 163, 164, 138, 139, 627],
        "625→627 (t=30.6s)": [625, 188, 189, 163, 164, 138, 139, 627]
    }
    
    print("Virtual PID 路徑分析報告")
    print("=" * 60)
    
    try:
        sat_to_pid, pid_to_agent, pid_to_sats = simulate_satellite_positions()
        
        # 分析每條路徑
        for path_name, path in paths.items():
            print(f"\n路徑: {path_name}")
            print("-" * 40)
            print(f"完整路徑: {' → '.join(map(str, path))}")
            print("\n衛星分析:")
            
            satellites_in_path = [sat for sat in path if sat < 1584]
            
            for sat in satellites_in_path:
                pid = sat_to_pid.get(sat, "未知")
                if pid != "未知" and pid in pid_to_agent:
                    agent = pid_to_agent[pid]
                    is_master = "🔸 Master" if sat == agent else "• 一般衛星"
                    print(f"  衛星 {sat:3d} - PID {pid:3d} - {is_master}")
                else:
                    print(f"  衛星 {sat:3d} - PID 未知")
    
    except Exception as e:
        print(f"分析過程中出錯: {e}")
        print("\n使用簡化分析方法:")
        analyze_simplified()

def analyze_simplified():
    """簡化分析 - 基於觀察到的模式"""
    paths = {
        "625→626 (t=0)": [625, 189, 163, 137, 111, 85, 86, 60, 61, 62, 63, 64, 626],
        "625→626 (t=30.6s)": [625, 188, 189, 163, 164, 138, 112, 86, 60, 61, 62, 63, 64, 626],
        "625→627 (t=0)": [625, 189, 163, 164, 138, 139, 627],
        "625→627 (t=30.6s)": [625, 188, 189, 163, 164, 138, 139, 627]
    }
    
    # 基於Virtual PID算法的特性，這些衛星很可能是agent（master）
    likely_agents = {189, 188, 163, 164, 138, 139, 137, 112, 111}
    
    for path_name, path in paths.items():
        print(f"\n路徑: {path_name}")
        print("-" * 40)
        satellites_in_path = [sat for sat in path if sat < 1584]
        
        agents_in_path = [sat for sat in satellites_in_path if sat in likely_agents]
        regular_sats = [sat for sat in satellites_in_path if sat not in likely_agents]
        
        print(f"Agent衛星 (Masters): {agents_in_path}")
        print(f"一般衛星: {regular_sats}")
        print(f"跨越群組數量: ~{len(agents_in_path)} 個")

if __name__ == "__main__":
    analyze_path_satellites()