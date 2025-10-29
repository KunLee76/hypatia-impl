# 路由分析腳本使用指南

## 📋 概述

已創建兩個自動化腳本用於分析不同網格大小（15°-30°）的路由路徑：

1. **`analyze_routes_all_grids.sh`** - 路徑和RTT分析（文本 + 曲線圖）
2. **`analyze_graphical_routes_all_grids.sh`** - 全球視角圖生成（PDF地圖）

## ⚙️ 配置參數

### 時間參數
- **Time Step**: 100ms
- **Duration**: 20s
- **Snapshots**: 200個時間點

### 地面站對
- **源站**: 1584 (東京 Tokyo)
- **目標站**:
  - 1585 (德里 Delhi)
  - 1586 (上海 Shanghai)
  - 1593 (紐約 New York)

### 算法與網格
- **算法**: Floyd-Warshall 和 Dijkstra 兩種
- **網格範圍**: 15° - 30° (16種尺寸)
- **總組合**: 16 grid sizes × 2 algorithms × 3 destinations = **96 個分析任務**

---

## 🚀 使用方式

### 1️⃣ 路徑和RTT分析

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia
./analyze_routes_all_grids.sh
```

**輸出內容**:
- ✅ 路徑變化記錄 (TXT)
- ✅ RTT時間序列數據 (TXT)
- ✅ RTT曲線圖 (PDF)

**執行時間**: 約 5-10 分鐘（取決於系統性能）

**輸出位置**:
```
paper/satgenpy_analysis/data/
├── starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_pid_15deg/
│   └── 100ms_for_20s/manual/
│       ├── data/
│       │   ├── networkx_path_1584_to_1585.txt
│       │   ├── networkx_path_1584_to_1586.txt
│       │   ├── networkx_path_1584_to_1593.txt
│       │   ├── networkx_rtt_1584_to_1585.txt
│       │   ├── networkx_rtt_1584_to_1586.txt
│       │   └── networkx_rtt_1584_to_1593.txt
│       └── pdf/
│           ├── time_vs_networkx_rtt_1584_to_1585.pdf
│           ├── time_vs_networkx_rtt_1584_to_1586.pdf
│           └── time_vs_networkx_rtt_1584_to_1593.pdf
├── starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_pid_16deg/
│   └── ... (相同結構)
└── ... (其他網格大小)
```

---

### 2️⃣ 全球視角圖生成

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia
./analyze_graphical_routes_all_grids.sh
```

**⚠️ 重要提示**:
- 每個時間點生成一張全球地圖PDF
- 200 snapshots × 96 任務 = **19,200 張 PDF 圖片**
- 每張圖約 500KB，總計約 **9.6 GB**
- 執行時間可能需要 **數小時到一天**

**輸出內容**:
- ✅ 全球地圖視角圖（每個路徑變化時刻）
- ✅ 顯示衛星位置、地面站、路由路徑

**輸出位置**:
```
paper/satgenpy_analysis/data/
└── starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_pid_15deg/
    └── 100ms_for_20s/manual/pdf/
        ├── graphics_1584_to_1585_time_0ms.pdf
        ├── graphics_1584_to_1585_time_100ms.pdf
        ├── graphics_1584_to_1585_time_200ms.pdf
        └── ... (每100ms一張，共約200張/每對)
```

---

## 📊 建議的執行順序

### 階段1: 快速驗證（先測試一個網格）

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia/satgenpy

# 測試 15° Floyd-Warshall 的一對路徑
python -m satgen.post_analysis.main_print_routes_and_rtt \
  ../paper/satgenpy_analysis/data \
  ../paper/satellite_networks_state/gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_pid_15deg \
  100 20 1584 1585

# 檢查輸出
ls -lh ../paper/satgenpy_analysis/data/starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_pid_15deg/100ms_for_20s/manual/data/
```

### 階段2: 批量路徑分析

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia
./analyze_routes_all_grids.sh
```

### 階段3: 選擇性生成視角圖（可選）

如果需要視覺化特定網格大小的路徑：

```bash
# 修改 analyze_graphical_routes_all_grids.sh
# 將 GRID_SIZES 改為只包含感興趣的網格
# 例如: GRID_SIZES=(15 20 25 30)

./analyze_graphical_routes_all_grids.sh
```

---

## 🔍 輸出解讀

### 路徑文件 (`networkx_path_*.txt`)
```
0,1584-213-214-215-1585
100000000,1584-213-220-221-1585
200000000,1584-213-214-215-1585
```
- 第一列: 時間 (ns)
- 第二列: 路徑 (節點ID以 `-` 連接)

### RTT文件 (`networkx_rtt_*.txt`)
```
0,45.2345678900
100000000,46.1234567800
200000000,45.5432109800
```
- 第一列: 時間 (ns)
- 第二列: RTT (ns)

### RTT曲線圖 (`time_vs_networkx_rtt_*.pdf`)
- X軸: 時間 (秒)
- Y軸: RTT (毫秒)
- 顯示路徑變化對延遲的影響

### 全球視角圖 (`graphics_*_time_*.pdf`)
- 🔴 紅色三角 (▲): 使用中的衛星
- ⚪ 空心三角: 未使用的衛星
- ⚫ 深灰圓圈 (●): 使用中的地面站
- ⚪ 空心圓圈: 未使用的地面站
- 🟠 橘色線: 路由路徑

---

## 🛠️ 故障排除

### 問題1: 目錄不存在
```
⚠️  目錄不存在，跳過: .../gen_data/..._15deg
```
**解決**: 確保已完成網格實驗生成
```bash
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state
./run_grid_experiments.sh
```

### 問題2: 缺少依賴
```
ModuleNotFoundError: No module named 'cartopy'
```
**解決**: 安裝 cartopy（視角圖需要）
```bash
conda activate kun_hypatia
conda install -c conda-forge cartopy
```

### 問題3: gnuplot 未安裝
```
gnuplot: command not found
```
**解決**: 安裝 gnuplot
```bash
sudo apt install gnuplot
```

---

## 📈 後續分析建議

完成路徑分析後，可以：

1. **比較不同網格大小的RTT差異**
   ```bash
   # 提取所有 15° 的 RTT 數據
   grep "15deg" paper/satgenpy_analysis/data/*/100ms_for_20s/manual/data/networkx_rtt_*.txt
   ```

2. **統計路徑跳數變化**
   ```python
   # 分析 networkx_path_*.txt
   # 計算每個路徑的跳數 (節點數 - 1)
   ```

3. **整合到論文圖表**
   - 使用 RTT 曲線圖比較不同算法
   - 使用全球視角圖展示路由策略差異

---

## ⏱️ 預估執行時間

### `analyze_routes_all_grids.sh`
- 單個分析任務: ~3-5秒
- 總計 96 任務: **約 5-10 分鐘**

### `analyze_graphical_routes_all_grids.sh`
- 單個分析任務: ~2-5分鐘（取決於路徑變化次數）
- 總計 96 任務: **約 3-8 小時**

---

## 📝 腳本自定義

如果需要修改參數，編輯腳本中的配置區域：

```bash
# 修改網格範圍
GRID_SIZES=(15 20 25 30)  # 只分析特定網格

# 修改目標地面站
declare -A DST_GS_MAP
DST_GS_MAP[1585]="Delhi"
# DST_GS_MAP[1586]="Shanghai"  # 註解掉不需要的

# 修改時間參數
TIME_STEP_MS=200  # 改為 200ms
DURATION_S=40     # 改為 40s
```

---

## 🎯 快速命令參考

```bash
# 運行路徑分析
./analyze_routes_all_grids.sh

# 運行視角圖生成（帶確認）
./analyze_graphical_routes_all_grids.sh

# 檢查特定網格的輸出
ls -lh paper/satgenpy_analysis/data/*_15deg/100ms_for_20s/manual/pdf/

# 統計生成的PDF數量
find paper/satgenpy_analysis/data -name "*.pdf" | wc -l

# 檢查磁碟使用量
du -sh paper/satgenpy_analysis/data/
```

---

**創建日期**: 2025-10-28  
**適用範圍**: 網格實驗 15°-30°  
**維護者**: Kun Lee
