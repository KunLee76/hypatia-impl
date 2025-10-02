#!/usr/bin/env python3
"""
比較Virtual PID算法與algorithm_free_one_only_over_isls的性能
驗證兩者的跳數是否一致
"""

import os
import sys

def compare_algorithms():
    """比較兩種算法的路由效率"""
    
    base_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state"
    
    # Virtual PID算法的路由文件
    vpid_file = os.path.join(base_dir, "gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/dynamic_state_100ms_for_10s/fstate_1000000000.txt")
    
    # Free one算法的路由文件
    free_file = os.path.join(base_dir, "gen_data/25x25_algorithm_free_one_only_over_isls_fast/dynamic_state_100ms_for_10s/fstate_1000000000.txt")
    
    print("📊 比較Virtual PID vs algorithm_free_one_only_over_isls")
    print("=" * 80)
    
    def trace_path(file_path, algorithm_name):
        """追蹤625→627的完整路徑"""
        if not os.path.exists(file_path):
            print(f"❌ {algorithm_name} 路由文件不存在")
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
                print(f"   ❌ {algorithm_name}: 無法追蹤路徑，在節點 {current} 卡住")
                return None
        
        return path, hop_count
    
    # 比較兩種算法  
    vpid_result = trace_path(vpid_file, "Virtual PID")
    free_result = trace_path(free_file, "Free One")
    
    # 檢查free_one是否有625→627路由
    print(f"🔍 檢查Free One是否有625→627路由...")
    if os.path.exists(free_file):
        with open(free_file, 'r') as f:
            free_lines = f.readlines()
        
        # 搜尋625→627的路由
        found_free_route = False
        for line in free_lines:
            if line.startswith("625,627,"):
                found_free_route = True
                parts = line.strip().split(',')
                print(f"   找到Free One路由: {line.strip()}")
                break
        
        if not found_free_route:
            print("   ❌ Free One沒有625→627的路由")
            
            # 檢查625到其他目標的路由模式
            print("   📊 檢查625的其他路由模式:")
            count = 0
            for line in free_lines:
                if line.startswith("625,") and count < 5:
                    print(f"      {line.strip()}")
                    count += 1
    else:
        print(f"   ❌ Free One路由文件不存在: {free_file}")
    
    if vpid_result:
        vpid_path, vpid_hops = vpid_result
        print(f"🎯 Virtual PID (優化後):")
        print(f"   路徑: {' → '.join(map(str, vpid_path))}")
        print(f"   跳數: {vpid_hops}")
        
        # 分析ISL部分（排除GSL）
        isl_path = [p for p in vpid_path if p < 625]  # 625+是地面站
        if len(isl_path) >= 2:
            isl_hops = len(isl_path) - 1
            print(f"   ISL跳數: {isl_hops} (衛星間: {' → '.join(map(str, isl_path))})")
    
    if free_result:
        free_path, free_hops = free_result
        print(f"\n🔄 Free One (參考基準):")
        print(f"   路徑: {' → '.join(map(str, free_path))}")
        print(f"   跳數: {free_hops}")
        
        # 分析ISL部分
        isl_path = [p for p in free_path if p < 625]
        if len(isl_path) >= 2:
            isl_hops = len(isl_path) - 1
            print(f"   ISL跳數: {isl_hops} (衛星間: {' → '.join(map(str, isl_path))})")
    
    # 結果比較
    print(f"\n📈 性能比較:")
    if vpid_result and free_result:
        vpid_path, vpid_hops = vpid_result
        free_path, free_hops = free_result
        
        if vpid_hops == free_hops:
            print(f"   ✅ 跳數一致: Virtual PID ({vpid_hops}) = Free One ({free_hops})")
            print("   🎉 優化成功！Virtual PID達到了與Free One相同的效率")
        elif vpid_hops < free_hops:
            print(f"   🚀 Virtual PID更優: {vpid_hops} < {free_hops} 跳")
        else:
            print(f"   ⚠️  Virtual PID需要更多跳數: {vpid_hops} > {free_hops}")
            print("   可能需要進一步優化")
            
        # 比較ISL路徑
        vpid_isl = [p for p in vpid_path if p < 625]
        free_isl = [p for p in free_path if p < 625]
        
        if vpid_isl == free_isl:
            print(f"   ✅ ISL路徑完全一致")
        else:
            print(f"   ⚠️  ISL路徑不同:")
            print(f"      Virtual PID: {' → '.join(map(str, vpid_isl))}")
            print(f"      Free One:    {' → '.join(map(str, free_isl))}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    compare_algorithms()