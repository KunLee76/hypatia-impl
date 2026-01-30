# ISL 集中式失效實驗完整流程

**實驗時間：** 2026-01-22 ~ 2026-01-23  
**實驗類型：** 衛星 861 的局部 ISL 失效（L1-L4）  
**參數配置：** 5 場景 × 6 K 值 = 30 個實驗

---

## 階段 1：ISL 失效場景生成

### 腳本：`generate_isl_failure_scenarios.py`

**功能：**
- 生成衛星 861 的 ISL 失效配置
- 輸出：4 個失效場景文件

**執行命令：**
```bash
python generate_isl_failure_scenarios.py
```

**輸出文件：**
```
satgenpy/satgen/isls/
├── isls_failure_l1.py    # 1 條 ISL 失效
├── isls_failure_l2.py    # 2 條 ISL 失效
├── isls_failure_l3.py    # 3 條 ISL 失效
└── isls_failure_l4.py    # 4 條 ISL 失效（節點 861 完全隔離）
```

**關鍵代碼位置：**
- `satgenpy/satgen/isls/generate_plus_grid_isls.py`
- 函數：`generate_plus_grid_isls_with_config()`

---

## 階段 2：運行實驗（生成 fstate 和統計數據）

### 腳本：`run_failure_scenarios_20s.sh`

**功能：**
- 運行 30 個實驗（5 場景 × 6 K 值）
- 每個實驗 20 秒，時間步 100ms（200 snapshots）
- 自動生成控制信令統計

**執行命令：**
```bash
cd /home/kun/ssd2t/Leo/kun_hypatia
nohup bash run_failure_scenarios_20s.sh > logs/failure_scenarios_$(date +%Y%m%d_%H%M%S).log 2>&1 &
```

**配置參數：**
```bash
# 場景定義
SCENARIOS=(
    "baseline:0"     # 無失效
    "l1:1"           # 1 條 ISL 失效
    "l2:2"           # 2 條 ISL 失效
    "l3:3"           # 3 條 ISL 失效
    "l4:4"           # 4 條 ISL 失效
)

# K 值範圍
K_VALUES=(1 2 4 6 8 999)

# 模擬參數
DURATION=20          # 20 秒
TIME_STEP_MS=100     # 100ms
GRID_DEG=27          # 27°
```

**輸出目錄結構：**
```
paper/satellite_networks_state/
├── gen_data/
│   ├── starlink_550_27deg_k1/                              # Baseline K=1
│   ├── starlink_550_27deg_k2/                              # Baseline K=2
│   ├── ...
│   ├── starlink_550_isls_failure_l1_27deg_k1/              # L1 K=1
│   ├── starlink_550_isls_failure_l1_27deg_k2/              # L1 K=2
│   └── .../dynamic_state_100ms_for_20s/
│       ├── fstate_0.txt
│       ├── fstate_100000000.txt
│       └── ...                                             # 200 個 fstate 文件
│
└── analytic_result/
    ├── temp_grhr_k1/                                       # Baseline K=1 臨時統計
    │   ├── grhr_stats_pid*_tid*.json                       # 10 個進程的統計文件
    │   └── ...
    ├── temp_grhr_failure_l1_k1/                            # L1 K=1 臨時統計
    └── .../
```

**關鍵點：**
1. **並行處理**：10 個進程同時生成 fstate
2. **統計自動收集**：每個進程生成獨立的統計文件
3. **命名規則**：`temp_grhr_failure_{scenario}_k{K值}/`

**預計耗時：** ~7.5 小時（30 個實驗，每個約 15 分鐘）

---

## 階段 3：合併統計文件

### 腳本 A：`merge_failure_scenario.sh` （單一場景）

**功能：**
- 合併單一場景的所有進程統計文件
- 去重（使用 `(snapshot, time_ms, event, detail)` 作為唯一鍵）

**執行命令：**
```bash
cd paper/satellite_networks_state
bash merge_failure_scenario.sh temp_grhr_failure_l1_k8
```

**處理流程：**
1. 讀取第一個 JSON 文件獲取元數據（grid_deg, k_best, scenario）
2. 自動生成輸出文件名（如 `hierarchical_gid_27deg_failure_l1_k8_signaling_stats.json`）
3. 合併所有進程的事件，並去重
4. 重新計算摘要統計

**輸出：**
```
analytic_result/hierarchical_gid_27deg_failure_l1_k8_signaling_stats.json
```

### 腳本 B：`merge_all_failure_scenarios.sh` （批量合併）

**功能：**
- 自動找到所有 `temp_grhr*` 目錄
- 對每個目錄調用 `merge_failure_scenario.sh`

**執行命令：**
```bash
cd paper/satellite_networks_state
bash merge_all_failure_scenarios.sh
```

**輸出示例：**
```
==================================================
批量合併失效場景統計
==================================================

[1] 處理: temp_grhr_failure_l1_k1
  ✓ 成功

[2] 處理: temp_grhr_failure_l1_k2
  ✓ 成功

...

==================================================
合併摘要
==================================================
總數: 30
成功: 30
失敗: 0
==================================================
```

**關鍵修復：**
- **去重邏輯**：從 `(snapshot, time_ms, event)` 改為 `(snapshot, time_ms, event, detail_json)`
- **原因**：避免多進程重複記錄同一事件

---

## 階段 4：分析與可視化

### 腳本：`analyze_failure_scenarios.py`

**功能：**
- 讀取所有合併後的統計文件
- 生成 K 值比較圖表（每個場景一張）
- 生成文字報告

**執行命令：**
```bash
python analyze_failure_scenarios.py
```

**輸出：**
```
k_parameter_analysis/
├── k_comparison_baseline.png       # Baseline 場景，比較 K=1~999
├── k_comparison_l1.png             # L1 場景，比較 K=1~999
├── k_comparison_l2.png             # L2 場景，比較 K=1~999
├── k_comparison_l3.png             # L3 場景，比較 K=1~999
├── k_comparison_l4.png             # L4 場景，比較 K=1~999
└── failure_scenarios_comparison_report.txt
```

**每張圖包含 4 個子圖：**
1. **總控制信令**（MB）
2. **事件類型分佈**（Gateway/Routing/GID）
3. **Gateway 更新開銷**（MB）
4. **相對於 K=1 的變化百分比**

**關鍵修改：**
- **圖表結構改變**：從「同一 K 值，比較不同場景」改為「同一場景，比較不同 K 值」
- **原因**：L1/L2/L3/L4 控制信令幾乎相同，無法體現差異；K 值影響更明顯

---

## 核心代碼修改記錄

### 1. **algorithm_hierarchical_virtual_gid.py**

**位置：** `satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_gid.py`

**修改內容：**
- **Lines 1349-1375**：提取 K 值和場景資訊，動態生成臨時目錄名
- **Lines 1352 & 1440**：從 `_GCACHE.k_best` 讀取 K 值（修復 AttributeError）
- **Line 1387**：場景命名從 `.replace("_", "")` 改為 `.lstrip("_")`（保留中間下劃線）

**關鍵代碼：**
```python
# 提取 K 值
k_best = getattr(_GCACHE, 'k_best', None)

# 提取場景資訊
scenario_info = ""
if "isls_failure_" in output_dir:
    match = re.search(r'isls_failure_(l\d+)', output_dir)
    if match:
        scenario_info = f"_failure_{match.group(1)}"

# 動態命名臨時目錄
temp_dir_name = "temp_grhr"
if scenario_info:
    temp_dir_name += scenario_info
if k_best is not None:
    temp_dir_name += f"_k{k_best}"
```

### 2. **merge_signaling_stats.py**

**位置：** `merge_signaling_stats.py`

**修改內容：**
- **Lines 60-105**：去重邏輯加入 `detail` 欄位

**關鍵代碼：**
```python
# 去重鍵值
detail_json = json.dumps(detail, sort_keys=True) if detail else ''
key = (snapshot, time_ms, event_type, detail_json)
```

### 3. **analyze_failure_scenarios.py**

**修改內容：**
- **plot_comparisons()**：從「按 K 值分組」改為「按場景分組」
- **_generate_scenario_comparison_charts()**：X 軸改為 K 值
- **子圖 4**：從「vs Baseline」改為「vs K=1」

---

## 測試與驗證

### 單一場景測試：`test_single_failure_scenario.sh`

**功能：**
- 測試單一場景（L1, K=8, 20s）
- 驗證統計文件生成
- 檢查合併功能

**執行命令：**
```bash
bash test_single_failure_scenario.sh
```

**驗證項目：**
- ✅ fstate 文件數量：200 個
- ✅ 臨時統計文件：10 個（對應 10 個進程）
- ✅ 合併後事件數：≤ 200（無重複計數）
- ✅ K 值和場景正確記錄

---

## 實驗結果摘要

**統計驗證：**
```
Baseline (無失效):
  K=1~8: 444-452 事件
  K=999: 452 事件

Failure L1-L4 (失效場景):
  K=1~8: 672-673 事件
  K=999: 506 事件 ← 控制信令反而減少！
```

**關鍵發現：**
1. ✅ **K=999 在失效時信令降低**：Gateway 更新從 210 次降至 44 次
2. ✅ **L1/L2/L3/L4 影響相似**：失效數量對信令影響極小
3. ✅ **K 值影響顯著**：K=999 vs K=1 的差異約 25%

---

## 完整流程腳本執行順序

```bash
# ===== 準備階段 =====
# 1. 生成 ISL 失效場景配置
python generate_isl_failure_scenarios.py

# ===== 實驗執行階段 =====
# 2. 運行 30 個實驗（背景執行，約 7.5 小時）
cd /home/kun/ssd2t/Leo/kun_hypatia
nohup bash run_failure_scenarios_20s.sh > logs/failure_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# 3. 監控進度（可選）
tail -f logs/failure_*.log

# ===== 數據處理階段 =====
# 4. 批量合併統計文件
cd paper/satellite_networks_state
bash merge_all_failure_scenarios.sh

# 5. 驗證合併結果
ls -lh analytic_result/hierarchical_gid_27deg_*_signaling_stats.json | wc -l
# 應該有 30 個文件

# ===== 分析與可視化階段 =====
# 6. 生成比較圖表和報告
cd /home/kun/ssd2t/Leo/kun_hypatia
python analyze_failure_scenarios.py

# 7. 查看結果
ls -lh k_parameter_analysis/k_comparison_*.png
cat k_parameter_analysis/failure_scenarios_comparison_report.txt
```

---

## 關鍵文件清單

**實驗腳本：**
- `generate_isl_failure_scenarios.py` - ISL 失效場景生成
- `run_failure_scenarios_20s.sh` - 批量運行實驗
- `test_single_failure_scenario.sh` - 單場景測試

**數據處理：**
- `merge_failure_scenario.sh` - 單一場景合併
- `merge_all_failure_scenarios.sh` - 批量合併
- `merge_signaling_stats.py` - 通用合併工具（被上述腳本調用）

**分析可視化：**
- `analyze_failure_scenarios.py` - 生成圖表和報告

**核心算法：**
- `satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_gid.py` - 統計收集
- `satgenpy/satgen/isls/generate_plus_grid_isls.py` - ISL 生成與失效

**輸出結果：**
- `k_parameter_analysis/` - 圖表和報告
- `paper/satellite_networks_state/analytic_result/` - 統計 JSON 文件
- `logs/` - 實驗日誌

---

## 下一步：隨機失效實驗

**需要新增/修改的腳本：**
1. `generate_random_isl_failures.py` - 隨機失效場景生成
2. `run_random_failure_scenarios_20s.sh` - 隨機失效實驗運行
3. 修改 `algorithm_hierarchical_virtual_gid.py` - 識別 `isls_random_p*`
4. 修改 `analyze_failure_scenarios.py` - 支持隨機場景分析

**預計實驗數量：** 3 場景 × 6 K 值 = 18 個實驗
