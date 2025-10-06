#!/usr/bin/env python3
"""
診斷 _alog 函數的問題
"""
import os
import tempfile
from datetime import datetime

def _alog_debug(msg: str, payload: dict | None = None):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "Z"
    line = f"{ts} {msg}\n"
    
    print(f"[DEBUG] Writing log message: {msg}")
    print(f"[DEBUG] Timestamp: {ts}")
    print(f"[DEBUG] Payload: {payload}")

    # 1) 優先寫到 Hypatia 的輸出資料夾（最容易找到）
    paths = []
    if payload and "output_dynamic_state_dir" in payload and payload["output_dynamic_state_dir"]:
        odir = payload["output_dynamic_state_dir"]
        print(f"[DEBUG] Found output_dynamic_state_dir: {odir}")
        try:
            os.makedirs(odir, exist_ok=True)
            print(f"[DEBUG] Created directory: {odir}")
        except Exception as e:
            print(f"[DEBUG] Failed to create directory {odir}: {e}")
        paths.append(os.path.join(odir, "alg_mode.log"))
    else:
        print("[DEBUG] No output_dynamic_state_dir found in payload")

    # 2) 專案工作目錄
    cwd_path = os.path.join(os.getcwd(), "alg_mode.log")
    paths.append(cwd_path)
    print(f"[DEBUG] Current working directory path: {cwd_path}")
    
    # 3) 系統暫存
    temp_path = os.path.join(tempfile.gettempdir(), "alg_mode.log")
    paths.append(temp_path)
    print(f"[DEBUG] Temp directory path: {temp_path}")

    success_count = 0
    for i, p in enumerate(paths):
        print(f"[DEBUG] Trying path {i+1}: {p}")
        try:
            with open(p, "a", encoding="utf-8") as f:
                f.write(line)
            print(f"[DEBUG] Successfully wrote to: {p}")
            success_count += 1
        except Exception as e:
            print(f"[DEBUG] Failed to write to {p}: {e}")
    
    print(f"[DEBUG] Successfully wrote to {success_count}/{len(paths)} paths")
    return success_count > 0

if __name__ == "__main__":
    print("=== Testing _alog function ===")
    
    # Test 1: No payload
    print("\n--- Test 1: No payload ---")
    _alog_debug("Test message without payload")
    
    # Test 2: Empty payload
    print("\n--- Test 2: Empty payload ---")
    _alog_debug("Test message with empty payload", {})
    
    # Test 3: With output_dynamic_state_dir
    print("\n--- Test 3: With output_dynamic_state_dir ---")
    test_payload = {
        "output_dynamic_state_dir": "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/test_log_output"
    }
    _alog_debug("Test message with output_dynamic_state_dir", test_payload)
    
    # Test 4: With a realistic path
    print("\n--- Test 4: With realistic satellite output path ---")
    realistic_payload = {
        "output_dynamic_state_dir": "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/dynamic_state_100ms_for_10s"
    }
    _alog_debug("Test message with realistic path", realistic_payload)
    
    print("\n=== Checking created log files ===")
    # Check if any log files were created
    possible_locations = [
        "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/alg_mode.log",
        "/tmp/alg_mode.log",
        "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/test_log_output/alg_mode.log",
        "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia/paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_clean_fixed_fast/dynamic_state_100ms_for_10s/alg_mode.log"
    ]
    
    for loc in possible_locations:
        if os.path.exists(loc):
            print(f"✓ Found log file: {loc}")
            with open(loc, 'r') as f:
                content = f.read()
                print(f"  Content: {content.strip()}")
        else:
            print(f"✗ No log file at: {loc}")