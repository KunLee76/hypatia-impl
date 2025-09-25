#!/usr/bin/env python3
"""
診斷Virtual PID算法的路由問題
"""

import sys
sys.path.append('/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')

def check_routing_issue():
    """檢查路由問題"""
    fstate_file = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_fast/dynamic_state_100ms_for_10s/fstate_0.txt"
    
    print("🔍 診斷625→627路由問題")
    print("=" * 50)
    
    # 讀取fstate
    fstate = {}
    with open(fstate_file, 'r') as f:
        for line in f:
            if line.strip():
                parts = line.strip().split(',')
                src = int(parts[0])
                dst = int(parts[1])  
                next_hop = int(parts[2])
                fstate[(src, dst)] = next_hop
    
    print(f"載入 {len(fstate)} 條路由規則")
    
    # 追蹤路徑
    def get_path(src, dst):
        path = [src]
        curr = src
        visited = set()
        
        while curr != dst:
            if curr in visited:
                return None  # 循環
            visited.add(curr)
            
            next_hop = fstate.get((curr, dst))
            if next_hop is None:
                return None  # 無路由
            
            path.append(next_hop)
            curr = next_hop
            
            if len(path) > 20:
                return None  # 太長
        
        return path
    
    # 檢查625→627
    path = get_path(625, 627)
    print(f"\n625→627路徑: {path}")
    
    if path is None:
        print("❌ 路徑不可達！")
        
        # 檢查第一跳
        first_hop = fstate.get((625, 627))
        print(f"625→627第一跳: {first_hop}")
        
        if first_hop is not None:
            # 檢查第一跳是否有到627的路由
            second_hop = fstate.get((first_hop, 627))
            print(f"{first_hop}→627第二跳: {second_hop}")
            
            if second_hop is None:
                print(f"❌ 衛星{first_hop}沒有到627的路由！")
                
                # 檢查衛星189的所有出站路由
                outgoing = {dst: nh for (src, dst), nh in fstate.items() if src == first_hop}
                print(f"衛星{first_hop}的出站路由數: {len(outgoing)}")
                
                # 檢查到地面站的路由
                to_gs = {dst: nh for dst, nh in outgoing.items() if dst >= 625}
                print(f"到地面站的路由: {len(to_gs)}")
    else:
        print("✅ 路徑可達")

if __name__ == "__main__":
    check_routing_issue()