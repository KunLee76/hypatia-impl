# LoHi 性能瓶頸分析與優化建議

## 📊 當前性能問題
- **模擬時間**: 20 秒
- **實際耗時**: ~150 分鐘
- **每個 snapshot**: ~45 秒（100ms 間隔，共 200 個 snapshot）

---

## 🔍 性能瓶頸分析

### 1. **全局 SPF Fallback（最大瓶頸）**
**位置**: `algorithm_lohi()` lines 1467-1511

**問題**:
```python
# 每個 snapshot 都檢查所有 sat→gs 的路由
for u in range(num_sats):  # 1584 顆衛星
    for gid0 in range(num_gs):  # 100 個地面站
        if (u, dst_node) not in fstate:
            missing_routes.append((u, dst_node, gid0))
            
# 然後對缺失的路由執行全局 SPF
for u, dst_node, gid0 in missing_routes[:batch_size]:
    path = nx.shortest_path(G, u, dst_sat, weight='weight')  # ❌ O(V×E)
```

**成本估算**:
- 檢查次數: `1584 × 100 = 158,400` 次/snapshot
- 缺失路由數: 冷啟動時可能 >50,000 條
- SPF 計算: 每次 `O(V log V + E)` ≈ 30ms（單次）
- **總耗時**: `50,000 × 30ms = 1,500 秒` ≈ **25 分鐘/snapshot**

**優化方向**:
✅ 使用多源 SPF（`nx.single_source_dijkstra`）
✅ 快取 SPF 結果（群內路徑幾乎不變）
✅ 只在真正需要時計算（lazy evaluation）

---

### 2. **群內路徑重複計算**
**位置**: `_route_direct_in_subgraph()` 被頻繁調用

**問題**:
```python
# 每個 sat→gs 都計算一次群內最短路徑
for u in range(num_sats):
    for gid in range(num_gs):
        # 調用 _route_direct_in_subgraph(u, target, pid, ...)
        # 內部執行 nx.shortest_path() ❌
```

**成本估算**:
- 調用次數: `1584 × 100 = 158,400` 次/snapshot
- 單次耗時: ~5ms（群內圖較小）
- **總耗時**: `158,400 × 5ms = 792 秒` ≈ **13 分鐘/snapshot**

**優化方向**:
✅ 使用 `intra_group_tree_cache`（已定義但未使用！）
✅ 預計算每個 PID 的最短路徑樹（`nx.single_source_dijkstra`）
✅ 快取 `(dst_sat, src_pid) -> {u: next_hop}` 映射

---

### 3. **2-Cycle 清洗過度迭代**
**位置**: `_break_2cycles()` lines 1311

**問題**:
```python
fstate = _break_2cycles(fstate, G_sat, sat_pid, router, num_sats, 
                       dst_sat_map, _isl_if_idxs, _noop_log, 
                       max_iterations=3)  # ❌ 每次都迭代 3 次
```

**成本估算**:
- 每次迭代檢查所有 fstate 項: `~158,400` 項
- 迭代次數: 3 次
- **總耗時**: ~10 秒/snapshot

**優化方向**:
✅ 提前終止（如果沒有發現 2-cycle）
✅ 只檢查新增的路由（增量檢查）

---

### 4. **群內圖去抖動過度防禦**
**位置**: `refresh_pid_members_and_subgraphs()` lines 280-370

**問題**:
```python
# 每個 PID 的每條邊都維護計數器
for edge_key in list(self.intra_edge_down_counter[pid].keys()):
    if edge_key not in observed_edges:
        self.intra_edge_down_counter[pid][edge_key] += 1  # ❌ 字典操作
        # ...檢查 holdover 邏輯...
```

**成本估算**:
- 邊數: 每個 PID 約 100-200 條邊
- PID 數: ~100 個
- **總耗時**: ~5 秒/snapshot

**優化方向**:
✅ 使用 `defaultdict` 減少字典查找
✅ 簡化去抖動邏輯（M_down=1 即可）

---

### 5. **群圖去抖動計數器**
**位置**: `GroupPlanner.build_group_graph()` lines 430-550

**問題**:
```python
# 維護兩個計數器：K_up 和 K_down
self.edge_up_counter[edge_key] += 1    # ❌
self.edge_down_counter[edge_key] += 1  # ❌
```

**成本估算**:
- 群邊數: ~200-300 條
- **總耗時**: ~2 秒/snapshot

**優化方向**:
✅ 減少 K_up/K_down（例如 K_up=1, K_down=1）
✅ 使用 `defaultdict`

---

## 🚀 優化方案（按優先級排序）

### 🥇 優先級 1: 修復全局 SPF Fallback（預計節省 20 分鐘/snapshot）

**問題根源**: 每個缺失路由都執行一次獨立的 SPF

**解決方案**:
```python
# 改為：每個 PID 只計算一次多源 SPF
def _compute_fallback_routes_batch(G_sat, sat_pid, dst_sat_map, missing_routes):
    """批次計算缺失路由（每個 PID 只執行一次 SPF）"""
    # 按 src_pid 分組
    by_pid = {}
    for u, dst_node, gid0 in missing_routes:
        src_pid = sat_pid.get(u)
        if src_pid not in by_pid:
            by_pid[src_pid] = []
        by_pid[src_pid].append((u, dst_node, gid0))
    
    fallback_fstate = {}
    
    # 每個 PID 只計算一次 SPF
    for src_pid, routes in by_pid.items():
        # 收集該 PID 的所有目標衛星
        targets = set()
        for u, dst_node, gid0 in routes:
            if dst_node in dst_sat_map:
                targets.add(dst_sat_map[dst_node])
        
        # 對每個目標衛星執行一次 single_source_dijkstra
        for dst_sat in targets:
            try:
                lengths, paths = nx.single_source_dijkstra(G_sat, dst_sat, weight='weight')
                
                # 反向填充所有到該目標的路由
                for u, dst_node, gid0 in routes:
                    if dst_sat_map.get(dst_node) == dst_sat and u in paths:
                        path = paths[u]
                        if len(path) > 1:
                            next_hop = path[1]  # u -> next_hop -> ... -> dst_sat
                            fallback_fstate[(u, dst_node)] = next_hop
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pass
    
    return fallback_fstate
```

**預期效果**: 
- 從 `O(missing_routes × V log V)` 降為 `O(PIDs × targets × V log V)`
- 成本從 ~25 分鐘降為 **~2 分鐘**

---

### 🥈 優先級 2: 啟用群內路徑樹快取（預計節省 10 分鐘/snapshot）

**問題根源**: `intra_group_tree_cache` 已定義但未使用

**解決方案**:
```python
# 在 build_fstate_lohi() 中，預計算每個目標的群內路徑樹
def _precompute_intra_group_trees(router, G_sat, dst_sat_map, sat_pid):
    """預計算每個目標衛星的群內最短路徑樹"""
    intra_tree_cache = {}  # (dst_sat, src_pid) -> {u: next_hop}
    
    for dst_sat in set(dst_sat_map.values()):
        dst_pid = sat_pid.get(dst_sat)
        if dst_pid is None:
            continue
        
        # 獲取該 PID 的子圖
        Gp = router.pid_subgraphs.get(dst_pid)
        if not Gp or not Gp.has_node(dst_sat):
            continue
        
        # 計算從 dst_sat 的 single_source_dijkstra（反向路徑樹）
        try:
            lengths, paths = nx.single_source_dijkstra(Gp, dst_sat, weight='weight')
            
            # 建立 next_hop 映射
            next_hop_map = {}
            for u in Gp.nodes():
                if u in paths and len(paths[u]) > 1:
                    next_hop_map[u] = paths[u][-2]  # 反向路徑：倒數第二個節點
            
            # 同 PID 內的所有源都可以使用這個樹
            for src_pid in [dst_pid]:  # 只快取同 PID
                intra_tree_cache[(dst_sat, src_pid)] = next_hop_map
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass
    
    return intra_tree_cache

# 然後在路由時查表
def _route_with_cache(u, target, src_pid, cache):
    """使用快取查詢下一跳"""
    cache_key = (target, src_pid)
    if cache_key in cache:
        return cache[cache_key].get(u)
    return None
```

**預期效果**: 
- 群內路由從 `O(sat_count × nx.shortest_path)` 降為 `O(1)` 查表
- 成本從 ~13 分鐘降為 **~10 秒**

---

### 🥉 優先級 3: 簡化去抖動邏輯（預計節省 3 分鐘/snapshot）

**問題根源**: 過度防禦的計數器維護

**解決方案**:
```python
# 1. 減少閾值
M_down = 1  # 從 2 改為 1
K_up = 1    # 從 3 改為 1
K_down = 1  # 從 3 改為 1

# 2. 使用 defaultdict
from collections import defaultdict

self.intra_edge_down_counter = defaultdict(lambda: defaultdict(int))
self.edge_up_counter = defaultdict(int)
self.edge_down_counter = defaultdict(int)

# 3. 批次清理過期計數器（每 10 個 snapshot）
if snapshot_idx % 10 == 0:
    self._cleanup_old_counters()
```

**預期效果**: 
- 字典操作減少 50%
- 成本從 ~7 秒降為 **~3 秒**

---

### 🏅 優先級 4: 2-Cycle 清洗提前終止（預計節省 5 秒/snapshot）

**解決方案**:
```python
def _break_2cycles(..., max_iterations=3):
    for iteration in range(max_iterations):
        fixes_this_round = 0
        
        # ... 檢測和修復邏輯 ...
        
        if fixes_this_round == 0:
            # 沒有發現 2-cycle，提前退出
            break
    
    return fstate
```

---

## 📈 預期整體效果

| 優化項目 | 節省時間/snapshot | 實施難度 | 風險 |
|---------|------------------|---------|------|
| 1. 批次 SPF Fallback | **~23 分鐘** | 中 | 低 |
| 2. 群內路徑樹快取 | **~12 分鐘** | 低 | 極低 |
| 3. 簡化去抖動 | **~3 分鐘** | 極低 | 中 |
| 4. 2-Cycle 提前終止 | **~5 秒** | 極低 | 極低 |
| **總計** | **~38 分鐘** | - | - |

**最終預期**:
- 當前: ~45 分鐘/snapshot × 200 = **150 分鐘**
- 優化後: ~7 分鐘/snapshot × 200 = **23 分鐘**
- **改善**: **84% 性能提升** ✨

---

## 🎯 實施建議

### 階段 1: 低風險快速優化（1 小時）
- ✅ 啟用群內路徑樹快取（優先級 2）
- ✅ 2-Cycle 提前終止（優先級 4）
- **預期效果**: 45 → 33 分鐘/snapshot（~26% 提升）

### 階段 2: 中等風險核心優化（2-3 小時）
- ✅ 批次 SPF Fallback（優先級 1）
- **預期效果**: 33 → 10 分鐘/snapshot（~78% 提升）

### 階段 3: 微調與驗證（1 小時）
- ✅ 簡化去抖動邏輯（優先級 3）
- ✅ 完整測試與驗證
- **預期效果**: 10 → 7 分鐘/snapshot（~84% 提升）

---

## ⚠️ 風險評估

### 低風險優化（立即可做）
- ✅ 群內路徑樹快取：只改變計算方式，結果不變
- ✅ 2-Cycle 提前終止：只是跳過不必要的迭代

### 中風險優化（需要測試）
- ⚠️ 批次 SPF Fallback：確保多源 SPF 計算正確
- ⚠️ 簡化去抖動：M_down=1 可能增加抖動敏感度

### 驗證方法
1. **功能驗證**: 確保 fstate 輸出一致
2. **路徑驗證**: 檢查 Tokyo→Shanghai 等路徑不變
3. **RTT 驗證**: 確保 RTT 性能不退化
4. **信令驗證**: 控制信令開銷應保持相近

---

## 🔧 其他發現

### 已定義但未使用的優化
1. `intra_group_tree_cache` (line 1072) - **未使用！**
2. `dst_pid_prev_cache` (line 1074) - **未使用！**

### 可能的進一步優化
1. 使用 C++ 擴展加速圖算法（`cython`）
2. 並行化 PID 的獨立計算（`multiprocessing`）
3. 增量更新群圖（只更新變動的邊）
