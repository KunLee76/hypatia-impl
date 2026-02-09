# Chaos Monkey 修復總結

## 問題診斷

發現 Baseline 和 LoHi 算法在 Dynamic 失效場景中沒有正確處理 ISL 失效：

- **症狀**: 所有 Dynamic P1/P5/P10 場景的 `changed_entries` 完全相同（773,324）
- **根本原因**: Baseline 和 LoHi 算法沒有實作 Chaos Monkey ISL 失效注入
- **證據**: 
  - Baseline Dynamic P1/P5/P10 均無 `topology_change` 事件
  - LoHi 有 100 個 `topology_change` 事件，但全部是 `delta_group_edges: 0`
  - 只有 GRHR 正確實作了 Chaos Monkey

## 修復內容

### 1. Baseline 算法修復
文件：`satgenpy/satgen/dynamic_state/algorithm_free_one_only_over_isls_with_stats.py`

**添加內容**：
- Chaos Monkey 配置（第 35-95 行）
  - `ENABLE_CHAOS_MONKEY`: 環境變數控制開關
  - `CHAOS_FAILURE_RATE`: 失效率（預設 1%）
  - `CHAOS_INTERVAL_SNAPSHOTS`: 注入間隔（預設 20 snapshots）
  - `CHAOS_LOG_FILE`: 日誌文件路徑
  
- `chaos_monkey_inject_failures()` 函數：隨機移除指定比例的 ISL

- 主函數中添加調用（圖檢查後）：
  ```python
  if ENABLE_CHAOS_MONKEY and (snapshot % CHAOS_INTERVAL_SNAPSHOTS == 0):
      removed_isls = chaos_monkey_inject_failures(...)
  ```

### 2. LoHi 算法修復
文件：`satgenpy/satgen/dynamic_state/algorithm_lohi.py`

**添加內容**：
- 相同的 Chaos Monkey 配置和函數
- 日誌文件：`chaos_monkey_lohi.log`
- 注入位置：權重重置後、分群之前

## 關鍵參數一致性

### 模擬參數（必須與 Normal 場景一致）
- **模擬時長**: 200 秒
- **時間步長**: 2000ms
- **快照數量**: 100 個 (snapshot 0, 20, 40, ..., 1980)
- **多線程**: 4 個線程

### Chaos Monkey 參數
- **失效率**:
  - P1: 1% (0.01)
  - P5: 5% (0.05)
  - P10: 10% (0.10)
- **注入間隔**: 每 20 snapshots = 40 秒 (20 × 2000ms)
- **預期注入次數**: 5 次 (snapshot 0, 20, 40, 60, 80)

### 暫存文件目錄
- Baseline: `temp_baseline_dynamic_p1/p5/p10/`
- LoHi: `temp_lohi_dynamic_p1/p5/p10/`
- GRHR: `temp_grhr_k4/` (已有，不需要修改)

### 輸出文件命名
- Baseline: `baseline_dynamic_p{1,5,10}_signaling_stats.json`
- LoHi: `lohi_dynamic_p{1,5,10}_signaling_stats.json`
- GRHR: `hierarchical_gid_27deg_dynamic_p{1,5,10}_k{1,2,4,6,8,999}_signaling_stats.json`

## 執行腳本

### 1. 快速測試（20 秒）
```bash
./test_chaos_monkey_quick.sh
```

**用途**: 驗證 Chaos Monkey 整合是否正確工作
**預期結果**: 
- 產生 `chaos_monkey_baseline_test.log` 和 `chaos_monkey_lohi_test.log`
- 兩個算法都能偵測到 `topology_change` 事件

### 2. 完整重跑（200 秒 × 6 場景 ≈ 2 小時）
```bash
./rerun_baseline_lohi_dynamic.sh
```

**執行順序**：
1. Baseline Dynamic P1 (~5 分鐘)
2. Baseline Dynamic P5 (~5 分鐘)
3. Baseline Dynamic P10 (~5 分鐘)
4. LoHi Dynamic P1 (~15 分鐘)
5. LoHi Dynamic P5 (~15 分鐘)
6. LoHi Dynamic P10 (~15 分鐘)

**自動處理**：
- 設置環境變數
- 清除舊的暫存目錄
- 運行模擬
- 合併暫存文件（使用去重）
- 移動 Chaos Monkey 日誌

## 驗證步驟

### 1. 檢查 Chaos Monkey 日誌
```bash
# 應該包含 5 次注入記錄（snapshot 0, 20, 40, 60, 80）
cat paper/satellite_networks_state/analytic_result/chaos_monkey_baseline_p1.log
cat paper/satellite_networks_state/analytic_result/chaos_monkey_lohi_p1.log
```

### 2. 驗證 changed_entries 遞增
```bash
python3 compare_changed_entries.py
```

**預期結果**：
- Normal: 773,324 (不變)
- Dynamic P1: > 773,324 (略增)
- Dynamic P5: > Dynamic P1 (中等增加)
- Dynamic P10: > Dynamic P5 (顯著增加)

### 3. 重新生成比較報告
```bash
python3 analyze_algorithm_comparison_dynamic.py
```

**預期結果**：
- Baseline 控制開銷隨失效率增加
- LoHi 控制開銷隨失效率增加
- 與 GRHR 的對比更加真實可信

## 技術細節

### 去重邏輯
使用 4 元組作為唯一鍵：
```python
key = (snapshot, time_ms, event_type, json.dumps(detail, sort_keys=True))
```

### ISL 失效注入時機
- **Baseline**: 圖檢查後、Floyd-Warshall 計算前
- **LoHi**: 權重重置後、分群操作前
- **GRHR**: 分群操作前（已實作）

### 拓撲變化檢測
- **Baseline**: 比較前後 snapshot 的 ISL 邊數 (`delta_isl`)
- **LoHi**: 檢測群圖邊數變化 (`delta_group_edges`)
- **GRHR**: 檢測 GID 分群變化 (`delta_isl`, `delta_gsl`)

## 預期成果

修復完成後，演算法比較將更加準確：

1. **Normal 場景**（無失效）：
   - Baseline < GRHR < LoHi

2. **Dynamic P1 場景**（1% 失效）：
   - Baseline 略增 (~5-10%)
   - GRHR 中等增加 (~100-150%)
   - LoHi 略增 (~5-10%)

3. **Dynamic P10 場景**（10% 失效）：
   - Baseline 顯著增加 (~50-100%)
   - GRHR 大幅增加 (~300-400%)
   - LoHi 中等增加 (~20-50%)

**論文貢獻**：證明 GRHR 在動態失效場景下能夠快速響應拓撲變化，雖然控制開銷較高，但能維持路由正確性。
