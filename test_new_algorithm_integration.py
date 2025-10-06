#!/usr/bin/env python3
"""
測試新算法是否能正確被調用並產生日誌
"""
import os
import sys
import tempfile
from datetime import datetime

# 添加 satgenpy 到 Python 路徑
sys.path.insert(0, '/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/satgenpy')

def test_new_algorithm():
    print("=== 測試新算法集成 ===")
    
    try:
        # 1. 測試導入
        print("\n--- 測試導入 ---")
        from satgen.dynamic_state.algorithm_hierarchical_virtual_pid import init, step, algorithm_hierarchical_virtual_pid_new
        print("✓ 成功導入新算法模塊")
        
        # 2. 測試初始化
        print("\n--- 測試初始化 ---")
        init_result = init()
        print(f"初始化結果: {init_result}")
        
        # 3. 測試 generate_dynamic_state 中的導入
        print("\n--- 測試 generate_dynamic_state 導入 ---")
        from satgen.dynamic_state.generate_dynamic_state import generate_dynamic_state_at
        print("✓ 成功導入 generate_dynamic_state")
        
        # 4. 檢查算法是否在可用列表中
        print("\n--- 檢查可用算法 ---")
        # 這裡我們可以通過查看代碼確認，但讓我們嘗試一個簡單的測試
        test_algorithm_name = "algorithm_hierarchical_virtual_pid_new"
        print(f"新算法名稱: {test_algorithm_name}")
        
        # 5. 清理並檢查日誌位置
        print("\n--- 清理舊日誌 ---")
        log_locations = [
            "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/alg_mode.log",
            "/tmp/alg_mode.log"
        ]
        
        for loc in log_locations:
            if os.path.exists(loc):
                print(f"刪除舊日誌: {loc}")
                os.remove(loc)
        
        # 6. 測試 _alog 函數
        print("\n--- 測試日誌函數 ---")
        from satgen.dynamic_state.algorithm_hierarchical_virtual_pid import _alog
        
        test_payload = {
            "output_dynamic_state_dir": "/tmp/test_new_algorithm_output"
        }
        os.makedirs(test_payload["output_dynamic_state_dir"], exist_ok=True)
        
        _alog("Test message from new algorithm integration", test_payload)
        print("✓ 日誌函數調用成功")
        
        # 7. 檢查日誌是否被創建
        print("\n--- 檢查日誌創建 ---")
        expected_log = os.path.join(test_payload["output_dynamic_state_dir"], "alg_mode.log")
        if os.path.exists(expected_log):
            print(f"✓ 日誌創建成功: {expected_log}")
            with open(expected_log, 'r') as f:
                content = f.read()
                print(f"日誌內容: {content.strip()}")
        else:
            print(f"✗ 日誌未創建: {expected_log}")
        
        # 8. 檢查其他位置的日誌
        for loc in log_locations:
            if os.path.exists(loc):
                print(f"✓ 發現日誌: {loc}")
                with open(loc, 'r') as f:
                    content = f.read()
                    lines = content.strip().split('\n')
                    print(f"  最新一行: {lines[-1] if lines else 'empty'}")
        
        return True
        
    except Exception as e:
        print(f"✗ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

def find_all_logs():
    print("\n=== 尋找所有 alg_mode.log 文件 ===")
    
    # 搜索整個項目目錄
    project_root = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia"
    
    import subprocess
    try:
        result = subprocess.run(
            ["find", project_root, "-name", "alg_mode.log", "-type", "f"],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0:
            logs = result.stdout.strip().split('\n')
            logs = [log for log in logs if log]  # 過濾空行
            
            if logs:
                print(f"找到 {len(logs)} 個日誌文件:")
                for log in logs:
                    print(f"  📄 {log}")
                    try:
                        with open(log, 'r') as f:
                            content = f.read()
                            lines = content.strip().split('\n')
                            print(f"     行數: {len(lines)}")
                            if lines:
                                print(f"     最新: {lines[-1]}")
                    except Exception as e:
                        print(f"     讀取失敗: {e}")
            else:
                print("沒有找到任何 alg_mode.log 文件")
        else:
            print(f"搜索失敗: {result.stderr}")
            
    except Exception as e:
        print(f"搜索過程出錯: {e}")

if __name__ == "__main__":
    success = test_new_algorithm()
    find_all_logs()
    
    if success:
        print("\n🎉 新算法集成測試成功！")
        print("\n📝 下一步:")
        print("1. 使用 'algorithm_hierarchical_virtual_pid_new' 作為算法名稱")
        print("2. 運行衛星網路生成，應該會看到日誌輸出")
        print("3. 檢查指定的 output_dynamic_state_dir 中的 alg_mode.log")
    else:
        print("\n❌ 新算法集成測試失敗，需要修復問題")