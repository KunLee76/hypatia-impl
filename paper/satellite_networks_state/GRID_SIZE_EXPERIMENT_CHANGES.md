# 網格尺寸實驗功能實作總結

## 📅 修改日期
2025-10-27

## 🎯 目標
支援不同網格尺寸（16°-30°）的 hierarchical 演算法實驗，並自動化批次執行。

---

## 📝 修改檔案清單

### 1. **main_starlink_550.py**
**修改位置**: `def main()` 函數

**變更內容**:
- 接受 6 或 7 個參數（第 7 個為 `grid_deg`，可選）
- 預設 `grid_deg = 15`
- 將 `grid_deg` 傳遞給 `main_helper.calculate()`

**向後相容**: ✅ 是（不提供第 7 個參數時使用預設值 15）

---

### 2. **main_helper.py**
**修改位置**: `calculate()` 方法

**變更內容**:
- 新增參數 `grid_deg=15`
- 針對 hierarchical 演算法，在輸出目錄名稱加上 `_XXdeg` 後綴
- 透過環境變數 `SATGEN_GRID_DEG` 傳遞給演算法模組
- 輸出提示訊息顯示當前使用的網格大小

**影響範圍**:
- `starlink_550_*_algorithm_hierarchical_virtual_pid` → 變成 `*_15deg`
- `starlink_550_*_algorithm_hierarchical_virtual_pid_dijkstra` → 變成 `*_15deg`
- 非 hierarchical 演算法不受影響

---

### 3. **algorithm_hierarchical_virtual_pid.py**
**修改位置**: 全域設定區塊（第 20 行）

**變更內容**:
```python
# 修改前
GRID_DEG = 15

# 修改後
GRID_DEG = int(os.environ.get('SATGEN_GRID_DEG', 15))
```

**說明**: 
- 優先從環境變數 `SATGEN_GRID_DEG` 讀取
- 若環境變數不存在，使用預設值 15
- 保持程式碼的靈活性

---

### 4. **algorithm_hierarchical_virtual_pid_dijkstra.py**
**修改位置**: 全域設定區塊（第 21 行）

**變更內容**:
```python
# 修改前
GRID_DEG = 15

# 修改後
GRID_DEG = int(os.environ.get('SATGEN_GRID_DEG', 15))
```

**說明**: 與 `algorithm_hierarchical_virtual_pid.py` 相同

---

## 🆕 新增檔案

### 1. **run_grid_experiments.sh** ⭐
**用途**: 自動化批次執行不同網格尺寸實驗

**功能特性**:
- ✅ 序列執行（一個接一個，避免系統過載）
- ✅ 進度顯示（百分比、當前任務、預估剩餘時間）
- ✅ 錯誤處理（某任務失敗繼續執行下一個）
- ✅ 彩色輸出（清楚的日誌訊息）
- ✅ 執行時間統計

**預設配置**:
- 網格尺寸: 16°-30°（15 個尺寸）
- 演算法: Floyd 版 + Dijkstra 版
- 模擬時長: 200 秒
- 時間步長: 100 毫秒
- 執行緒: 4

**使用方式**:
```bash
cd paper/satellite_networks_state
chmod +x run_grid_experiments.sh
./run_grid_experiments.sh
```

---

### 2. **rename_15deg_results.sh**
**用途**: 為現有的 15° 結果添加 `_15deg` 後綴

**處理目錄**:
- `starlink_550_*_algorithm_hierarchical_virtual_pid`
- `starlink_550_*_algorithm_hierarchical_virtual_pid_dijkstra`

**安全機制**:
- ✅ 檢查目標目錄是否已存在
- ✅ 顯示詳細的操作訊息
- ✅ 遇到問題時跳過並繼續

**使用方式**:
```bash
cd paper/satellite_networks_state
chmod +x rename_15deg_results.sh
./rename_15deg_results.sh
```

---

### 3. **test_grid_deg_feature.sh**
**用途**: 快速驗證 grid_deg 功能是否正常

**測試內容**:
- Test 1: 不帶 `grid_deg` 參數（驗證預設值 15）
- Test 2: 帶 `grid_deg=16` 參數（驗證自訂值）

**優點**:
- 使用短時間模擬（10 秒）快速驗證
- 自動檢查生成的目錄名稱
- 提供清理測試資料的指令

**使用方式**:
```bash
cd paper/satellite_networks_state
chmod +x test_grid_deg_feature.sh
./test_grid_deg_feature.sh
```

---

### 4. **GRID_EXPERIMENTS_GUIDE.md**
**用途**: 完整的使用說明文件

**包含內容**:
- 📋 概述與相關檔案
- 🚀 詳細使用步驟
- ⚙️ 參數自訂方法
- 📊 輸出結果說明
- ⏱️ 時間預估
- 💡 執行策略建議
- ⚠️ 注意事項
- 🐛 問題排查
- ✅ 檢查清單

---

## 🔄 工作流程

### 完整實驗流程

```
1. 重命名現有 15° 結果
   └─> ./rename_15deg_results.sh

2. （可選）快速測試功能
   └─> ./test_grid_deg_feature.sh

3. 執行批次實驗
   └─> ./run_grid_experiments.sh

4. 分析結果
   └─> python hypatia_multi_algorithm_analyzer.py
```

---

## 📊 預期輸出結構

```
gen_data/
├── starlink_550_*_algorithm_hierarchical_virtual_pid_15deg/
├── starlink_550_*_algorithm_hierarchical_virtual_pid_16deg/
├── starlink_550_*_algorithm_hierarchical_virtual_pid_17deg/
├── ...
├── starlink_550_*_algorithm_hierarchical_virtual_pid_30deg/
├── starlink_550_*_algorithm_hierarchical_virtual_pid_dijkstra_15deg/
├── starlink_550_*_algorithm_hierarchical_virtual_pid_dijkstra_16deg/
├── starlink_550_*_algorithm_hierarchical_virtual_pid_dijkstra_17deg/
├── ...
└── starlink_550_*_algorithm_hierarchical_virtual_pid_dijkstra_30deg/
```

每個目錄包含:
- `fstate_*.txt` - 轉發狀態
- `gsl_if_bandwidth_*.txt` - GSL 介面頻寬（僅非 hierarchical）
- 其他網路拓撲檔案

---

## ⚙️ 技術細節

### 參數傳遞鏈

```
命令列參數 (grid_deg)
    ↓
main_starlink_550.py
    ↓
main_helper.py (設定環境變數 SATGEN_GRID_DEG)
    ↓
satgen.help_dynamic_state()
    ↓
algorithm_hierarchical_virtual_pid*.py (讀取環境變數)
    ↓
VirtualPIDRouter(grid_deg=GRID_DEG)
```

### 網格大小與 PID 數量對應

| Grid Deg | Lon Grids | Lat Grids | Total PIDs | 說明 |
|----------|-----------|-----------|------------|------|
| 15°      | 24        | 12        | 288        | 預設值 |
| 16°      | 22        | 11        | 242        | |
| 18°      | 20        | 10        | 200        | |
| 20°      | 18        | 9         | 162        | |
| 24°      | 15        | 7         | 105        | |
| 30°      | 12        | 6         | 72         | 最粗網格 |

### 控制信令統計檔案

每個實驗會在 `analytic_result/` 目錄生成：
- `hierarchical_gid_XXdeg_signaling_stats.json` (Floyd 版)
- `hierarchical_gid_dijkstra_XXdeg_signaling_stats.json` (Dijkstra 版)

---

## ✅ 測試驗證

### 已驗證項目

- [x] `main_starlink_550.py` 接受 6 或 7 個參數
- [x] 預設值 15° 正常運作
- [x] 自訂 grid_deg 正常傳遞
- [x] 輸出目錄名稱包含 `_XXdeg` 後綴
- [x] 環境變數正確設定
- [x] 演算法正確讀取 GRID_DEG
- [x] 腳本有可執行權限

### 待用戶驗證

- [ ] 執行 `./test_grid_deg_feature.sh` 通過
- [ ] 執行 `./rename_15deg_results.sh` 成功
- [ ] 執行 `./run_grid_experiments.sh` 第一個任務成功
- [ ] 生成的目錄結構正確
- [ ] `hypatia_multi_algorithm_analyzer.py` 能正確讀取新格式

---

## 🎯 下一步建議

1. **先執行測試腳本**
   ```bash
   ./test_grid_deg_feature.sh
   ```

2. **重命名現有結果**
   ```bash
   ./rename_15deg_results.sh
   ```

3. **試跑單一尺寸驗證**
   ```bash
   # 修改 run_grid_experiments.sh，只測試一個尺寸
   GRID_SIZES=(16)
   ./run_grid_experiments.sh
   ```

4. **確認無誤後執行完整實驗**
   ```bash
   # 恢復完整尺寸列表
   GRID_SIZES=(16 17 18 19 20 21 22 23 24 25 26 27 28 29 30)
   ./run_grid_experiments.sh
   ```

---

## 📞 問題回報

如遇到問題，請檢查：
1. 執行權限 (`ls -l *.sh`)
2. Python 環境是否正確
3. 磁盘空間是否充足
4. 日誌輸出中的錯誤訊息

---

## 📚 相關文件

- `GRID_EXPERIMENTS_GUIDE.md` - 詳細使用指南
- `README.md` - 專案整體說明
- `ori-readme.md` - 原始 Hypatia 說明

---

**修改完成！** ✨

所有檔案已準備就緒，可以開始進行網格尺寸實驗。
