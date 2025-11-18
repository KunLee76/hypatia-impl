# LoHi 新格式遷移操作清單

## ✅ 已完成

1. ✅ **舊格式分析完成** - 使用現有的 `lohi_signaling_stats_pure_p6_s10.json` 生成報告
2. ✅ **LoHi 算法已更新** - `algorithm_lohi.py` 的 `to_json()` 方法已改為輸出標準格式
3. ✅ **分析腳本已簡化** - `hypatia_multi_algorithm_analyzer.py` 移除標準化邏輯，只接受新格式

---

## 📋 接下來的步驟

### Step 1: 備份舊的分析結果（可選）

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia

# 備份舊格式的分析結果
mv multi_algorithm_analysis multi_algorithm_analysis_OLD_FORMAT_BACKUP

# 或者只備份報告文件
cp multi_algorithm_analysis/multi_algorithm_comparison_report.txt \
   comparison_report_OLD_FORMAT.txt
```

### Step 2: 刪除舊的 LoHi 統計檔案

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 刪除舊格式的統計檔案
rm analytic_result/lohi_signaling_stats_pure_p6_s10.json

# 確認已刪除
ls -lh analytic_result/
```

**預期輸出**：
```
baseline_floyd_warshall_signaling_stats.json
hierarchical_gid_27deg_signaling_stats.json
（lohi 檔案已不存在）
```

### Step 3: 重新執行 LoHi 測試（生成新格式）

```bash
# 確保在正確目錄
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 執行 LoHi 測試（20 秒模擬，10 執行緒）
time python main_starlink_550.py 20 100 isls_plus_grid \
  ground_stations_top_100 algorithm_lohi 10
```

**預期時間**：約 18-22 分鐘

**預期輸出結尾**：
```
...
✅ LoHi routing computation completed
Total time: XXXs

real    XXmXX.XXXs
user    XXmXX.XXXs
sys     XmXX.XXXs
```

### Step 4: 驗證新格式正確

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

# 檢查新生成的檔案
ls -lh analytic_result/lohi_signaling_stats_pure_p6_s10.json

# 查看前 60 行（驗證格式）
head -60 analytic_result/lohi_signaling_stats_pure_p6_s10.json
```

**應該看到的新格式**：
```json
{
  "algorithm": "algorithm_lohi_pure",
  "algorithm_display_name": "LoHi (p=6, s=10)",  // ✅ 新增
  "p": 6,
  "s": 10,
  "timestamp": "2025-11-18T...",
  "summary": {
    "total_events": 611,
    "total_bytes": 24318736,
    "by_type": {                                  // ✅ 新格式
      "pid_rebuild": {
        "count": 201,
        "bytes": ...
      },
      "routing_update": {
        "count": 209,
        "bytes": ...
      },
      "topology_change": {
        "count": 201,
        "bytes": ...
      }
    }
  },
  "timeline": [
    {
      "snapshot": 60,
      "time_ms": 6000,                            // ✅ 統一欄位名（不是 sim_time_ms）
      "event": "pid_rebuild",
      "count": 1,
      "bytes": 2304,
      "detail": {
        "changed_pids": 36
      }
    },
    ...
  ]
}
```

### Step 5: 執行新格式分析

```bash
cd /home/kun/ssd2t/Leo/kun_hypatia

# 執行分析腳本
python hypatia_multi_algorithm_analyzer.py
```

**預期輸出**：
```
============================================================
Hypatia 多算法控制信令統計分析工具
============================================================

🔍 查找算法統計文件...

📊 找到 3 個統計文件:
  - baseline: 1 個文件
  - hierarchical_floyd: 1 個文件
  - lohi: 1 個文件

  ✅ Floyd-Warshall Baseline: 209 事件, 264,984,896 字節
  ✅ Hierarchical GID (27°): 239 事件, 827,680 字節
  ✅ LoHi (p=6, s=10): 611 事件, 24,318,736 字節

📄 比較報告已保存: multi_algorithm_analysis/multi_algorithm_comparison_report.txt
  📊 圖表1已保存: multi_chart1_overall_comparison.png
  📊 圖表2已保存: multi_chart2_timeline_analysis.png
  📊 圖表3已保存: multi_chart3_event_type_distribution.png
  📊 圖表4已保存: multi_chart4_improvement_percentage.png

✅ 所有圖表已保存到: multi_algorithm_analysis/

🎉 分析完成！
結果保存在: multi_algorithm_analysis/
  - multi_algorithm_comparison_report.txt (詳細比較報告)
  - multi_chart1_overall_comparison.png (總體比較)
  - multi_chart2_timeline_analysis.png (時間軸分析)
  - multi_chart3_event_type_distribution.png (事件類型分佈)
  - multi_chart4_improvement_percentage.png (相對改進)
```

### Step 6: 檢查結果

```bash
# 查看報告
cat multi_algorithm_analysis/multi_algorithm_comparison_report.txt

# 查看圖表
ls -lh multi_algorithm_analysis/*.png
```

### Step 7: 對比新舊結果（可選）

如果你在 Step 1 備份了舊的分析結果，可以對比：

```bash
# 對比數值是否一致（格式不同，但數值應該相同）
diff multi_algorithm_analysis_OLD_FORMAT_BACKUP/multi_algorithm_comparison_report.txt \
     multi_algorithm_analysis/multi_algorithm_comparison_report.txt

# 如果數值相同，說明格式遷移成功！
```

---

## ⚠️ 可能的錯誤處理

### 錯誤 1: 格式驗證失敗

**錯誤訊息**：
```
❌ 格式錯誤: lohi_signaling_stats_pure_p6_s10.json
   期望 summary.by_type 結構，但未找到。
   請確保所有算法輸出統一格式的統計數據。
```

**原因**：可能還在使用舊的 LoHi 統計檔案

**解決方法**：
```bash
# 確認刪除舊檔案
rm paper/satellite_networks_state/analytic_result/lohi_signaling_stats_pure_p6_s10.json

# 重新執行測試
cd paper/satellite_networks_state
time python main_starlink_550.py 20 100 isls_plus_grid \
  ground_stations_top_100 algorithm_lohi 10
```

### 錯誤 2: 時間欄位名稱錯誤

**症狀**：圖表 2（時間軸分析）為空白或錯誤

**檢查**：
```bash
# 檢查 timeline 中的欄位名
grep -A 5 '"timeline"' analytic_result/lohi_signaling_stats_pure_p6_s10.json | head -20
```

**應該看到 `"time_ms"`，而不是 `"sim_time_ms"`**

---

## 📊 期望的圖表

### Chart 1: 總體比較
- **橘色柱**：Floyd-Warshall Baseline (最高)
- **綠色柱**：Hierarchical GID (27°) (最低)
- **紫色柱**：LoHi (p=6, s=10) (中間)

### Chart 2: 時間軸分析
- **橘色線**：Baseline（快速上升到最高）
- **綠色線**：GID（幾乎水平，非常低）
- **紫色線**：LoHi（中等斜率）

### Chart 3: 事件類型分佈
- Baseline: 只有 `routing_update`
- GID: `pid_rebuild` + `gateway_update` + `topology_change`
- LoHi: `pid_rebuild` + `routing_update` + `topology_change`

### Chart 4: 改進百分比
- GID: +99.X% (相對 Baseline 大幅改進)
- LoHi: +90.X% (相對 Baseline 顯著改進)

---

## ✅ 完成檢查清單

- [ ] **Step 1**: 備份舊分析結果（可選）
- [ ] **Step 2**: 刪除舊的 LoHi 統計檔案
- [ ] **Step 3**: 重新執行 LoHi 測試（~20 分鐘）
- [ ] **Step 4**: 驗證新格式正確（`by_type` + `time_ms`）
- [ ] **Step 5**: 執行新格式分析
- [ ] **Step 6**: 檢查報告和圖表
- [ ] **Step 7**: 對比新舊結果（可選）

---

## 🎯 總結

**現在的狀態**：
- ✅ LoHi 算法已更新（輸出新格式）
- ✅ 分析腳本已簡化（只接受新格式）
- ✅ 舊格式分析已完成（已備份）

**下一步**：執行 Step 2-7，完成格式遷移！

預計總耗時：約 25-30 分鐘（主要是 LoHi 測試的 20 分鐘）
