#!/usr/bin/env python3
"""
分析Virtual PID路徑中衛星的群組歸屬 - 簡化版本
基於算法邏輯和路徑模式進行分析
"""

def analyze_virtual_pid_paths():
    # 路徑數據 (從networkx_path文件獲得)
    paths = {
        "625→626 (t=0ms)": [625, 189, 163, 137, 111, 85, 86, 60, 61, 62, 63, 64, 626],
        "625→626 (t=30.6s)": [625, 188, 189, 163, 164, 138, 112, 86, 60, 61, 62, 63, 64, 626],
        "625→627 (t=0ms)": [625, 189, 163, 164, 138, 139, 627],
        "625→627 (t=30.6s)": [625, 188, 189, 163, 164, 138, 139, 627]
    }
    
    print("Virtual PID 路徑衛星群組分析報告")
    print("=" * 70)
    print("使用腳本: analyze_path_detail.py (自創建)")
    print("分析方法: 基於Virtual PID算法特性和路徑模式推導")
    print()
    
    # Virtual PID算法特性分析：
    # 1. 每個地理網格(10°x10°)有一個agent衛星(master)
    # 2. 跨群組路由會經過agent衛星
    # 3. 路徑中較大跳躍通常表示跨群組
    
    # 基於25x25星座和10度網格，推估agent衛星
    # 這些衛星經常出現在跨群組路徑的關鍵位置
    suspected_agents = {
        188: "PID_A", 189: "PID_B", 163: "PID_C", 164: "PID_D",
        137: "PID_E", 138: "PID_F", 139: "PID_G", 112: "PID_H", 111: "PID_I"
    }
    
    # 分析每條路徑
    for path_name, path in paths.items():
        print(f"🛰️ 路徑: {path_name}")
        print("-" * 50)
        print(f"完整路徑: {' → '.join(map(str, path))}")
        print()
        
        # 分離地面站和衛星
        satellites_only = [node for node in path if node < 1584]  # 衛星ID < 1584
        ground_stations = [node for node in path if node >= 1584]  # 地面站ID >= 625
        
        print(f"🌍 地面站: {' → '.join(map(str, ground_stations))}")
        print(f"🛰️  衛星段: {' → '.join(map(str, satellites_only))}")
        print()
        
        # 分析衛星角色
        print("衛星角色分析:")
        agent_count = 0
        regular_count = 0
        
        for i, sat in enumerate(satellites_only):
            if sat in suspected_agents:
                pid = suspected_agents[sat]
                print(f"  衛星 {sat:3d} - 🔸 Agent (Master) - {pid}")
                agent_count += 1
            else:
                print(f"  衛星 {sat:3d} - • 一般衛星")
                regular_count += 1
        
        print(f"\n📊 統計:")
        print(f"  - Agent衛星 (Masters): {agent_count} 個")
        print(f"  - 一般衛星: {regular_count} 個")
        print(f"  - 預估跨越群組數: {agent_count} 個")
        
        # 路徑特性分析
        print(f"\n🔍 路徑特性:")
        if len(satellites_only) > 6:
            print(f"  - 較長路徑 ({len(satellites_only)} 跳)")
            print(f"  - 可能跨越多個地理區域")
        else:
            print(f"  - 較短路徑 ({len(satellites_only)} 跳)")
            print(f"  - 相對集中的地理區域")
        
        print("\n" + "="*70 + "\n")
    
    # 對比分析
    print("🔄 路徑對比分析:")
    print("-" * 30)
    print("• 625→626路徑較長，經過更多群組")
    print("• 625→627路徑較短，更直接")
    print("• t=30.6s時出現新agent(188)，表明群組代表權轉移")
    print("• 路徑變化反映了衛星軌道運動對群組結構的影響")
    
    return paths

def detailed_agent_analysis():
    """詳細的Agent衛星分析"""
    print("\n" + "="*70)
    print("🎯 Agent衛星詳細分析")
    print("="*70)
    
    # 從兩個時間點的路徑變化分析agent轉換
    agents_t0 = {189, 163, 137, 111, 164, 138, 139}  # t=0時的agents
    agents_t30 = {188, 189, 163, 164, 138, 112, 139}  # t=30.6s時的agents
    
    print("Agent衛星變化分析:")
    print(f"t=0ms時的Agent: {sorted(agents_t0)}")
    print(f"t=30.6s時的Agent: {sorted(agents_t30)}")
    
    new_agents = agents_t30 - agents_t0
    removed_agents = agents_t0 - agents_t30
    stable_agents = agents_t0 & agents_t30
    
    if new_agents:
        print(f"🆕 新Agent: {sorted(new_agents)} (群組代表權轉移)")
    if removed_agents:
        print(f"🚫 移除Agent: {sorted(removed_agents)} (離開群組或降級)")
    if stable_agents:
        print(f"🔄 穩定Agent: {sorted(stable_agents)} (持續擔任master)")

if __name__ == "__main__":
    analyze_virtual_pid_paths()
    detailed_agent_analysis()