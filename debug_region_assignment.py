#!/usr/bin/env python3
"""
詳細調試地理分群和master衛星分配
"""

import sys
import os
sys.path.append("satgenpy")

from satgen.post_analysis.graph_tools import get_path
from satgen.dynamic_state.region_grouping import assign_satellites_to_regions, select_master_for_regions
import satgen


def debug_regional_routing(data_dir, time_ns, src_gs, dst_gs, region_size=5.0):
    """
    詳細調試地理分群路由
    """
    
    print(f"\n🔍 詳細調試地理分群路由 GS{src_gs} → GS{dst_gs}")
    print("=" * 70)
    
    # 1. 讀取路由狀態
    fstate_file = f"{data_dir}/fstate_{time_ns}.txt"
    if not os.path.exists(fstate_file):
        print(f"❌ 找不到文件: {fstate_file}")
        return
    
    fstate = {}
    with open(fstate_file, 'r') as f:
        for line in f:
            if line.strip():
                spl = line.strip().split(',')
                current = int(spl[0])
                destination = int(spl[1])
                next_hop = int(spl[2])
                fstate[(current, destination)] = next_hop
    
    print(f"✅ 已載入 {len(fstate)} 條路由規則")
    
    # 2. 獲取路由路徑
    path = get_path(src_gs, dst_gs, fstate)
    if not path:
        print(f"❌ 找不到從 GS{src_gs} 到 GS{dst_gs} 的路由")
        return
    
    print(f"📍 路由路徑: {' → '.join(map(str, path))}")
    print(f"📊 總跳數: {len(path) - 1}")
    
    # 3. 計算衛星位置
    base_dir = "/".join(data_dir.split("/")[:-1])
    tles_file = f"{base_dir}/tles.txt"
    
    if not os.path.exists(tles_file):
        print(f"❌ 找不到TLE文件: {tles_file}")
        return
    
    print(f"📡 正在計算衛星位置...")
    sat_positions = calculate_satellite_positions(tles_file, time_ns)
    print(f"📊 計算得到 {len(sat_positions)} 個衛星位置")
    
    # 4. 地理分群詳細分析
    print(f"\n🌍 地理分群詳細分析 (網格大小: {region_size}° × {region_size}°)")
    print("-" * 50)
    
    # 使用真實的地理分群算法
    sat_to_group, region_to_sats = assign_satellites_to_regions(
        sat_positions, region_size, region_size
    )
    
    print(f"📊 總共識別 {len(region_to_sats)} 個地理區域")
    print(f"📊 衛星分組情況:")
    
    # 顯示每個區域的詳細信息
    for region_id, satellites in sorted(region_to_sats.items()):
        if len(satellites) > 0:
            sample_sats = satellites[:5]  # 只顯示前5個
            more_text = f" (+{len(satellites)-5} more)" if len(satellites) > 5 else ""
            print(f"   區域 {region_id}: {len(satellites)} 個衛星 {sample_sats}{more_text}")
    
    # 5. 分析路由路徑中的衛星分組
    print(f"\n🛤️ 路由路徑中的衛星分組分析:")
    print("-" * 50)
    
    satellite_nodes = [node for node in path if node < 625]
    involved_groups = {}
    
    for sat_id in satellite_nodes:
        group_id = sat_to_group.get(sat_id, -1)
        if group_id not in involved_groups:
            involved_groups[group_id] = []
        involved_groups[group_id].append(sat_id)
        
        if sat_id < len(sat_positions):
            lat, lon = sat_positions[sat_id]
            print(f"   SAT-{sat_id:3d}: 群組 {group_id}, 位置 ({lat:.2f}°, {lon:.2f}°)")
        else:
            print(f"   SAT-{sat_id:3d}: 群組 {group_id}, 位置未知")
    
    print(f"\n📈 路由跨越群組統計:")
    print(f"   涉及群組數量: {len(involved_groups)}")
    for group_id, satellites in involved_groups.items():
        print(f"   群組 {group_id}: {len(satellites)} 個衛星 {satellites}")
    
    # 6. Master衛星分析
    print(f"\n🔶 Master衛星分析:")
    print("-" * 50)
    
    if len(region_to_sats) > 1:
        # 創建簡化的ISL圖
        sat_net_graph = create_simplified_isl_graph(len(sat_positions))
        
        # 選擇master衛星
        group_to_master = select_master_for_regions(region_to_sats)
        
        master_satellites = set(group_to_master.values())
        print(f"🎯 識別的Master衛星:")
        for group_id, master_id in group_to_master.items():
            print(f"   群組 {group_id} → Master衛星 {master_id}")
        
        # 分析路由中的master衛星
        masters_in_path = [sat for sat in satellite_nodes if sat in master_satellites]
        print(f"📊 路由中的Master衛星: {masters_in_path}")
        
    else:
        print("⚠️  只有1個地理區域，無需Master衛星")
    
    # 7. 結論
    print(f"\n💡 分析結論:")
    print("-" * 30)
    if len(involved_groups) == 1:
        print("✅ 這是群內路由 (所有衛星在同一地理區域)")
        print("📝 群內路由不需要Master衛星轉發")
    else:
        print("🔄 這是跨群組路由")
        print("📝 應該經過Master衛星進行區域間轉發")


def calculate_satellite_positions(tles_file, time_ns):
    """計算衛星位置"""
    import ephem
    from datetime import datetime, timezone
    
    # 轉換時間
    epoch_time = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sim_time = epoch_time.timestamp() + time_ns / 1e9
    date = datetime.fromtimestamp(sim_time, tz=timezone.utc)
    
    positions = []
    
    with open(tles_file, 'r') as f:
        lines = f.readlines()
    
    # 每3行是一組TLE
    for i in range(0, len(lines), 3):
        if i + 2 < len(lines):
            try:
                sat = ephem.readtle(lines[i].strip(), lines[i+1].strip(), lines[i+2].strip())
                sat.compute(date)
                
                # 轉換為度數
                lat = float(sat.sublat) * 180.0 / 3.14159
                lon = float(sat.sublong) * 180.0 / 3.14159
                
                positions.append((lat, lon))
            except:
                positions.append((0.0, 0.0))  # 默認位置
                
    return positions


def create_simplified_isl_graph(num_satellites):
    """創建簡化的ISL圖"""
    import networkx as nx
    
    G = nx.Graph()
    
    # 添加節點
    for i in range(num_satellites):
        G.add_node(i)
    
    # 添加簡化的ISL連接（基於25x25網格）
    for i in range(num_satellites):
        # 同軌道連接
        if i + 1 < num_satellites and (i + 1) % 25 != 0:
            G.add_edge(i, i + 1, weight=1.0)
        
        # 跨軌道連接
        if i + 25 < num_satellites:
            G.add_edge(i, i + 25, weight=1.0)
    
    return G


def main():
    """主函數"""
    if len(sys.argv) < 5:
        print("用法: python debug_region_assignment.py <data_dir> <time_ms> <src_gs> <dst_gs> [region_size]")
        return
    
    data_dir = sys.argv[1]
    time_ms = int(sys.argv[2])
    src_gs = int(sys.argv[3])
    dst_gs = int(sys.argv[4])
    region_size = float(sys.argv[5]) if len(sys.argv) > 5 else 5.0
    
    time_ns = time_ms * 1000000
    
    print("🔬 Hypatia 地理分群路由詳細調試器")
    print(f"📁 數據目錄: {data_dir}")
    print(f"⏰ 分析時間: {time_ms}ms")
    print(f"🌍 區域大小: {region_size}°")
    
    debug_regional_routing(data_dir, time_ns, src_gs, dst_gs, region_size)


if __name__ == "__main__":
    main()
