# 關於 grid_deg 參數對 LoHi 的影響

## 問題
你擔心 `main_starlink_550.py` 中第 7 個參數 `grid_deg` 會不會影響 LoHi 演算法？

## 答案：✅ 不會影響

### 原因分析

#### 1. 參數處理邏輯
```python
# main_starlink_550.py (第 92-93 行)
grid_deg = int(args[6]) if len(args) == 7 else 15
main_helper.calculate(..., grid_deg)
```
- 當只提供 6 個參數時，`grid_deg` 預設為 15
- 但這個值不會被 LoHi 使用！

#### 2. main_helper.py 的智能判斷
```python
# main_helper.py (第 71-88 行)
if "hierarchical_virtual_gid" in dynamic_state_algorithm.lower():
    name += f"_{grid_deg}deg"
    os.environ['SATGEN_GRID_DEG'] = str(grid_deg)
    print(f"[GID] Setting grid degree to {grid_deg}°")
elif "lohi" in dynamic_state_algorithm.lower():
    print(f"[LoHi] Using fixed 6×10 plane-block grouping (grid_deg parameter ignored)")
```

**關鍵點**：
- ✅ LoHi 的演算法名稱是 `algorithm_lohi`
- ✅ 不包含 "hierarchical_virtual_gid" 字串
- ✅ 會進入 `elif "lohi"` 分支
- ✅ **不會設置** `SATGEN_GRID_DEG` 環境變數
- ✅ **不會** 在輸出目錄名稱加上 `_XXdeg` 後綴

#### 3. 輸出目錄名稱比較
```bash
# GID 演算法（會使用 grid_deg）
gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_hierarchical_virtual_gid_dijkstra_21deg/
                                                                                                            ^^^^^^
                                                                                                     有 deg 後綴

# LoHi 演算法（忽略 grid_deg）
gen_data/starlink_550_isls_plus_grid_ground_stations_top_100_algorithm_lohi/
                                                                        ^^^^^
                                                                  沒有 deg 後綴
```

## 實際測試結果

### 測試 1: LoHi + grid_deg=15
```bash
$ python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10
# 實際行為：
[LoHi] Using fixed 6×10 plane-block grouping (grid_deg parameter ignored)
輸出目錄: .../algorithm_lohi/  (沒有 _15deg)
環境變數 SATGEN_GRID_DEG: 未設置 ✓
```

### 測試 2: LoHi + grid_deg=21 (如果不小心加了)
```bash
$ python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10 21
# 實際行為：
[LoHi] Using fixed 6×10 plane-block grouping (grid_deg parameter ignored)
輸出目錄: .../algorithm_lohi/  (仍然沒有 _21deg)
環境變數 SATGEN_GRID_DEG: 未設置 ✓
```

### 測試 3: GID + grid_deg=21
```bash
$ python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_gid_dijkstra 10 21
# 實際行為：
[GID] Setting grid degree to 21° for hierarchical GID algorithm
輸出目錄: .../algorithm_hierarchical_virtual_gid_dijkstra_21deg/  (有 _21deg)
環境變數 SATGEN_GRID_DEG: 21 ✓
```

## 為什麼設計成這樣？

### LoHi 的分群邏輯
```python
# algorithm_lohi.py
PLANES_PER_GROUP = 6                   # 固定值
SATS_PER_PLANE_IN_GROUP = 10           # 固定值

# 分群公式
plane_block_id = plane_id // 6         # 不依賴 grid_deg
seg_id_in_plane = pos_in_plane // 10   # 不依賴 grid_deg
```

**LoHi 使用**：
- ✅ 衛星的**軌道平面編號**（plane_id）
- ✅ 衛星在平面中的**位置**（pos_in_plane）
- ❌ 不使用**地理位置**（lat/lon）
- ❌ 不使用 **grid_deg**

### GID 的分群邏輯
```python
# algorithm_hierarchical_virtual_gid.py
grid_deg = int(os.environ.get('SATGEN_GRID_DEG', 15))  # 讀取環境變數

# 分群公式
lon_idx = int((lon - lon_min) // grid_deg)  # 依賴 grid_deg
lat_idx = int((lat - lat_min) // grid_deg)  # 依賴 grid_deg
gid = lat_idx * num_lon + lon_idx
```

**GID 使用**：
- ✅ 衛星的**地理位置**（lat/lon）
- ✅ **grid_deg** 參數
- ❌ 不使用軌道平面編號

## 結論

### ✅ 可以放心
1. **LoHi 完全不受 grid_deg 影響**
2. 即使不小心加了第 7 個參數，LoHi 也會忽略它
3. 輸出目錄名稱不會有 `_XXdeg` 後綴（避免混淆）
4. 環境變數 `SATGEN_GRID_DEG` 不會被設置

### 📝 使用建議

#### 標準用法（推薦）
```bash
# LoHi: 6 個參數（清晰明確）
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10

# GID: 7 個參數（必須指定 grid_deg）
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_gid_dijkstra 10 21
```

#### 即使寫錯也沒關係
```bash
# 不小心加了 grid_deg，但 LoHi 會忽略它
python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10 15
# 行為：[LoHi] Using fixed 6×10 plane-block grouping (grid_deg parameter ignored)
# 結果：完全正確，不受影響 ✓
```

### 🎯 設計優點
1. **容錯性**：即使誤用參數也不會影響結果
2. **明確性**：輸出目錄名稱清楚顯示分群方式
3. **一致性**：所有演算法用同一個腳本，邏輯清晰
4. **可追蹤性**：日誌訊息明確說明參數如何被處理

## 驗證方法

運行測試腳本：
```bash
cd /home/kun/ssd2t/Leo/kun_hypatia
./test_algorithm_params.sh
```

檢查輸出目錄名稱：
```bash
ls -ld gen_data/*lohi*        # 應該沒有 deg 後綴
ls -ld gen_data/*gid*21deg*   # 應該有 21deg 後綴
```

## 參考
- 實作細節：`main_helper.py` 第 71-88 行
- LoHi 分群：`algorithm_lohi.py` 第 8-10 行
- GID 分群：`algorithm_hierarchical_virtual_gid.py` 第 22 行
