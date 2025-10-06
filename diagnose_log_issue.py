#!/usr/bin/env python3
"""
診斷和解決 alg_mode.log 找不到的問題
"""
import os
import sys
import subprocess
from datetime import datetime

def diagnose_log_issue():
    print("🔍 診斷 alg_mode.log 找不到的問題")
    print("=" * 50)
    
    # 1. 檢查系統是否在使用新算法
    print("\n1. 檢查算法集成狀態")
    print("-" * 30)
    
    try:
        sys.path.insert(0, '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')
        
        # 檢查是否能導入
        from satgen.dynamic_state.algorithm_hierarchical_virtual_pid import init, _alog
        print("✓ 新算法模塊導入成功")
        
        # 檢查是否在 generate_dynamic_state 中註冊
        from satgen.dynamic_state.generate_dynamic_state import generate_dynamic_state_at
        print("✓ generate_dynamic_state 導入成功")
        
        # 讀取 generate_dynamic_state.py 檢查註冊
        gen_file = '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy/satgen/dynamic_state/generate_dynamic_state.py'
        with open(gen_file, 'r') as f:
            content = f.read()
            if 'algorithm_hierarchical_virtual_pid_new' in content:
                print("✓ 新算法已在 generate_dynamic_state.py 中註冊")
            else:
                print("✗ 新算法未在 generate_dynamic_state.py 中註冊")
        
    except Exception as e:
        print(f"✗ 檢查失敗: {e}")
    
    # 2. 檢查當前正在使用的算法
    print("\n2. 檢查當前使用的算法")
    print("-" * 30)
    
    # 從現有輸出目錄推斷
    existing_dirs = []
    base_path = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data"
    
    if os.path.exists(base_path):
        for item in os.listdir(base_path):
            if os.path.isdir(os.path.join(base_path, item)):
                existing_dirs.append(item)
    
    print("現有的生成目錄:")
    for dir_name in existing_dirs:
        print(f"  📁 {dir_name}")
        # 檢查是否有recent的文件
        dir_path = os.path.join(base_path, dir_name)
        if os.path.exists(dir_path):
            files = os.listdir(dir_path)
            recent_files = []
            for f in files:
                f_path = os.path.join(dir_path, f)
                if os.path.isfile(f_path):
                    mtime = os.path.getmtime(f_path)
                    recent_files.append((f, mtime))
            
            if recent_files:
                recent_files.sort(key=lambda x: x[1], reverse=True)
                latest = recent_files[0]
                mtime_str = datetime.fromtimestamp(latest[1]).strftime("%Y-%m-%d %H:%M:%S")
                print(f"     最新文件: {latest[0]} ({mtime_str})")
    
    # 3. 全系統搜索所有 alg_mode.log 文件
    print("\n3. 全系統搜索 alg_mode.log")
    print("-" * 30)
    
    search_paths = [
        "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia",
        "/tmp",
        "/var/tmp"
    ]
    
    all_logs = []
    for search_path in search_paths:
        try:
            result = subprocess.run(
                ["find", search_path, "-name", "alg_mode.log", "-type", "f"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                logs = [log.strip() for log in result.stdout.split('\n') if log.strip()]
                all_logs.extend(logs)
        except Exception as e:
            print(f"搜索 {search_path} 失敗: {e}")
    
    if all_logs:
        print(f"找到 {len(all_logs)} 個 alg_mode.log 文件:")
        for log in all_logs:
            try:
                stat = os.stat(log)
                size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  📄 {log}")
                print(f"     大小: {size} bytes, 修改時間: {mtime}")
                
                # 讀取內容預覽
                with open(log, 'r') as f:
                    content = f.read()
                    lines = content.strip().split('\n')
                    print(f"     行數: {len(lines)}")
                    if lines:
                        print(f"     最新一行: {lines[-1]}")
                print()
            except Exception as e:
                print(f"     讀取失敗: {e}")
    else:
        print("❌ 沒有找到任何 alg_mode.log 文件")
    
    # 4. 測試日誌寫入功能
    print("\n4. 測試日誌寫入功能")
    print("-" * 30)
    
    try:
        from satgen.dynamic_state.algorithm_hierarchical_virtual_pid import _alog
        
        test_dir = "/tmp/log_test_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(test_dir, exist_ok=True)
        
        test_payload = {
            "output_dynamic_state_dir": test_dir
        }
        
        _alog("[DIAGNOSIS] Testing log write functionality", test_payload)
        
        # 檢查是否創建了日誌
        expected_log = os.path.join(test_dir, "alg_mode.log")
        if os.path.exists(expected_log):
            print(f"✓ 日誌寫入測試成功: {expected_log}")
            with open(expected_log, 'r') as f:
                content = f.read()
                print(f"✓ 內容: {content.strip()}")
        else:
            print(f"✗ 日誌寫入測試失敗，未找到: {expected_log}")
            
    except Exception as e:
        print(f"✗ 日誌寫入測試失敗: {e}")
    
    # 5. 提供解決方案
    print("\n5. 問題診斷和解決方案")
    print("-" * 30)
    
    print("🔧 可能的問題和解決方案:")
    print()
    print("A. 如果沒有找到任何日誌文件:")
    print("   - 你的新算法可能沒有被調用")
    print("   - 檢查是否使用了正確的算法名稱: 'algorithm_hierarchical_virtual_pid_new'")
    print()
    print("B. 如果找到了日誌但內容是舊的:")
    print("   - 系統可能仍在使用舊算法")
    print("   - 確保在生成時指定了新算法名稱")
    print()
    print("C. 如果日誌寫入測試失敗:")
    print("   - 可能有權限問題")
    print("   - 檢查目錄創建權限")
    print()
    print("D. 下一步操作建議:")
    print("   1. 確認使用算法名稱: 'algorithm_hierarchical_virtual_pid_new'")
    print("   2. 在生成命令中明確指定算法")
    print("   3. 檢查生成過程的輸出，看是否有錯誤信息")
    print("   4. 生成完成後立即檢查指定的 output_dynamic_state_dir")
    
    return all_logs

if __name__ == "__main__":
    logs_found = diagnose_log_issue()
    
    print("\n" + "=" * 50)
    print("🏁 診斷完成")
    
    if logs_found:
        print(f"✅ 找到了 {len(logs_found)} 個日誌文件")
        print("💡 建議檢查最新的日誌文件內容")
    else:
        print("❌ 沒有找到日誌文件")
        print("💡 這表明你的新算法可能還沒有被實際調用")
        print("🔧 請確保在運行衛星網路生成時使用算法名稱: 'algorithm_hierarchical_virtual_pid_new'")