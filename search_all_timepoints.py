#!/usr/bin/env python3
"""
在所有時間點搜尋625→627的路由，找到Free One算法的最佳性能
"""

import os
import glob

def find_625_627_routes():
    """在所有時間點搜尋625→627路由"""
    
    base_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state"
    
    # Free One算法的路由文件目錄
    free_dir = os.path.join(base_dir, "gen_data/25x25_algorithm_free_one_only_over_isls_fast/dynamic_state_100ms_for_10s")
    vpid_dir = os.path.join(base_dir, "gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/dynamic_state_100ms_for_10s")
    
    print("🔍 搜尋所有時間點的625→627路由...")
    print("=" * 80)
    
    def trace_route_in_file(file_path):
        """在單個文件中追蹤625→627路由"""
        if not os.path.exists(file_path):
            return None
            
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # 追蹤完整路徑
        current = 625
        target = 627
        path = [current]
        hop_count = 0
        max_hops = 15
        
        while current != target and hop_count < max_hops:
            found_next = False
            for line in lines:
                line = line.strip()
                if line.startswith(f"{current},{target},"):
                    parts = line.split(',')
                    if len(parts) >= 3:
                        next_hop = int(parts[2])
                        path.append(next_hop)
                        current = next_hop
                        hop_count += 1
                        found_next = True
                        break
            
            if not found_next:
                return None
        
        return path, hop_count
    
    # 搜尋Free One的所有時間點
    free_files = glob.glob(os.path.join(free_dir, "fstate_*.txt"))
    free_results = []
    
    print("📡 Free One算法結果:")
    for file_path in sorted(free_files):
        timestamp = os.path.basename(file_path).replace("fstate_", "").replace(".txt", "")
        result = trace_route_in_file(file_path)
        if result:
            path, hops = result
            free_results.append((timestamp, path, hops))
            isl_path = [p for p in path if p < 625]
            isl_hops = len(isl_path) - 1 if len(isl_path) >= 2 else 0
            print(f"   時間 {timestamp}: {' → '.join(map(str, path))} ({hops}跳, ISL:{isl_hops}跳)")
    
    if not free_results:
        print("   ❌ 在所有時間點都沒有找到625→627路由")
    
    # 搜尋Virtual PID的結果進行對比
    print(f"\n🎯 Virtual PID算法結果 (參考):")
    vpid_file = os.path.join(vpid_dir, "fstate_1000000000.txt")
    vpid_result = trace_route_in_file(vpid_file)
    if vpid_result:
        path, hops = vpid_result
        isl_path = [p for p in path if p < 625]
        isl_hops = len(isl_path) - 1 if len(isl_path) >= 2 else 0
        print(f"   時間 1000000000: {' → '.join(map(str, path))} ({hops}跳, ISL:{isl_hops}跳)")
    
    # 分析結果
    print(f"\n📊 性能分析:")
    if free_results:
        best_free = min(free_results, key=lambda x: x[2])
        timestamp, path, hops = best_free
        isl_path = [p for p in path if p < 625]
        isl_hops = len(isl_path) - 1 if len(isl_path) >= 2 else 0
        
        print(f"   Free One最佳: {hops}跳 (ISL:{isl_hops}跳) 在時間 {timestamp}")
        
        if vpid_result:
            vpid_path, vpid_hops = vpid_result
            vpid_isl_path = [p for p in vpid_path if p < 625]
            vpid_isl_hops = len(vpid_isl_path) - 1 if len(vpid_isl_path) >= 2 else 0
            
            if vpid_hops <= hops:
                print(f"   ✅ Virtual PID ({vpid_hops}跳) <= Free One ({hops}跳)")
            else:
                print(f"   ⚠️  Virtual PID ({vpid_hops}跳) > Free One ({hops}跳)")
                print(f"       差距: {vpid_hops - hops} 跳")
                
            # ISL跳數比較
            if vpid_isl_hops <= isl_hops:
                print(f"   ✅ ISL跳數: Virtual PID ({vpid_isl_hops}) <= Free One ({isl_hops})")
            else:
                print(f"   ⚠️  ISL跳數: Virtual PID ({vpid_isl_hops}) > Free One ({isl_hops})")
    
    else:
        print(f"   Virtual PID提供連通性，而Free One無法連通625→627")
        print(f"   這是Virtual PID算法的重大優勢！")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    find_625_627_routes()