# LoHi 演算法使用指南

## 指令格式

### 基本格式（與 GID 相同）
```bash
python main_starlink_550.py [duration_s] [time_step_ms] [isl_config] [gs_config] [algorithm] [num_threads]
```

**重要差異**：
- LoHi **不需要** `grid_deg` 參數（第 7 個參數）
- LoHi 使用固定的 p×s (6×10) 分群，不是網格分群

---

## 使用範例

### 1. LoHi 演算法（20秒模擬，100ms步長）
```bash
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

python main_starlink_550.py \
    20 \
    100 \
    isls_plus_grid \
    ground_stations_top_100 \
    algorithm_lohi \
    10
```

### 2. GID 演算法（需要 grid_deg）
```bash
python main_starlink_550.py \
    20 \
    100 \
    isls_plus_grid \
    ground_stations_top_100 \
    algorithm_hierarchical_virtual_gid \
    10 \
    21
```

### 3. GID Dijkstra 版本（需要 grid_deg）
```bash
python main_starlink_550.py \
    20 \
    100 \
    isls_plus_grid \
    ground_stations_top_100 \
    algorithm_hierarchical_virtual_gid_dijkstra \
    10 \
    21
```

---

## 參數說明

| 參數位置 | 參數名稱 | LoHi | GID/GID-Dijkstra | 說明 |
|---------|---------|------|------------------|------|
| 1 | duration_s | ✓ | ✓ | 模擬時長（秒）|
| 2 | time_step_ms | ✓ | ✓ | 時間步長（毫秒）|
| 3 | isl_config | ✓ | ✓ | ISL 配置：`isls_plus_grid` 或 `isls_none` |
| 4 | gs_config | ✓ | ✓ | 地面站配置：`ground_stations_top_100` 等 |
| 5 | algorithm | `algorithm_lohi` | `algorithm_hierarchical_virtual_gid[_dijkstra]` | 演算法名稱 |
| 6 | num_threads | ✓ | ✓ | 執行緒數 |
| 7 | grid_deg | ✗ **不需要** | ✓ **必須** | 網格大小（僅 GID 需要）|

---

## 完整比較指令

### 比較三種演算法（建議配置）

#### 1. Floyd-Warshall Baseline
```bash
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_free_one_only_over_isls_with_stats 10
```

#### 2. LoHi Baseline（文獻方法）
```bash
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10
```

#### 3. GID（你的方法，測試不同網格大小）
```bash
# 測試 15 度網格
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_gid_dijkstra 10 15

# 測試 21 度網格
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_gid_dijkstra 10 21

# 測試 30 度網格
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_gid_dijkstra 10 30
```

---

## 輸出目錄結構

### LoHi 輸出
```
gen_data/
└── starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_lohi/
    ├── dynamic_state_*.txt
    ├── fstate_*.txt
    └── (其他檔案)

analytic_result/
└── lohi_signaling_stats_pure_p6_s10.json  # LoHi 統計
```

### GID 輸出
```
gen_data/
└── starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_gid_dijkstra_21deg/
    ├── dynamic_state_*.txt
    ├── fstate_*.txt
    └── (其他檔案)

analytic_result/
└── hierarchical_gid_dijkstra_21deg_signaling_stats.json  # GID 統計
```

---

## 環境變數（可選配置）

### LoHi 參數調整
```bash
# 群內負載感知權重
export LOHI_BETA_Q=1.0              # 佇列延遲權重（預設 1.0）
export LOHI_BETA_S=0.0              # 靜態偏移（預設 0.0）

# 管理衛星跳點
export LOHI_ENFORCE_MGMT_HOP=1      # 1=強制，0=關閉（預設 1）

# 群級成本模型
export LOHI_TG_MODE=constant        # constant 或 off（預設 constant）
export LOHI_TG_CONST_NG=10          # 預估 DATA 物件數（預設 10）
export LOHI_TG_CONST_LAVG=1500      # 平均物件大小 bytes（預設 1500）
export LOHI_LINK_BW_BPS=1000000000  # 頻寬 1 Gbps（預設）
export LOHI_TG_SCALE=1.0            # 縮放係數（預設 1.0）

# 執行範例（關閉管理跳點）
export LOHI_ENFORCE_MGMT_HOP=0
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10
```

### GID 參數調整
```bash
# 網格大小（也可用指令參數）
export SATGEN_GRID_DEG=21

# 執行範例
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_gid_dijkstra 10 21
```

---

## 常見問題

### Q1: LoHi 需要指定 grid_deg 嗎？
**A:** 不需要！LoHi 使用固定的 6×10 平面區塊分群，不依賴網格大小。

### Q2: 如果我加了 grid_deg 參數會怎樣？
**A:** 系統會忽略它，因為 LoHi 不使用這個參數。但建議不要加，避免混淆。

### Q3: 我之前用的 `algorithm_hierarchical_virtual_pid` 還能用嗎？
**A:** 應該改用 `algorithm_hierarchical_virtual_gid` 或 `algorithm_hierarchical_virtual_gid_dijkstra`，因為已經完成 PID → GID 重構。

### Q4: LoHi 的統計輸出在哪裡？
**A:** `analytic_result/lohi_signaling_stats_pure_p6_s10.json`

### Q5: 如何比較三種演算法的性能？
**A:** 
1. 分別運行三種演算法生成動態狀態
2. 檢查 `analytic_result/` 目錄下的統計檔案
3. 使用 `paper/satgenpy_analysis/` 下的分析腳本

---

## 快速測試腳本

創建 `run_lohi_test.sh`：
```bash
#!/bin/bash
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

echo "運行 LoHi 演算法測試..."
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10

echo "檢查輸出..."
ls -lh gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_lohi/
ls -lh analytic_result/lohi_signaling_stats_pure_p6_s10.json

echo "完成！"
```

---

## 批次執行腳本

創建 `run_all_algorithms.sh` 比較所有演算法：
```bash
#!/bin/bash
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

echo "==================================="
echo "運行所有演算法進行比較"
echo "==================================="

# 1. Floyd-Warshall Baseline
echo -e "\n[1/3] Running Floyd-Warshall..."
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 \
    algorithm_free_one_only_over_isls_with_stats 10

# 2. LoHi Baseline
echo -e "\n[2/3] Running LoHi..."
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 \
    algorithm_lohi 10

# 3. GID (你的方法)
echo -e "\n[3/3] Running GID (21deg)..."
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 \
    algorithm_hierarchical_virtual_gid_dijkstra 10 21

echo -e "\n==================================="
echo "所有演算法執行完成！"
echo "==================================="
echo "檢查結果："
ls -lh analytic_result/
```

---

## 總結

| 演算法 | 指令 | grid_deg | 分群方式 |
|--------|------|----------|----------|
| Floyd-Warshall | `python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_free_one_only_over_isls_with_stats 10` | N/A | 無分群 |
| **LoHi** | `python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10` | **不需要** | 6×10 平面區塊 |
| GID | `python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_gid_dijkstra 10 21` | **必須** | 網格（21度）|

**關鍵差異**：LoHi 不需要第 7 個參數（grid_deg），直接 6 個參數即可！
