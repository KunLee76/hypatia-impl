# 新增新竹地面站指南

## ✅ 驗證結果

新竹地面站已成功生成並驗證：

- **ID**: 100
- **名稱**: Hsinchu (新竹)
- **緯度**: 24.8138° N
- **經度**: 120.9675° E
- **海拔**: 0 m
- **笛卡爾座標**: 
  - X: -2,980,643.40 m
  - Y: 4,967,003.38 m
  - Z: 2,660,366.46 m

### 距離驗證
- 新竹 → 上海: 711.4 km ✅
- 新竹 → 東京: 2,151.6 km ✅

## 📝 檔案格式說明

### Input 檔案格式 (.basic.txt)
```
ID,城市名稱,緯度,經度,海拔
100,Hsinchu,24.8138,120.9675,0
```

### Output 檔案格式 (ground_stations.txt)
```
ID,城市名稱,緯度,經度,海拔,笛卡爾X,笛卡爾Y,笛卡爾Z
100,Hsinchu,24.813800,120.967500,0.000000,-2980643.40,4967003.38,2660366.46
```

**笛卡爾座標自動計算** (使用 WGS84 橢球模型)

## 🚀 使用方式

### 方法 1: 修改現有腳本 (臨時測試)

編輯 `main_starlink_550.py` 或 `main_oneweb_1200.py`:

```python
# 在 main_helper.py 第 102 行附近
if gs_selection == "ground_stations_top_100":
    satgen.extend_ground_stations(
        # "input_data/ground_stations_cities_sorted_by_estimated_2025_pop_top_100.basic.txt",  # 原本
        "input_data/ground_stations_cities_sorted_by_estimated_2025_pop_top_100_with_hsinchu.basic.txt",  # 改為這個
        output_generated_data_dir + "/" + name + "/ground_stations.txt"
    )
```

### 方法 2: 新增選項 (建議，保持彈性)

1. **修改 `main_helper.py`** (約第 100-112 行):

```python
# Ground stations
print("Generating ground stations...")
if gs_selection == "ground_stations_top_100":
    satgen.extend_ground_stations(
        "input_data/ground_stations_cities_sorted_by_estimated_2025_pop_top_100.basic.txt",
        output_generated_data_dir + "/" + name + "/ground_stations.txt"
    )
elif gs_selection == "ground_stations_top_100_with_hsinchu":  # ← 新增這個
    satgen.extend_ground_stations(
        "input_data/ground_stations_cities_sorted_by_estimated_2025_pop_top_100_with_hsinchu.basic.txt",
        output_generated_data_dir + "/" + name + "/ground_stations.txt"
    )
elif gs_selection == "ground_stations_paris_moscow_grid":
    satgen.extend_ground_stations(
        "input_data/ground_stations_paris_moscow_grid.basic.txt",
        output_generated_data_dir + "/" + name + "/ground_stations.txt"
    )
else:
    raise ValueError("Unknown ground station selection: " + gs_selection)
```

2. **執行模擬**:

```bash
cd paper/satellite_networks_state

# Starlink 550 with 新竹
conda run -n kun_hypatia python main_starlink_550.py \
  20 100 isls_plus_grid ground_stations_top_100_with_hsinchu algorithm_lohi 4

# OneWeb 1200 with 新竹
conda run -n kun_hypatia python main_oneweb_1200.py \
  20 100 isls_plus_grid ground_stations_top_100_with_hsinchu algorithm_lohi 4
```

## 🔍 為什麼不會造成資料混亂？

### 1. **自動 ID 分配**
地面站 ID 由檔案順序決定（從 0 開始），系統**自動處理**。

### 2. **自動座標計算**
笛卡爾座標由 `geodetic2cartesian()` 函數自動計算：
```python
cartesian = geodetic2cartesian(
    latitude_degrees,   # 24.8138
    longitude_degrees,  # 120.9675
    elevation_m         # 0
)
```

### 3. **格式一致性**
`extend_ground_stations()` 確保所有地面站格式完全一致。

### 4. **獨立性**
地面站配置**獨立於衛星網路**：
- `tles.txt`: 衛星軌道 (不受影響)
- `isls.txt`: 衛星間鏈路 (不受影響)
- `ground_stations.txt`: 地面站 (新增第 101 個)
- `gsl_interfaces_info.txt`: 自動調整 (由 satgen 生成)

## 📊 驗證步驟

1. **執行測試腳本**:
```bash
python3 test_hsinchu_ground_station.py
```

2. **檢查生成檔案**:
```bash
# 查看最後幾行，確認新竹在列表中
tail -5 gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_with_hsinchu_algorithm_lohi/ground_stations.txt
```

3. **執行完整模擬**:
```bash
# 短時間測試 (1 秒)
conda run -n kun_hypatia python main_starlink_550.py \
  1 100 isls_plus_grid ground_stations_top_100_with_hsinchu algorithm_lohi 1
```

4. **檢查路由**:
```bash
# 查看新竹的路由表 (ID 1684 = 1584 sats + 100 ground stations)
grep "^1684," gen_data/.../fstate_0.txt | head -10
```

## 🎯 實際應用範例

### 測試新竹 → 東京路由

```bash
cd satgenpy

# 生成視覺化路由
python -m satgen.post_analysis.main_print_graphical_routes_and_rtt \
  ../paper/satgenpy_analysis/data \
  ../paper/satellite_networks_state/gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_with_hsinchu_algorithm_lohi \
  100 20 1684 1584
  # 1684 = 新竹 (sat 1584 + gs 100)
  # 1584 = 東京 (sat 1584 + gs 0)
```

## ⚠️ 注意事項

1. **地面站數量變化**: 從 100 → 101 個
   - 路由表大小會增加: `(1584 + 101) × (1584 + 101) = 2,840,225` 條路由
   - 生成時間會稍微增加 (約 +1%)

2. **ID 對應關係**:
   - 衛星: ID 0-1583 (1584 顆)
   - 地面站: ID 1584-1684 (101 個，東京=1584, 新竹=1684)

3. **命名一致性**:
   - 目錄名稱會變成 `..._ground_stations_top_100_with_hsinchu_...`
   - 確保腳本中的路徑正確

## 📚 參考座標 (台灣其他城市)

如需新增更多台灣城市：

| 城市 | 緯度 | 經度 |
|------|------|------|
| 台北 Taipei | 25.0330 | 121.5654 |
| 新竹 Hsinchu | 24.8138 | 120.9675 |
| 台中 Taichung | 24.1477 | 120.6736 |
| 台南 Tainan | 22.9998 | 120.2269 |
| 高雄 Kaohsiung | 22.6273 | 120.3014 |

只需在 `.basic.txt` 檔案中新增對應行即可。

## ✅ 總結

**你的理解完全正確！**

只需要：
1. ✅ 知道城市經緯度
2. ✅ 新增到 `.basic.txt` 檔案
3. ✅ 重新執行生成腳本

**不會造成資料混亂**，因為：
- ✅ ID 自動分配
- ✅ 座標自動計算
- ✅ 格式自動統一
- ✅ 模擬系統完全支援
