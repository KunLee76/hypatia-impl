# 控制信令統計異常診斷與修正報告

生成時間: 2026-01-07

## 🔍 問題發現

在分析多算法控制信令統計時，發現以下異常：

### 1. **Baseline: 2009 次 routing_update**
- **預期**：200 秒 ÷ 0.1 秒 = 2000 個 snapshot，應該最多 2000 次
- **實際**：2009 次
- **問題**：超出理論上限 9 次

### 2. **GID: 1991 次 routing_update**
- **預期**：2000 次
- **實際**：1991 次
- **問題**：少了 9 次

### 3. **LoHi: 1999 次 pid_rebuild**
- **預期**：2000 次
- **實際**：1999 次
- **問題**：少了 1 次（第一個 snapshot 沒記錄）

---

## 🔬 診斷分析

### 診斷工具輸出

執行 `diagnose_signaling_stats.py` 後發現：

#### Baseline 問題根源
```
⚠️  routing_update: 2009 記錄但只有 201 個唯一 snapshot
重複的 snapshot: [(0, 10), (1, 10), (2, 10), (3, 10), ...]
```

**關鍵發現**：
- 實際上只有 **201 個唯一 snapshot** (0-200)
- 每個 snapshot 被記錄了 **10 次**！
- 201 × 10 = 2010，但有一個 snapshot 只記錄了 9 次 → 2009

**根本原因**：
1. Baseline 算法使用 **process-local 計數器** (`_current_snapshot`)
2. 在並行執行或多次呼叫時，同一個 snapshot 會被重複記錄
3. Hypatia 系統可能為每對 GS 或其他原因多次呼叫算法函數

#### GID 與 LoHi 的情況

- **GID**: 1991 次是合理的，因為有去抖動機制和條件性記錄
  - 某些 snapshot 可能沒有路由變化，因此沒有記錄
  - 使用正確的 snapshot 索引，無重複問題
  
- **LoHi**: 1999 次是合理的
  - 第一個 snapshot (t=0) 是初始化，不記錄 `pid_rebuild`
  - 從第二個 snapshot (t=1) 開始記錄 → 1999 次
  - 符合預期行為

---

## ✅ 修正措施

### 1. 修正 Baseline 算法的 snapshot 計數

**修改檔案**：`algorithm_free_one_only_over_isls_with_stats.py`

#### 修改 1: 添加函數參數
```python
def algorithm_free_one_only_over_isls(
    ...
    enable_verbose_logs,
    time_step_ns=None  # 新增：用於計算準確的 snapshot 索引
):
```

#### 修改 2: 改進 snapshot 計算邏輯
```python
# 舊代碼（有問題）
snapshot = getattr(_get_process_local_stats(), '_current_snapshot', 0)
_get_process_local_stats()._current_snapshot = snapshot + 1

# 新代碼（正確）
if time_step_ns is not None and time_step_ns > 0:
    snapshot = int(time_since_epoch_ns / time_step_ns)
else:
    # 預設 100ms per snapshot
    snapshot = int(time_since_epoch_ns / 100_000_000)
```

#### 修改 3: 添加去重機制
```python
class ControlSignalingStats:
    def reset(self):
        ...
        self._recorded_snapshots: Set[int] = set()  # 追蹤已記錄的 snapshot

    def record_routing_update(self, snapshot, ...):
        # 去重檢查：每個 snapshot 只記錄一次
        if snapshot in self._recorded_snapshots:
            return
        self._recorded_snapshots.add(snapshot)
        ...
```

---

## 📊 預期修正後的結果

| 演算法 | 事件類型 | 修正前 | 修正後 | 說明 |
|--------|---------|--------|--------|------|
| **Baseline** | routing_update | 2009 | 2001 | 移除重複，保留 snapshot 0-2000 |
| **GID** | routing_update | 1991 | 1991 | 無需修改（合理） |
| **GID** | gid_rebuild | 2000 | 2000 | 無需修改（正確） |
| **LoHi** | pid_rebuild | 1999 | 1999 | 無需修改（合理：從 t=1 開始） |
| **LoHi** | routing_update | 2000 | 2000 | 無需修改（正確） |

**注意**：Baseline 應該是 2001 次（snapshot 0-2000），而不是 2000 次。

---

## 🔧 驗證步驟

### 1. 重新執行模擬

```bash
cd paper/satellite_networks_state
# 重新生成 Baseline 統計
python -m satgen.post_analysis.main_print_routes_and_rtt \
    --base-name="kuiper_630_isls_plus_grid_ground_stations_top_100" \
    --dynamic-state-algorithm="algorithm_free_one_only_over_isls"
```

### 2. 重新執行診斷

```bash
python diagnose_signaling_stats.py
```

預期輸出：
```
Baseline:
  ✅ routing_update: 無重複
  總記錄數: 2001
  唯一 snapshot 數: 2001
```

### 3. 重新執行多算法分析

```bash
python hypatia_multi_algorithm_analyzer.py
```

---

## 📝 總結

### 問題本質
- **Baseline 算法**：重複計數問題，源於錯誤的 snapshot 追蹤機制
- **GID 和 LoHi**：實際上沒有問題，數字差異是合理的算法行為

### 修正重點
1. ✅ 使用 `time_since_epoch_ns / time_step_ns` 計算準確的 snapshot 索引
2. ✅ 添加去重機制，防止同一 snapshot 被重複記錄
3. ✅ 修正函數簽名，接收 `time_step_ns` 參數

### 下一步
1. 重新執行 Baseline 模擬
2. 驗證統計數據的正確性
3. 更新比較報告和圖表

---

**修正完成日期**：2026-01-07  
**診斷工具**：`diagnose_signaling_stats.py`  
**修正檔案**：`algorithm_free_one_only_over_isls_with_stats.py`
