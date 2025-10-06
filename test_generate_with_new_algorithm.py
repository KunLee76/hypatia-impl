#!/usr/bin/env python3
"""
使用新算法生成衛星網路狀態的測試腳本
"""
import os
import sys
import subprocess
import time

def generate_with_new_algorithm():
    print("=== 使用新算法生成衛星網路狀態 ===")
    
    # 設置路徑
    base_dir = "/home/w2cnlab/ssd2t/kun/Leo/kun_hypatia"
    output_dir = os.path.join(base_dir, "paper/satellite_networks_state/gen_data/25x25_algorithm_hierarchical_virtual_pid_new_test")
    
    print(f"輸出目錄: {output_dir}")
    
    # 清理舊輸出
    if os.path.exists(output_dir):
        print("清理舊輸出目錄...")
        import shutil
        shutil.rmtree(output_dir)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 清理舊日誌
    log_files = [
        os.path.join(base_dir, "alg_mode.log"),
        "/tmp/alg_mode.log"
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            print(f"清理舊日誌: {log_file}")
            os.remove(log_file)
    
    # 生成配置腳本
    config_script = f"""#!/usr/bin/env python3

import math
import ephem
from astropy import units as u
from astropy.time import Time
from satgen.constellation import *

# 25x25 Plus Grid constellation
name = "25x25_new_algorithm"
description = "25x25 Plus Grid constellation using new algorithm"

# Constellation parameters
ECCENTRICITY = 0.0001
ARG_OF_PERIGEE_DEGREE = 90.0
MEAN_MOTION_REV_PER_DAY = 15.19
ALTITUDE_M = 550000

constellation = Constellation(
    name,
    description,
    ECCENTRICITY, 
    ARG_OF_PERIGEE_DEGREE,
    MEAN_MOTION_REV_PER_DAY
)

# Create 25x25 grid
for orbit_id in range(25):
    inclination_degree = 53
    raan_degree = orbit_id * 360.0 / 25
    
    for sat_in_orbit in range(25):
        argument_of_latitude_degree = sat_in_orbit * 360.0 / 25
        constellation.add_satellite(
            sat_id=orbit_id * 25 + sat_in_orbit,
            orbit_id=orbit_id,
            inclination_degree=inclination_degree,
            raan_degree=raan_degree,
            argument_of_latitude_degree=argument_of_latitude_degree,
            altitude_m=ALTITUDE_M
        )

# Ground stations (simplified)
ground_stations = []
for i, (name, lat, lon) in enumerate([
    ("Tokyo", 35.6762, 139.6503),
    ("Shanghai", 31.2304, 121.4737),
    ("Manila", 14.5995, 120.9842),
    ("Dalian", 38.9140, 121.6147)
]):
    ground_stations.append({{
        "gid": i,
        "name": name,
        "latitude_degrees_of_center_of_antenna": lat,
        "longitude_degrees_of_center_of_antenna": lon,
        "elevation_angle_degrees": 30.0,
        "cartesian_antenna_count": 1,
        "max_GSL_length_m": 10000000,
        "max_GSL_dx_m": 10000000,
        "max_GSL_dy_m": 10000000,
        "antenna_diameter_m": 1.0,
        "max_tx_rate_megabit_per_s": 1.0,
        "max_rx_rate_megabit_per_s": 1.0
    }})

# ISL configuration
max_isl_length_m = 5016062.992
max_gsl_length_m = 10000000

# Time configuration  
simulation_end_time_s = 10  # 只生成10秒
time_step_ms = 100

print("Configuration loaded for new algorithm test")
"""
    
    config_file = os.path.join(output_dir, "generate_config.py")
    with open(config_file, 'w') as f:
        f.write(config_script)
    
    print(f"配置文件創建: {config_file}")
    
    # 運行生成命令
    print("\n--- 運行衛星網路生成 ---")
    
    cmd = [
        "python", "-m", "satgen.extend",
        config_file,
        output_dir,
        "--algorithm", "algorithm_hierarchical_virtual_pid_new",
        "--threads", "1"
    ]
    
    print(f"運行命令: {' '.join(cmd)}")
    
    try:
        # 切換到正確的目錄
        os.chdir(os.path.join(base_dir, "satgenpy"))
        
        # 設置環境
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(base_dir, "satgenpy")
        
        start_time = time.time()
        
        # 運行命令
        result = subprocess.run(
            cmd,
            cwd=os.path.join(base_dir, "satgenpy"),
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5分鐘超時
        )
        
        end_time = time.time()
        print(f"生成完成，耗時: {end_time - start_time:.2f} 秒")
        
        if result.returncode == 0:
            print("✓ 生成成功！")
            print("標準輸出:")
            print(result.stdout[-1000:])  # 只顯示最後1000字符
        else:
            print("✗ 生成失敗")
            print("錯誤輸出:")
            print(result.stderr)
            print("標準輸出:")
            print(result.stdout)
        
    except subprocess.TimeoutExpired:
        print("✗ 生成超時（5分鐘）")
    except Exception as e:
        print(f"✗ 生成過程出錯: {e}")
    
    # 檢查輸出和日誌
    print("\n--- 檢查輸出結果 ---")
    
    # 檢查生成的文件
    expected_files = [
        "satellites.txt",
        "ground_stations.txt", 
        "isls.txt",
        "dynamic_state_100ms_for_10s"
    ]
    
    for file_name in expected_files:
        file_path = os.path.join(output_dir, file_name)
        if os.path.exists(file_path):
            print(f"✓ 找到: {file_name}")
            if os.path.isdir(file_path):
                files = os.listdir(file_path)
                print(f"  包含 {len(files)} 個文件")
        else:
            print(f"✗ 缺失: {file_name}")
    
    # 檢查日誌
    print("\n--- 檢查算法日誌 ---")
    
    possible_log_locations = [
        os.path.join(output_dir, "dynamic_state_100ms_for_10s", "alg_mode.log"),
        os.path.join(output_dir, "alg_mode.log"),
        os.path.join(base_dir, "alg_mode.log"),
        "/tmp/alg_mode.log"
    ]
    
    for log_path in possible_log_locations:
        if os.path.exists(log_path):
            print(f"✓ 找到日誌: {log_path}")
            with open(log_path, 'r') as f:
                content = f.read()
                lines = content.strip().split('\\n')
                print(f"  行數: {len(lines)}")
                print("  內容預覽:")
                for line in lines[:5]:  # 顯示前5行
                    print(f"    {line}")
                if len(lines) > 5:
                    print("    ...")
                    for line in lines[-3:]:  # 顯示最後3行
                        print(f"    {line}")
            break
    else:
        print("✗ 沒有找到任何日誌文件")
    
    return True

if __name__ == "__main__":
    print("🚀 新算法衛星網路生成測試")
    print("這個腳本將使用你的新算法生成一個小型衛星網路")
    
    try:
        success = generate_with_new_algorithm()
        
        if success:
            print("\\n🎉 測試完成！")
            print("\\n📂 檢查生成的文件:")
            print("1. 衛星網路數據文件")
            print("2. 動態狀態文件") 
            print("3. 算法日誌文件 (alg_mode.log)")
            print("\\n💡 如果看到日誌內容，說明你的新算法已經在工作了！")
        else:
            print("\\n❌ 測試過程中遇到問題")
            
    except KeyboardInterrupt:
        print("\\n⏹️  用戶中斷")
    except Exception as e:
        print(f"\\n💥 未預期的錯誤: {e}")
        import traceback
        traceback.print_exc()