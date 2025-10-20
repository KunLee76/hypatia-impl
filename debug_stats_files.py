#!/usr/bin/env python3
"""
檢查算法統計文件生成的調試腳本
"""

import os
import sys
import json
from pathlib import Path

def check_algorithm_files():
    """檢查算法執行後的文件生成情況"""
    
    base_dir = "/home/kun/ssd2t/Leo/kun_hypatia"
    stats_dir = os.path.join(base_dir, "paper", "satellite_networks_state")
    
    print("=== 檢查算法統計文件生成情況 ===")
    print(f"檢查目錄: {stats_dir}")
    print()
    
    # 檢查預期的統計文件
    expected_files = [
        "hierarchical_pid_signaling_stats.json",
        "baseline_floyd_warshall_signaling_stats.json", 
        "alg_mode.log"
    ]
    
    for file_name in expected_files:
        file_path = os.path.join(stats_dir, file_name)
        if os.path.exists(file_path):
            print(f"✅ {file_name} - 存在")
            if file_name.endswith('.json'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    print(f"   → 算法: {data.get('algorithm', 'N/A')}")
                    print(f"   → 時間戳: {data.get('timestamp', 'N/A')}")
                    print(f"   → 總事件: {data.get('summary', {}).get('total_events', 'N/A')}")
                    print(f"   → 總字節: {data.get('summary', {}).get('total_bytes', 'N/A')}")
                    print(f"   → 時間軸事件: {len(data.get('timeline', []))}")
                except Exception as e:
                    print(f"   ❌ JSON 讀取錯誤: {e}")
            elif file_name.endswith('.log'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    print(f"   → 日誌行數: {len(lines)}")
                    if lines:
                        print(f"   → 最後一行: {lines[-1].strip()}")
                except Exception as e:
                    print(f"   ❌ 日誌讀取錯誤: {e}")
        else:
            print(f"❌ {file_name} - 不存在")
        print()
    
    # 檢查生成的數據目錄
    gen_data_dir = os.path.join(stats_dir, "gen_data")
    if os.path.exists(gen_data_dir):
        print("=== 檢查 gen_data 目錄 ===")
        subdirs = [d for d in os.listdir(gen_data_dir) if os.path.isdir(os.path.join(gen_data_dir, d))]
        for subdir in sorted(subdirs):
            if "algorithm" in subdir:
                print(f"📁 {subdir}")
        print()
    
    # 搜索任何包含 signaling 的文件
    print("=== 搜索所有 signaling 相關文件 ===")
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if "signaling" in file.lower() or "stats" in file.lower():
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir)
                print(f"🔍 找到: {rel_path}")
    
    # 檢查當前工作目錄
    print(f"\n=== 當前工作目錄檢查 ===")
    cwd = os.getcwd()
    print(f"當前目錄: {cwd}")
    
    cwd_files = [f for f in os.listdir(cwd) if "signaling" in f or f.endswith('.json') or f.endswith('.log')]
    if cwd_files:
        print("當前目錄中的相關文件:")
        for f in cwd_files:
            print(f"  - {f}")
    else:
        print("當前目錄中沒有找到相關文件")

if __name__ == "__main__":
    check_algorithm_files()