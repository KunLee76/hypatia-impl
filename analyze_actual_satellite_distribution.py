#!/usr/bin/env python3
"""
使用實際的algorithm_hierarchical_region.py來分析真實的衛星分布
"""

import sys
import os
from collections import defaultdict

def add_satgen_path():
    """添加satgen路徑"""
    satgen_path = '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy'
    if satgen_path not in sys.path:
        sys.path.append(satgen_path)

def analyze_actual_satellite_distribution():
    """分析實際運行中的衛星分布"""
    print("🔍 分析實際運行中的衛星分布")
    print("=" * 50)
    
    # 檢查實際的分群數據
    input_data_dir = '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/input_data'
    gen_data_dir = '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_region'
    
    # 1. 檢查輸入數據
    print("\n📂 檢查輸入數據:")
    tles_file = os.path.join(input_data_dir, 'tles.txt')
    ground_stations_file = os.path.join(input_data_dir, 'ground_stations.txt')
    
    if os.path.exists(tles_file):
        with open(tles_file, 'r') as f:
            lines = f.readlines()
        sat_count = len([l for l in lines if l.strip().startswith('S')])
        print(f"  衛星數量 (from tles.txt): {sat_count}")
    
    if os.path.exists(ground_stations_file):
        with open(ground_stations_file, 'r') as f:
            lines = f.readlines()
        gs_count = len([l for l in lines if l.strip() and not l.startswith('#')])
        print(f"  地面站數量: {gs_count}")
    
    # 2. 檢查區域分群數據
    print("\n📊 檢查區域分群數據:")
    
    # 尋找satellites.txt或相關檔案
    possible_files = [
        os.path.join(gen_data_dir, 'satellites.txt'),
        os.path.join(gen_data_dir, 'satellite_network_state.txt'),
        os.path.join(gen_data_dir, 'isls.txt')
    ]
    
    for file_path in possible_files:
        if os.path.exists(file_path):
            print(f"  找到檔案: {os.path.basename(file_path)}")
            with open(file_path, 'r') as f:
                first_lines = [f.readline().strip() for _ in range(5)]
            print(f"    前5行: {first_lines}")
    
    # 3. 嘗試直接運行algorithm_hierarchical_region來獲取統計
    print("\n🔧 嘗試獲取實際分群統計:")
    
    try:
        # 檢查是否有debug輸出檔案
        debug_files = [
            '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/debug_output.txt',
            '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/detailed_debug.txt'
        ]
        
        for debug_file in debug_files:
            if os.path.exists(debug_file):
                print(f"  檢查debug檔案: {os.path.basename(debug_file)}")
                with open(debug_file, 'r') as f:
                    lines = f.readlines()
                
                # 搜尋區域統計
                for i, line in enumerate(lines):
                    if 'region' in line.lower() and 'satellite' in line.lower():
                        print(f"    Line {i+1}: {line.strip()}")
                    elif 'master' in line.lower() and 'select' in line.lower():
                        print(f"    Line {i+1}: {line.strip()}")
                        
                # 最後10行通常包含摘要
                print(f"  最後10行:")
                for line in lines[-10:]:
                    if line.strip():
                        print(f"    {line.strip()}")
                        
    except Exception as e:
        print(f"  讀取debug檔案出錯: {e}")
    
    # 4. 運行一個簡化的分群分析
    print("\n🧮 運行簡化分群分析:")
    
    try:
        add_satgen_path()
        from satgen.post_analysis.main_print_routes_and_rtt import read_ground_stations_extended
        
        # 讀取地面站
        gs_file = '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/input_data/ground_stations.txt'
        if os.path.exists(gs_file):
            ground_stations = read_ground_stations_extended(gs_file)
            print(f"  成功讀取 {len(ground_stations)} 個地面站")
            
            # 檢查前幾個地面站的位置
            for i, gs in enumerate(ground_stations[:5]):
                print(f"    GS{i}: lat={gs['latitude']:.2f}, lon={gs['longitude']:.2f}, name={gs.get('name', 'Unknown')}")
    
    except Exception as e:
        print(f"  讀取地面站出錯: {e}")

def analyze_region_files():
    """分析生成的區域檔案"""
    print("\n📁 分析生成的區域檔案")
    print("=" * 30)
    
    gen_data_dir = '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_region'
    
    if os.path.exists(gen_data_dir):
        files = os.listdir(gen_data_dir)
        print(f"生成的檔案: {files}")
        
        # 檢查dynamic_state目錄
        dynamic_state_dir = os.path.join(gen_data_dir, 'dynamic_state_100ms_for_1s')
        if os.path.exists(dynamic_state_dir):
            dynamic_files = os.listdir(dynamic_state_dir)
            print(f"動態狀態檔案: {len(dynamic_files)} 個檔案")
            
            # 分析fstate檔案來了解網路拓撲
            fstate_files = [f for f in dynamic_files if f.startswith('fstate_')]
            if fstate_files:
                fstate_file = os.path.join(dynamic_state_dir, fstate_files[0])
                print(f"\n分析 {fstate_files[0]}:")
                
                nodes = set()
                with open(fstate_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            parts = line.strip().split(',')
                            if len(parts) >= 3:
                                nodes.add(int(parts[0]))
                                nodes.add(int(parts[1]))
                
                print(f"  節點總數: {len(nodes)}")
                print(f"  節點範圍: {min(nodes)} - {max(nodes)}")
                
                # 分析節點類型 (假設地面站ID較大)
                satellites = [n for n in nodes if n < 625]  # 假設衛星ID < 625
                ground_stations = [n for n in nodes if n >= 625]
                
                print(f"  推測衛星數: {len(satellites)}")
                print(f"  推測地面站數: {len(ground_stations)}")
    
    else:
        print(f"目錄不存在: {gen_data_dir}")

if __name__ == "__main__":
    print("📡 實際衛星分布分析")
    print("=" * 50)
    
    analyze_actual_satellite_distribution()
    analyze_region_files()
    
    print("\n✅ 實際分析完成!")
