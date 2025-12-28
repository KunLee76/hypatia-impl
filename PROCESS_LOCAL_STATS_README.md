# Process-Local Statistics Implementation

## 概述

為了從根本上解決並行處理時的統計數據重複問題，已將三個路由算法從全局統計對象改為 process-local 統計。

## 問題根源

**並行處理競態條件**：
- 多個 worker 進程同時處理不同的 snapshot
- 共享全局 `_SIGNALING_STATS` 對象
- 在 snapshot 邊界（0, 100, 200...）同時記錄事件
- 導致重複記錄（GRHR 9筆，LoHi 9筆）

## 解決方案

### 1. Thread-Local Storage

每個算法文件都已改為 process-local 統計：

```python
# 舊版（全局共享）
_SIGNALING_STATS = ControlSignalingStats()

# 新版（process-local）
_thread_local = threading.local()

def _get_process_local_stats():
    """獲取當前進程的統計對象"""
    if not hasattr(_thread_local, 'stats'):
        _thread_local.stats = ControlSignalingStats()
    return _thread_local.stats
```

### 2. 臨時文件輸出

每個進程將統計數據寫入獨立的臨時文件：

```python
# Baseline
temp_dir = os.path.join(stats_output_dir, "temp_baseline")
stats_file = os.path.join(temp_dir, f"baseline_stats_pid{pid}_tid{thread_id}.json")

# GRHR
temp_dir = os.path.join(stats_output_dir, "temp_grhr")
stats_file = os.path.join(temp_dir, f"grhr_stats_pid{pid}_tid{thread_id}.json")

# LoHi
temp_dir = os.path.join(stats_output_dir, "temp_lohi")
stats_file = os.path.join(temp_dir, f"lohi_stats_pid{pid}_tid{thread_id}.json")
```

### 3. 合併工具

創建了 `merge_signaling_stats.py` 工具：

**功能**：
- 自動收集所有臨時文件
- 基於 `(snapshot, time_ms, event)` 去重
- 重新計算摘要統計
- 生成最終 JSON 文件
- 清理臨時文件（可選保留）

**使用方法**：
```bash
# 基本用法（自動處理所有算法）
python merge_signaling_stats.py

# 指定目錄
python merge_signaling_stats.py -d analytic_result

# 保留臨時文件（用於調試）
python merge_signaling_stats.py --keep-temp

# 詳細模式
python merge_signaling_stats.py -v
```

## 修改文件清單

### 1. algorithm_free_one_only_over_isls_with_stats.py (Baseline)
✅ **完成**

修改內容：
- Line ~16: 添加 `import threading`
- Lines 146-162: 改為 thread-local storage
- Line 205: 在函數中獲取 process-local stats
- Lines 322-332: 輸出到臨時文件（已修改）

### 2. algorithm_hierarchical_virtual_gid.py (GRHR)
✅ **完成**

修改內容：
- Line 16: 添加 `import threading`
- Lines 276-292: 改為 thread-local storage
- Line 1537: 在函數中獲取 process-local stats
- Lines 1327-1340: 輸出到臨時文件（第一處）
- Lines 1387-1404: 輸出到臨時文件（第二處）

### 3. algorithm_lohi.py (LoHi)
✅ **完成**

修改內容：
- Line 34: 添加 `import threading`
- Lines 178-194: 改為 thread-local storage
- Line 1506: 在函數中獲取 process-local stats
- Lines 1783-1795: 輸出到臨時文件

### 4. merge_signaling_stats.py
✅ **新建**

特點：
- 自動檢測三種算法的臨時文件
- 智能去重（基於唯一鍵）
- 保留所有元數據（grid_deg, p, s 等）
- 自動清理臨時文件
- 完整的錯誤處理和日誌

## 工作流程

### 模擬階段
```
進程1: snapshot 0, 100, 200... → temp_baseline/baseline_stats_pid1234_tid5678.json
進程2: snapshot 300, 400, 500... → temp_baseline/baseline_stats_pid1235_tid5679.json
...
```

### 合併階段
```bash
# 模擬完成後執行
python merge_signaling_stats.py

# 輸出：
# analytic_result/baseline_floyd_warshall_signaling_stats.json
# analytic_result/hierarchical_gid_15deg_signaling_stats.json
# analytic_result/lohi_signaling_stats_pure_p6_s10.json
```

### 分析階段
```bash
# 使用合併後的文件
python hypatia_multi_algorithm_analyzer.py
```

## 優勢

1. **徹底解決重複問題**：每個進程獨立記錄，無競態條件
2. **保持向後兼容**：最終輸出格式不變
3. **易於調試**：可以檢查每個進程的統計數據
4. **自動化**：合併工具一鍵處理
5. **安全性**：自動去重，防止遺漏或重複

## 測試建議

### 小規模測試（推薦先執行）
```bash
# 1. 修改配置為少量 snapshot（例如 5 個）
# 2. 運行模擬
# 3. 檢查臨時文件
ls -l analytic_result/temp_*/

# 4. 運行合併工具
python merge_signaling_stats.py -v --keep-temp

# 5. 驗證結果
python deduplicate_signaling_stats.py -d analytic_result --check-only
python hypatia_multi_algorithm_analyzer.py
```

### 完整模擬
```bash
# 1. 確保小規模測試通過
# 2. 恢復原始配置（完整 snapshot 數量）
# 3. 運行完整模擬（~11+ 小時）
# 4. 運行合併工具
python merge_signaling_stats.py

# 5. 驗證和分析
python deduplicate_signaling_stats.py -d analytic_result --check-only
python hypatia_multi_algorithm_analyzer.py
```

## 預期結果

**無重複數據**：
- GRHR: ~1698 事件（無重複）
- LoHi: ~5998 事件（無重複）
- Baseline: ~1009 事件（無重複）

**性能對比**（預期）：
- GRHR vs Baseline: 節省 ~91-92%
- LoHi vs Baseline: 節省 ~60-61%

## 故障排除

### 臨時文件未生成
**問題**：模擬後沒有 temp_* 目錄
**原因**：代碼未正確修改或未執行到輸出部分
**解決**：檢查算法文件修改是否正確

### 合併工具報錯
**問題**：找不到臨時文件或合併失敗
**原因**：臨時文件格式錯誤或缺失必要字段
**解決**：使用 `-v` 參數查看詳細錯誤，檢查臨時文件內容

### 仍有重複數據
**問題**：合併後仍發現重複事件
**原因**：去重邏輯未正確執行
**解決**：使用 deduplicate_signaling_stats.py 驗證，檢查合併工具邏輯

## 回滾方案

如果遇到問題需要回滾到全局統計：

```bash
# 1. 使用 git 恢復原始文件
git checkout algorithm_free_one_only_over_isls_with_stats.py
git checkout algorithm_hierarchical_virtual_gid.py
git checkout algorithm_lohi.py

# 2. 重新運行模擬
# 3. 使用後處理去重
python deduplicate_signaling_stats.py -d analytic_result
```

## 總結

✅ **已完成**：
- 3 個算法文件全部改為 process-local 統計
- 創建了自動化合併工具
- 文檔完整，包含測試和故障排除指南

📋 **待執行**：
- 運行小規模測試驗證實現
- 運行完整模擬（11+ 小時）
- 驗證最終結果無重複

🎯 **預期效果**：
- 完全消除並行處理導致的重複事件
- 保持分析結果的準確性
- 為未來模擬提供穩定的統計基礎
