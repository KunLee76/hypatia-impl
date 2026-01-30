# 隨機 ISL 失效實驗指南

## 目錄
1. [實驗概述](#實驗概述)
2. [與局部失效的差異](#與局部失效的差異)
3. [實驗流程](#實驗流程)
4. [文件結構](#文件結構)
5. [實施細節](#實施細節)

---

## 實驗概述

**目的：** 研究全網隨機分布的 ISL 失效對衛星網路控制信令的影響

**場景設計：**
- **3 種失效概率：** 1%, 5%, 10%
- **6 種 K 值：** 1, 2, 4, 6, 8, 999
- **總實驗數：** 18 個場景

**與之前局部失效實驗的對比：**

| 實驗類型 | 場景數 | 失效模式 | 目錄命名格式 |
|---------|-------|---------|------------|
| **局部失效** | 30 (5×6) | 特定區域密集失效 (L1-L4) | `starlink_550_isls_failure_l*_27deg_k*` |
| **隨機失效** | 18 (3×6) | 全網隨機分布失效 (1%, 5%, 10%) | `starlink_550_isls_random_p*_27deg_k*` |

---

## 與局部失效的差異

### 1. 失效模式

**局部失效 (Localized Failures):**
```
scenario_l1: 模擬單一衛星全部 ISL 失效
scenario_l2: 模擬區域集中式失效（如衛星群故障）
scenario_l3: 模擬更大範圍的區域失效
scenario_l4: 模擬極端的密集失效區域
```

**隨機失效 (Random Distributed Failures):**
```
scenario_p1:  1% ISL 隨機失效（~32 條 ISL）
scenario_p5:  5% ISL 隨機失效（~158 條 ISL）
scenario_p10: 10% ISL 隨機失效（~317 條 ISL）
```

### 2. 實現方式

**局部失效：**
- 預先生成特定失效模式
- 從 `input_data/failure_scenarios/` 複製配置文件
- 失效 ISL 固定且集中

**隨機失效：**
- 動態生成 ISL 拓撲
- 使用 `generate_plus_grid_isls_with_random_failures()` 函數
- 失效 ISL 隨機分布（固定種子保證可重複性）

### 3. 臨時統計目錄

**局部失效：**
```
analytic_result/temp_grhr_failure_l1_k1/
analytic_result/temp_grhr_failure_l2_k1/
...
```

**隨機失效：**
```
analytic_result/temp_grhr_random_p1_k1/
analytic_result/temp_grhr_random_p5_k1/
...
```

### 4. 最終統計文件

**局部失效：**
```
analytic_result/hierarchical_gid_27deg_failure_l1_k1_signaling_stats.json
```

**隨機失效：**
```
analytic_result/hierarchical_gid_27deg_random_p1_k1_signaling_stats.json
```

---

## 實驗流程

### 階段 1: 功能測試

```bash
# 測試隨機失效功能是否正常
python test_random_isl_failures.py
```

**測試內容：**
- ✅ Starlink (53° 非極地星座) 隨機失效
- ✅ OneWeb (87.9° 極地星座) 隨機失效
- ✅ 隨機種子可重複性
- ✅ 極端情況 (0% 和 100% 失效率)

### 階段 2: 執行實驗

```bash
# 執行 18 個隨機失效場景實驗
./run_random_failure_scenarios_20s.sh
```

**實驗配置：**
- 模擬時長: 20 秒
- 時間步長: 100 毫秒 (200 個 snapshot)
- 網格大小: 27°
- 並行線程: 10
- 隨機種子: 42 (固定，確保可重複性)

**預估時間：** ~4.5 小時 (18 個實驗 × 15 分鐘/個)

### 階段 3: 合併統計數據

```bash
# 合併所有場景的統計數據
./merge_all_random_failure_scenarios.sh
```

**輸入：**
```
analytic_result/temp_grhr_random_p*_k*/grhr_stats_pid*_tid*.json
```

**輸出：**
```
analytic_result/hierarchical_gid_27deg_random_p1_k1_signaling_stats.json
analytic_result/hierarchical_gid_27deg_random_p5_k1_signaling_stats.json
...
analytic_result/hierarchical_gid_27deg_random_p10_k999_signaling_stats.json
```

### 階段 4: 生成分析圖表

```bash
# 生成 K 值比較圖表
python analyze_random_failure_scenarios.py
```

**輸出圖表：**
```
k_parameter_analysis/k_comparison_random_p1.png   # 1% 失效率下的 K 值比較
k_parameter_analysis/k_comparison_random_p5.png   # 5% 失效率下的 K 值比較
k_parameter_analysis/k_comparison_random_p10.png  # 10% 失效率下的 K 值比較
```

---

## 文件結構

### 1. 核心代碼修改

**新增功能：**

| 文件 | 功能 | 修改內容 |
|------|-----|---------|
| `satgenpy/satgen/isls/generate_plus_grid_isls.py` | ISL 拓撲生成 | ✅ 新增 `generate_plus_grid_isls_with_random_failures()` |
| `paper/satellite_networks_state/main_helper.py` | 場景配置 | ✅ 添加 `isls_random_p*` 識別邏輯 |
| `satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_gid.py` | 統計收集 | ✅ 添加 `random_p*` 場景識別 |

### 2. 實驗腳本

| 文件 | 用途 |
|------|-----|
| `test_random_isl_failures.py` | 功能測試腳本 |
| `run_random_failure_scenarios_20s.sh` | 批量執行 18 個實驗 |
| `merge_all_random_failure_scenarios.sh` | 合併統計數據（待創建） |
| `analyze_random_failure_scenarios.py` | 生成分析圖表（待創建） |

### 3. 輸出目錄

```
kun_hypatia/
├── gen_data/                                    # 場景數據
│   ├── starlink_550_isls_random_p1_27deg_k1/
│   ├── starlink_550_isls_random_p1_27deg_k2/
│   ├── ...
│   ├── starlink_550_isls_random_p10_27deg_k999/
│
├── analytic_result/                             # 統計數據
│   ├── temp_grhr_random_p1_k1/                 # 臨時統計目錄
│   │   └── grhr_stats_pid*_tid*.json
│   ├── hierarchical_gid_27deg_random_p1_k1_signaling_stats.json
│   ├── ...
│   └── hierarchical_gid_27deg_random_p10_k999_signaling_stats.json
│
├── k_parameter_analysis/                        # 分析圖表
│   ├── k_comparison_random_p1.png
│   ├── k_comparison_random_p5.png
│   └── k_comparison_random_p10.png
│
└── logs/                                        # 執行日誌
    ├── random_p1_k1.log
    ├── random_p1_k2.log
    └── ...
```

---

## 實施細節

### 1. 隨機失效函數

**函數簽名：**
```python
def generate_plus_grid_isls_with_random_failures(
    output_filename_isls,
    n_orbits,
    n_sats_per_orbit,
    isl_shift,
    failure_probability,
    random_seed=None,
    idx_offset=0,
    inclination_degree=None,
    use_polar_version=None
):
```

**實現邏輯：**
1. 生成完整的 ISL 拓撲（自動選擇 polar/original 版本）
2. 對每條 ISL 進行隨機抽樣（根據 `failure_probability`）
3. 保留存活的 ISL 寫入輸出文件
4. 使用固定隨機種子確保可重複性

**示例：**
```python
# Starlink-550: 1% 失效率
surviving_isls = generate_plus_grid_isls_with_random_failures(
    "isls.txt",
    n_orbits=72,
    n_sats_per_orbit=22,
    isl_shift=0,
    failure_probability=0.01,  # 1%
    random_seed=42,             # 固定種子
    inclination_degree=53.0,
    use_polar_version=None      # Auto-detect
)
# 輸出: Total ISLs: 3168, Failed: 34 (1.07%), Surviving: 3134 (98.93%)
```

### 2. 場景識別

**在 `algorithm_hierarchical_virtual_gid.py` 中：**

```python
# 從目錄名稱提取場景資訊
if "isls_failure_" in output_dir:
    match = re.search(r'isls_failure_(l\d+)', output_dir)
    if match:
        scenario_info = f"_failure_{match.group(1)}"
elif "isls_random_" in output_dir:
    match = re.search(r'isls_random_(p\d+)', output_dir)
    if match:
        scenario_info = f"_random_{match.group(1)}"
```

**臨時目錄命名：**
```python
temp_dir_name = "temp_grhr"
if scenario_info:
    temp_dir_name += scenario_info  # temp_grhr_random_p1
if k_best is not None:
    temp_dir_name += f"_k{k_best}"  # temp_grhr_random_p1_k1
```

### 3. Main Helper 配置

**在 `main_helper.py` 中：**

```python
elif isl_selection.startswith("isls_random_"):
    # 解析失效率
    match = re.search(r'isls_random_p(\d+)', isl_selection)
    failure_percent = int(match.group(1))
    failure_probability = failure_percent / 100.0
    
    # 動態生成隨機失效 ISL 拓撲
    satgen.generate_plus_grid_isls_with_random_failures(
        output_file,
        self.NUM_ORBS,
        self.NUM_SATS_PER_ORB,
        isl_shift=0,
        failure_probability=failure_probability,
        random_seed=42,  # 固定種子
        inclination_degree=self.INCLINATION_DEGREE,
        use_polar_version=None
    )
```

### 4. 命令行示例

**單個實驗：**
```bash
# Random p1 (1%), K=4, 27° grid
export SATGEN_GRID_DEG=27
export K_BEST_GATEWAYS=4

python paper/satellite_networks_state/main_starlink_550.py \
    20 \
    100 \
    isls_random_p1 \
    ground_stations_top_100 \
    algorithm_hierarchical_virtual_gid \
    10 \
    27 \
    4
```

**批量實驗：**
```bash
# 執行所有 18 個場景
./run_random_failure_scenarios_20s.sh
```

---

## 重要提醒

### ✅ 可重複性
- 隨機失效使用固定種子 (`random_seed=42`)
- 相同參數重複執行會得到完全一致的結果
- 測試腳本已驗證種子功能正常

### ✅ 與舊實驗隔離
- 參數命名不同：`isls_random_p*` vs `isls_failure_l*`
- 輸出目錄分離：不會覆蓋之前的 30 個局部失效實驗
- 統計文件獨立：`random_p*` vs `failure_l*`

### ✅ 相容性
- 支援 Starlink (53° 非極地星座) - 使用 original 版本
- 支援 OneWeb (87.9° 極地星座) - 使用 polar 版本
- 自動偵測星座類型（基於 inclination_degree）

### ⚠️ 執行時間
- 18 個實驗預估 ~4.5 小時
- 建議在伺服器上執行，避免中斷
- 每個實驗獨立，可中途重啟

### ⚠️ 磁碟空間
- 每個場景約 500MB-1GB（包含 fstate 文件）
- 18 個場景總計約 10-20GB
- 確保 `gen_data/` 目錄有足夠空間

---

## 下一步

### 1. 執行實驗
```bash
./run_random_failure_scenarios_20s.sh
```

### 2. 合併統計（需創建腳本）
```bash
./merge_all_random_failure_scenarios.sh
```

### 3. 生成分析（需創建腳本）
```bash
python analyze_random_failure_scenarios.py
```

### 4. 對比分析（可選）
創建腳本對比 **局部失效** vs **隨機失效** 的控制信令差異

---

## 常見問題

**Q1: 為什麼隨機失效需要動態生成，而局部失效使用預先生成的文件？**

A: 
- **局部失效：** 特定區域模式，可預先設計（如 L1-L4）
- **隨機失效：** 每次依概率隨機選擇，無法預先窮舉所有組合

**Q2: 隨機失效的實際失效率會完全等於設定值嗎？**

A: 不完全相等。由於隨機抽樣的統計特性，實際失效率會在設定值附近波動：
- 1% 失效率：實際約 0.9%-1.1%
- 5% 失效率：實際約 4.5%-5.5%
- 10% 失效率：實際約 9.5%-10.5%

測試結果顯示誤差在 ±1% 以內。

**Q3: 舊的 30 個局部失效實驗需要重跑嗎？**

A: ❌ **不需要！** 隨機失效實驗完全獨立：
- 不同的 ISL selection 參數 (`isls_random_p*` vs `isls_failure_l*`)
- 不同的輸出目錄
- 不同的統計文件命名

**Q4: 如何確保實驗結果的一致性？**

A: 
- ✅ 使用固定隨機種子 (`random_seed=42`)
- ✅ 測試腳本已驗證可重複性
- ✅ 相同參數執行多次結果完全一致

**Q5: 如果實驗中途中斷怎麼辦？**

A: 可以註釋掉 `run_random_failure_scenarios_20s.sh` 中已完成的場景，重新執行未完成的部分。每個實驗獨立，不影響其他實驗。

---

## 版本歷史

- **2026-01-28:** 完成隨機失效功能實現
  - 新增 `generate_plus_grid_isls_with_random_failures()` 函數
  - 更新場景識別邏輯
  - 創建測試腳本和實驗腳本
  - 驗證 Starlink/OneWeb 相容性

---

## 聯絡資訊

如有問題或建議，請參考：
- 局部失效實驗文檔：`ISL_FAILURE_EXPERIMENT_WORKFLOW.md`
- 測試腳本：`test_random_isl_failures.py`
- 實驗腳本：`run_random_failure_scenarios_20s.sh`
