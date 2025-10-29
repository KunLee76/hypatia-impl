# 網格尺寸實驗自動化指南

## 📋 概述

這份文件說明如何使用自動化腳本進行不同網格尺寸的 hierarchical 演算法實驗。

## 📁 相關檔案

1. **run_grid_experiments.sh** - 主要自動化實驗腳本
2. **rename_15deg_results.sh** - 重命名現有 15° 結果腳本
3. **main_starlink_550.py** - 已修改支援 grid_deg 參數
4. **main_helper.py** - 已修改支援 grid_deg 參數

## 🚀 使用步驟

### 步驟 1：重命名現有的 15° 結果（僅需執行一次）

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state
chmod +x rename_15deg_results.sh
./rename_15deg_results.sh
```

這會將現有的目錄重命名為：
- `starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_pid_15deg`
- `starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_pid_dijkstra_15deg`

### 步驟 2：執行自動化實驗

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state
chmod +x run_grid_experiments.sh
./run_grid_experiments.sh
```

### 步驟 3：監控進度

腳本會顯示：
- ✅ 當前進度百分比
- ⏱️ 每個任務的執行時間
- 🕐 預估剩餘時間
- 📊 完成後的統計資訊

## ⚙️ 自訂參數

如果你想修改實驗參數，編輯 `run_grid_experiments.sh` 的以下部分：

```bash
# 網格尺寸範圍（可以只測試部分尺寸）
GRID_SIZES=(16 17 18 19 20)  # 例如只測試 16-20°

# 模擬參數
DURATION_S=200          # 模擬時長
TIME_STEP_MS=100        # 時間步長
NUM_THREADS=4           # 執行緒數（建議設為 CPU 核心數）
```

## 📊 輸出結果

所有結果會保存在 `gen_data/` 目錄中，命名格式：

```
starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_pid_XXdeg/
starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_pid_dijkstra_XXdeg/
```

其中 `XX` 是網格大小（15, 16, 17, ..., 30）。

## 🔍 分析結果

實驗完成後，使用 `hypatia_multi_algorithm_analyzer.py` 進行分析：

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia
python hypatia_multi_algorithm_analyzer.py
```

## ⏱️ 預估時間

根據以往經驗：
- 單一網格尺寸單一演算法：約 30-60 分鐘
- 15 個網格尺寸 × 2 演算法 = 30 次執行
- **總預估時間：15-30 小時**

## 💡 執行策略建議

### 選項 1：完整序列執行（最安全）
```bash
./run_grid_experiments.sh
# 讓它跑一整夜或週末
```

### 選項 2：分批執行（平行化）
如果你想加速，可以在 3 個不同的 terminal 分別執行：

**Terminal 1:**
```bash
# 修改腳本，只跑 16-20°
GRID_SIZES=(16 17 18 19 20)
./run_grid_experiments.sh
```

**Terminal 2:**
```bash
# 修改腳本，只跑 21-25°
GRID_SIZES=(21 22 23 24 25)
./run_grid_experiments.sh
```

**Terminal 3:**
```bash
# 修改腳本，只跑 26-30°
GRID_SIZES=(26 27 28 29 30)
./run_grid_experiments.sh
```

## ⚠️ 注意事項

1. **磁盤空間**：確保至少有 60GB 可用空間
2. **序列執行**：腳本預設是一個接一個執行，不會過載系統
3. **錯誤處理**：如果某個任務失敗，腳本會繼續執行下一個
4. **中斷恢復**：如果中途中斷，可以修改 `GRID_SIZES` 陣列只跑未完成的尺寸

## 🐛 問題排查

### 如果腳本執行失敗

1. 檢查執行權限：
```bash
ls -l run_grid_experiments.sh
# 應該顯示 -rwxr-xr-x
```

2. 手動執行單一實驗測試：
```bash
python main_starlink_550.py 200 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_pid 4 16
```

3. 檢查環境變數：
```bash
echo $SATGEN_GRID_DEG
# 應該顯示你設定的網格大小
```

## 📈 後續分析

實驗完成後，你可以：

1. 比較不同網格尺寸的效能
2. 分析控制信令開銷
3. 視覺化結果（使用 analyzer）
4. 寫入論文

## 📞 技術細節

### 修改內容總結

1. **main_starlink_550.py**：新增第 7 個可選參數 `grid_deg`
2. **main_helper.py**：
   - 新增 `grid_deg` 參數（預設 15）
   - 輸出目錄自動加上 `_XXdeg` 後綴
   - 透過環境變數 `SATGEN_GRID_DEG` 傳給演算法
3. **algorithm_hierarchical_virtual_pid.py**：從環境變數讀取 `GRID_DEG`
4. **algorithm_hierarchical_virtual_pid_dijkstra.py**：從環境變數讀取 `GRID_DEG`

### 向後相容性

- 不提供 `grid_deg` 參數時，預設使用 15°
- 現有的手動執行方式仍然有效

## ✅ 檢查清單

執行實驗前確認：

- [ ] 已重命名現有的 15° 結果
- [ ] 腳本有執行權限
- [ ] 磁盤空間充足（至少 60GB）
- [ ] 確認模擬參數（duration, time_step）
- [ ] 選擇執行策略（序列或分批）
- [ ] 準備好長時間執行（建議夜間或週末）

祝實驗順利！🎉
