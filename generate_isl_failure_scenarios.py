#!/usr/bin/env python3
"""
ISL 失效場景生成工具

用途：
  生成不同級別的 ISL 失效場景，用於測試不同 K_BEST_GATEWAYS 參數下的路由韌性

失效策略：
  - 選擇關鍵中繼節點（如 861, 927）
  - 漸進式移除其 ISL 連接
  - 觀察不同 K 值下的恢復能力

使用方法：
  python generate_isl_failure_scenarios.py [source_isls] [output_dir]
  
  source_isls: 原始 isls.txt 路徑
  output_dir:  輸出目錄（將生成 isls_baseline.txt, isls_failure_l1.txt 等）
"""

import sys
import os
from typing import List, Tuple, Set

def read_isls(filename: str) -> List[Tuple[int, int]]:
    """讀取 ISL 文件，返回 (node_a, node_b) 的列表"""
    isls = []
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                a, b = int(parts[0]), int(parts[1])
                # 確保 a < b（統一格式）
                isls.append((min(a, b), max(a, b)))
    return isls

def write_isls(filename: str, isls: List[Tuple[int, int]]):
    """寫入 ISL 文件"""
    with open(filename, 'w') as f:
        for a, b in sorted(isls):
            f.write(f"{a} {b}\n")

def remove_isls(original_isls: List[Tuple[int, int]], 
                failed_isls: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """從原始 ISL 列表中移除失效的 ISL"""
    # 轉換為 set 方便比較（確保順序一致）
    failed_set = set()
    for a, b in failed_isls:
        failed_set.add((min(a, b), max(a, b)))
    
    # 過濾掉失效的 ISL
    remaining = []
    for isl in original_isls:
        if isl not in failed_set:
            remaining.append(isl)
    
    return remaining

def get_node_isls(isls: List[Tuple[int, int]], node: int) -> List[Tuple[int, int]]:
    """獲取某個節點的所有 ISL"""
    node_isls = []
    for a, b in isls:
        if a == node or b == node:
            node_isls.append((a, b))
    return node_isls

def print_scenario_info(scenario_name: str, failed_isls: List[Tuple[int, int]], 
                       original_count: int, remaining_count: int):
    """打印場景信息"""
    print(f"\n{'='*60}")
    print(f"場景: {scenario_name}")
    print(f"{'='*60}")
    print(f"移除的 ISL:")
    for a, b in failed_isls:
        print(f"  {a} ↔ {b}")
    print(f"\n原始 ISL 數量: {original_count}")
    print(f"剩餘 ISL 數量: {remaining_count}")
    print(f"移除比例: {len(failed_isls) / original_count * 100:.2f}%")

def main():
    if len(sys.argv) < 3:
        print("用法: python generate_isl_failure_scenarios.py <source_isls> <output_dir>")
        print("\n範例:")
        print("  python generate_isl_failure_scenarios.py \\")
        print("    paper/satellite_networks_state/gen_data/starlink_550_.../isls.txt \\")
        print("    paper/satellite_networks_state/input_data/failure_scenarios/")
        sys.exit(1)
    
    source_file = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not os.path.exists(source_file):
        print(f"❌ 錯誤: 找不到檔案 {source_file}")
        sys.exit(1)
    
    # 創建輸出目錄
    os.makedirs(output_dir, exist_ok=True)
    
    # 讀取原始 ISL
    print(f"📖 讀取原始 ISL: {source_file}")
    original_isls = read_isls(source_file)
    print(f"   總共 {len(original_isls)} 條 ISL")
    
    # 分析關鍵節點
    print(f"\n🔍 分析關鍵中繼節點...")
    node_861_isls = get_node_isls(original_isls, 861)
    node_927_isls = get_node_isls(original_isls, 927)
    print(f"   節點 861 (1584→1585 路徑第一跳): {len(node_861_isls)} 條 ISL")
    print(f"     {', '.join([f'{a}-{b}' for a, b in node_861_isls])}")
    print(f"   節點 927 (1584→1593 路徑第一跳): {len(node_927_isls)} 條 ISL")
    print(f"     {', '.join([f'{a}-{b}' for a, b in node_927_isls])}")
    
    # === Baseline: 無失效 ===
    baseline_file = os.path.join(output_dir, "isls_baseline.txt")
    write_isls(baseline_file, original_isls)
    print(f"\n✓ 生成 Baseline: {baseline_file}")
    print(f"  (完整拓撲，{len(original_isls)} 條 ISL)")
    
    # === Failure Level 1: 輕度失效 ===
    # 移除節點 861 的一條同軌 ISL (839-861)
    failed_l1 = [(839, 861)]
    remaining_l1 = remove_isls(original_isls, failed_l1)
    l1_file = os.path.join(output_dir, "isls_failure_l1.txt")
    write_isls(l1_file, remaining_l1)
    print_scenario_info("Failure Level 1 (輕度失效)", failed_l1, 
                       len(original_isls), len(remaining_l1))
    print(f"✓ 輸出: {l1_file}")
    print(f"預期影響: K=1 可能需繞路，K≥2 可切換至其他 gateway")
    
    # === Failure Level 2: 中度失效 ===
    # 移除節點 861 的兩條同軌 ISL (839-861, 861-883)
    failed_l2 = [(839, 861), (861, 883)]
    remaining_l2 = remove_isls(original_isls, failed_l2)
    l2_file = os.path.join(output_dir, "isls_failure_l2.txt")
    write_isls(l2_file, remaining_l2)
    print_scenario_info("Failure Level 2 (中度失效)", failed_l2,
                       len(original_isls), len(remaining_l2))
    print(f"✓ 輸出: {l2_file}")
    print(f"預期影響: K≤2 顯著繞路，K≥4 可用跨軌 ISL")
    
    # === Failure Level 3: 重度失效 ===
    # 移除節點 861 的三條 ISL (839-861, 861-883, 860-861)
    failed_l3 = [(839, 861), (861, 883), (860, 861)]
    remaining_l3 = remove_isls(original_isls, failed_l3)
    l3_file = os.path.join(output_dir, "isls_failure_l3.txt")
    write_isls(l3_file, remaining_l3)
    print_scenario_info("Failure Level 3 (重度失效)", failed_l3,
                       len(original_isls), len(remaining_l3))
    print(f"✓ 輸出: {l3_file}")
    print(f"預期影響: K≤4 可能中斷或大幅繞路，K≥6 仍可透過多 gateway 恢復")
    
    # === Failure Level 4: 極端失效 ===
    # 移除節點 861 的所有 ISL（完全孤立）
    failed_l4 = [(839, 861), (861, 883), (860, 861), (861, 862)]
    remaining_l4 = remove_isls(original_isls, failed_l4)
    l4_file = os.path.join(output_dir, "isls_failure_l4.txt")
    write_isls(l4_file, remaining_l4)
    print_scenario_info("Failure Level 4 (極端失效 - 節點孤立)", failed_l4,
                       len(original_isls), len(remaining_l4))
    print(f"✓ 輸出: {l4_file}")
    print(f"預期影響: 節點 861 完全孤立，必須繞過此節點或切換 gateway")
    
    print(f"\n{'='*60}")
    print(f"✅ 完成！共生成 5 個場景")
    print(f"{'='*60}")
    print(f"\n📊 下一步:")
    print(f"1. 複製這些 isls.txt 到對應的實驗目錄")
    print(f"2. 對每個場景運行所有 K 值 (1, 2, 4, 6, 8, 999)")
    print(f"3. 比較不同 K 值在各失效場景下的:")
    print(f"   - RTT 變化")
    print(f"   - 路徑可達性")
    print(f"   - 控制信令開銷")
    print(f"\n💡 失效邏輯:")
    print(f"   Level 1: 輕度 - 移除 1 條同軌 ISL")
    print(f"   Level 2: 中度 - 移除 2 條同軌 ISL（同軌完全斷）")
    print(f"   Level 3: 重度 - 移除 3 條 ISL（只剩 1 條跨軌）")
    print(f"   Level 4: 極端 - 移除 4 條 ISL（節點完全孤立）")

if __name__ == "__main__":
    main()
