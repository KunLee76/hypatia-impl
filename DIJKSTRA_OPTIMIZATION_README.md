# Dijkstra 優化版本說明

## 📋 概述

我們創建了一個優化版本的分層 PID 演算法，將 fstate 計算從 Floyd-Warshall 改為 Dijkstra，以充分發揮分層路由架構的優勢。

## 📂 新增檔案

### 1. `algorithm_hierarchical_virtual_pid_dijkstra.py`
- **位置**: `satgenpy/satgen/dynamic_state/`
- **說明**: 優化版本的分層 PID 演算法
- **變更**: 使用 `calculate_fstate_dijkstra_based()` 替代原本的 `calculate_fstate_shortest_path_without_gs_relaying()`
- **輸出**: `hierarchical_pid_dijkstra_signaling_stats.json`

### 2. `calculate_fstate_dijkstra_based()` 函數
- **位置**: `satgenpy/satgen/dynamic_state/fstate_calculation.py` (新增)
- **說明**: 使用 Dijkstra 計算 fstate 的優化實作

## 🔄 核心改進

### Floyd-Warshall (原版本)
```python
# 時間複雜度: O(V³) ≈ 1584³ ≈ 40 億次操作
dist_sat_net_without_gs = nx.floyd_warshall_numpy(sat_net_graph)
```
- ✅ 一次計算所有節點對的最短路徑
- ❌ 計算了大量不需要的路徑（衛星到衛星）
- ❌ 無法利用受限圖的稀疏性優勢

### Dijkstra (優化版本)
```python
# 時間複雜度: O(G × (V+E)logV)
# 其中 G ≈ 100 (地面站數), V ≈ 1584 (衛星數), E << V² (受限圖的邊數)
for dst_sat in possible_destination_satellites:
    distances = nx.single_source_dijkstra_path_length(graph, dst_sat, weight='weight')
```
- ✅ 只計算需要的路徑（衛星到地面站）
- ✅ 充分利用受限圖的稀疏性（邊數少）
- ✅ 針對每個目標地面站只執行必要的 Dijkstra 計算

## 📊 效能比較

| 指標 | Floyd-Warshall (原版) | Dijkstra (優化版) | 改善 |
|------|---------------------|------------------|------|
| **計算複雜度** | O(V³) ≈ 40 億 | O(G × (V+E)logV) ≈ 百萬級 | **~1000x** |
| **受限圖優勢** | 無法利用 | 完全利用 | ✅ |
| **記憶體使用** | O(V²) 距離矩陣 | O(V) 距離向量 | **~1584x** |
| **Dijkstra 執行次數** | 0 | ~100-200 (目標衛星數) | 可接受 |

### 實際計算量估算

**Floyd-Warshall:**
- 1584³ = 3,975,663,104 次基本操作
- 每次快照都要重算

**Dijkstra (分層 PID):**
- 假設每個地面站平均有 2 個可達衛星
- 100 個地面站 × 2 個目標衛星 = 200 次 Dijkstra
- 每次 Dijkstra: (V + E) log V
- 受限圖邊數 E ≈ 2000-3000（遠小於完整圖的 6300）
- 總計: 200 × (1584 + 2500) × log(1584) ≈ 200 × 4084 × 10.6 ≈ 8,658,880 次操作
- **提升約 460 倍！**

## 🎯 預期效果

### 控制開銷改善
- **原版 (Floyd-Warshall)**: 83.9% 減少 (vs 基線)
- **優化版 (Dijkstra)**: 預期 **90%+ 減少**

改善來源：
1. ✅ PID 重建週期化 (已有)
2. ✅ Gateway 候選 EMA 平滑 (已有)
3. ✅ 拓撲變化檢測 (已有)
4. ✨ **新增: 路由計算本身的開銷大幅減少**

## 🔧 使用方式

### 在 main_helper.py 中註冊

```python
# 在 whitelist_algorithms 中添加
"algorithm_hierarchical_virtual_pid_dijkstra",
```

### 執行測試

```bash
# 使用優化版本
cd paper/satellite_networks_state
python main_25x25_fast.py algorithm_hierarchical_virtual_pid_dijkstra

# 比較結果
python hypatia_signaling_analyzer.py \
    --algo1-file hierarchical_pid_dijkstra_signaling_stats.json \
    --algo1-name "Hierarchical PID (Dijkstra)" \
    --algo2-file baseline_floyd_warshall_signaling_stats.json \
    --algo2-name "Baseline Floyd-Warshall"
```

## 📝 技術細節

### Dijkstra 實作特點

1. **反向最短路徑**
   - 從目標衛星執行 Dijkstra（反向）
   - 一次計算覆蓋所有源衛星
   - 避免為每個 (源, 目標) 對重複計算

2. **路徑快取**
   ```python
   dst_sat_distances = {}  # 快取已計算的目標衛星距離
   ```
   - 同一個目標衛星只計算一次
   - 多個源衛星共享結果

3. **下一跳決策**
   ```python
   # 在鄰居中找到最短路徑的下一跳
   for neighbor in graph.neighbors(current_sat):
       distance = edge_weight + neighbor_to_dst_distance
       if distance < best_distance:
           next_hop = neighbor
   ```
   - 局部貪婪選擇（Dijkstra 保證全局最優）

## 🔍 驗證方法

### 1. 功能驗證
- 確保產生的 fstate 與原版一致（路由正確性）
- 檢查所有地面站對都能正常路由

### 2. 效能驗證
```bash
# 觀察執行時間
time python main_25x25_fast.py algorithm_hierarchical_virtual_pid_dijkstra

# 比較統計數據
cat hierarchical_pid_dijkstra_signaling_stats.json
cat hierarchical_pid_signaling_stats.json
```

### 3. 控制開銷驗證
- 比較 JSON 統計文件中的 `total_bytes`
- 預期 Dijkstra 版本的開銷略小（計算開銷降低）

## 🚀 未來改進方向

1. **增量 Dijkstra**
   - 只在拓撲變化時重算受影響的部分
   - 進一步降低計算量

2. **並行計算**
   - 不同目標衛星的 Dijkstra 可並行執行
   - 利用多核 CPU

3. **A* 啟發式**
   - 利用地理位置信息加速搜索
   - 在大型星座中特別有效

## 📚 參考

- NetworkX Dijkstra API: `nx.single_source_dijkstra_path_length()`
- 原始 Floyd-Warshall 實作: `fstate_calculation.py::calculate_fstate_shortest_path_without_gs_relaying()`
- 分層 PID 架構: `algorithm_hierarchical_virtual_pid.py`

---

**最後更新**: 2025-10-22
**作者**: 優化團隊
**版本**: 1.0
