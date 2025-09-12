#!/usr/bin/env python3
"""
分析hierarchical routing中的master衛星和路由路徑
顯示路由路徑中哪些是master衛星，哪些是一般衛星
"""

import sys
import os
sys.path.append("satgenpy")

from satgen.post_analysis.graph_tools import get_path
from satgen.dynamic_state.algorithm_hierarchical_region import assign_satellites_to_regions, select_regional_master_by_connectivity
import satgen


def analyze_master_routing(data_dir, time_ns, src_gs, dst_gs, region_lat_step=20.0, region_lon_step=20.0):
    """
    分析特定時間點的master路由
    
    Args:
        data_dir: 數據目錄路徑
        time_ns: 時間點（納秒）
        src_gs: 源地面站ID
        dst_gs: 目標地面站ID
        region_lat_step: 地理分群緯度步長
        region_lon_step: 地理分群經度步長
    """
    
    print(f"\n🔍 分析時間點 {time_ns//1000000}ms 的路由 GS{src_gs} → GS{dst_gs}")
    print("=" * 60)
    
    # 1. 讀取forwarding state
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
    
    # 3. 載入衛星位置數據來計算master
    # 需要從TLE或其他文件獲取衛星位置
    base_dir = os.path.dirname(data_dir)
    tles_file = f"{base_dir}/tles.txt"
    
    if not os.path.exists(tles_file):
        print(f"❌ 找不到TLE文件: {tles_file}")
        return
    
    # 讀取TLE並計算衛星位置
    print("📡 正在計算衛星位置和master分配...")
    
    try:
        # 計算指定時間的衛星位置
        sat_positions = calculate_satellite_positions(tles_file, time_ns)
        
        # 執行地理分群
        sat_to_group, region_to_sats = assign_satellites_to_regions(
            sat_positions, lat_step=region_lat_step, lon_step=region_lon_step
        )
        
        # 創建ISL圖（簡化版）
        sat_net_graph = create_simplified_isl_graph(len(sat_positions))
        
        # 選擇master衛星
        group_to_master = select_regional_master_by_connectivity(
            region_to_sats, sat_net_graph
        )
        
        # 創建master衛星集合
        master_satellites = set(group_to_master.values())
        
        print(f"🎯 共識別 {len(master_satellites)} 個master衛星")
        print(f"🌍 共 {len(region_to_sats)} 個地理區域")
        
        # 4. 分析路由路徑
        print("\n🛤️  路由路徑分析:")
        print("-" * 50)
        
        for i, node in enumerate(path):
            if node >= 625:  # 地面站
                gs_id = node - 625
                print(f"  {i:2d}. GS-{gs_id:2d} (地面站)")
            else:  # 衛星
                sat_id = node
                is_master = sat_id in master_satellites
                group_id = sat_to_group.get(sat_id, -1)
                
                if is_master:
                    print(f"  {i:2d}. SAT-{sat_id:3d} 🔶 MASTER (Group {group_id})")
                else:
                    print(f"  {i:2d}. SAT-{sat_id:3d} ⚪ Regular (Group {group_id})")
        
        # 5. 統計分析
        satellite_nodes = [node for node in path if node < 625]
        master_count = sum(1 for sat in satellite_nodes if sat in master_satellites)
        regular_count = len(satellite_nodes) - master_count
        
        print(f"\n📈 路由統計:")
        print(f"   總衛星節點: {len(satellite_nodes)}")
        print(f"   Master衛星: {master_count}")
        print(f"   一般衛星: {regular_count}")
        print(f"   Master比例: {master_count/len(satellite_nodes)*100:.1f}%" if satellite_nodes else "N/A")
        
        # 6. 顯示涉及的地理區域
        involved_groups = set(sat_to_group.get(sat, -1) for sat in satellite_nodes)
        print(f"   涉及區域: {len(involved_groups)} 個 {sorted(involved_groups)}")
        
    except Exception as e:
        print(f"❌ 分析過程中出現錯誤: {e}")
        import traceback
        traceback.print_exc()


def calculate_satellite_positions(tles_file, time_ns):
    """簡化的衛星位置計算"""
    import ephem
    from datetime import datetime, timezone
    
    # 轉換時間
    epoch_time = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sim_time = epoch_time.timestamp() + time_ns / 1e9
    date = datetime.fromtimestamp(sim_time, tz=timezone.utc)
    
    positions = []
    
    with open(tles_file, 'r') as f:
        lines = f.readlines()
    
    # 每3行是一組TLE (name, line1, line2)
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
                # 如果TLE解析失敗，使用默認位置
                positions.append((0.0, 0.0))
    
    return positions


def create_simplified_isl_graph(num_satellites):
    """創建簡化的ISL圖"""
    import networkx as nx
    
    G = nx.Graph()
    G.add_nodes_from(range(num_satellites))
    
    # 簡化：假設每個衛星都與鄰近衛星相連
    # 這裡使用簡單的格網連接模式
    for i in range(num_satellites):
        # 連接到下一個衛星（環形）
        G.add_edge(i, (i + 1) % num_satellites, weight=1.0)
        # 連接到軌道內鄰近衛星
        if i + 25 < num_satellites:
            G.add_edge(i, i + 25, weight=1.0)
    
    return G


def main():
    """主函數"""
    if len(sys.argv) < 6:
        print("用法: python analyze_master_routing.py <data_dir> <time_ms> <src_gs> <dst_gs> [region_size]")
        print("例如: python analyze_master_routing.py paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_region_fast/dynamic_state_100ms_for_200s 1000 625 626")
        return
    
    data_dir = sys.argv[1]
    time_ms = int(sys.argv[2])
    src_gs = int(sys.argv[3])
    dst_gs = int(sys.argv[4])
    region_size = float(sys.argv[5]) if len(sys.argv) > 5 else 20.0
    
    time_ns = time_ms * 1000000  # 轉換為納秒
    
    print("🚀 Hypatia Master Routing Analyzer")
    print(f"📁 數據目錄: {data_dir}")
    print(f"⏰ 分析時間: {time_ms}ms")
    print(f"🌍 地理區域大小: {region_size}° × {region_size}°")
    
    analyze_master_routing(data_dir, time_ns, src_gs, dst_gs, region_size, region_size)


if __name__ == "__main__":
    main()
