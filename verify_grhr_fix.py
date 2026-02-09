#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GRHR 修復效果驗證腳本

用途：
  比較修復前後的 GRHR 統計數據，確認 gid_rebuilds 減半

執行方式：
  python3 verify_grhr_fix.py
"""

import json
import os
from datetime import datetime

# 工作目錄
ANALYTIC_DIR = "paper/satellite_networks_state/analytic_result"

# 備份目錄（如果有的話）
BACKUP_DIR = "paper/satellite_networks_state/analytic_result_backup_before_fix"

# 場景定義
SCENARIOS = ["p1", "p5", "p10"]
K_VALUES = [4, 8]

def load_json(filepath):
    """載入 JSON 文件"""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"  ✗ 讀取失敗：{filepath} - {e}")
        return None


def main():
    print("")
    print("=" * 80)
    print("GRHR 修復效果驗證")
    print("=" * 80)
    print("")
    
    # 檢查是否有備份
    has_backup = os.path.exists(BACKUP_DIR)
    
    if has_backup:
        print(f"✓ 找到備份目錄：{BACKUP_DIR}")
        print("")
        print("進行修復前後對比...")
        print("")
        
        comparison_table = []
        
        for scenario in SCENARIOS:
            for k in K_VALUES:
                filename = f"hierarchical_gid_27deg_dynamic_{scenario}_k{k}_signaling_stats.json"
                
                # 修復前（備份）
                old_path = os.path.join(BACKUP_DIR, filename)
                old_data = load_json(old_path)
                
                # 修復後（當前）
                new_path = os.path.join(ANALYTIC_DIR, filename)
                new_data = load_json(new_path)
                
                if old_data and new_data:
                    old_gid = old_data.get('gid_rebuilds', 0)
                    new_gid = new_data.get('gid_rebuilds', 0)
                    old_total = old_data.get('total_messages', 0)
                    new_total = new_data.get('total_messages', 0)
                    
                    ratio = new_gid / old_gid if old_gid > 0 else 0
                    
                    comparison_table.append({
                        'scenario': scenario.upper(),
                        'k': k,
                        'old_gid': old_gid,
                        'new_gid': new_gid,
                        'ratio': ratio,
                        'old_total': old_total,
                        'new_total': new_total
                    })
        
        # 輸出對比表格
        print("-" * 80)
        print(f"{'場景':<8} {'K':<4} {'修復前GID':>12} {'修復後GID':>12} {'比例':>8} {'修復前總訊息':>14} {'修復後總訊息':>14}")
        print("-" * 80)
        
        for row in comparison_table:
            print(f"{row['scenario']:<8} {row['k']:<4} {row['old_gid']:>12,} {row['new_gid']:>12,} {row['ratio']:>7.2f}x {row['old_total']:>14,} {row['new_total']:>14,}")
        
        print("-" * 80)
        print("")
        
        # 驗證結果
        all_good = all(0.45 <= row['ratio'] <= 0.55 for row in comparison_table)
        
        if all_good:
            print("✓ 驗證通過！所有場景的 gid_rebuilds 都減少約 50%")
            print("  修復成功：消除了雙重調用問題")
        else:
            print("⚠ 驗證異常：gid_rebuilds 減少幅度不符合預期（應約 50%）")
            print("  可能原因：")
            print("    1. 修復代碼未正確應用")
            print("    2. 還有其他地方調用了 refresh_gid_members_and_subgraphs()")
        
    else:
        print(f"⚠ 未找到備份目錄：{BACKUP_DIR}")
        print("")
        print("僅檢查當前數據...")
        print("")
        
        print("-" * 80)
        print(f"{'場景':<8} {'K':<4} {'GID重建':>12} {'總訊息':>12} {'總流量(KB)':>15}")
        print("-" * 80)
        
        for scenario in SCENARIOS:
            for k in K_VALUES:
                filename = f"hierarchical_gid_27deg_dynamic_{scenario}_k{k}_signaling_stats.json"
                filepath = os.path.join(ANALYTIC_DIR, filename)
                data = load_json(filepath)
                
                if data:
                    gid_rebuilds = data.get('gid_rebuilds', 0)
                    total_messages = data.get('total_messages', 0)
                    total_bytes = data.get('total_bytes', 0)
                    
                    print(f"{scenario.upper():<8} {k:<4} {gid_rebuilds:>12,} {total_messages:>12,} {total_bytes/1024:>15,.2f}")
                else:
                    print(f"{scenario.upper():<8} {k:<4} {'N/A':>12} {'N/A':>12} {'N/A':>15}")
        
        print("-" * 80)
        print("")
        print("提示：如需對比修復效果，請先備份修復前的數據到：")
        print(f"  {BACKUP_DIR}")
    
    print("")
    print("=" * 80)


if __name__ == "__main__":
    main()
