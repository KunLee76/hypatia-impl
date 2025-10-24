# Hypatia Signaling Analyzer 更新文檔

## 更新概覽

本次更新優化了信令分析器以支持：
1. **網格大小比較**：支持比較不同 GRID_DEG 配置（10°, 15°, 20°, 25°等）
2. **獨立圖表**：生成 4 張獨立 PNG 文件而非單一 2x2 網格圖
3. **數值標籤**：Chart 3 事件類型分佈圖添加數值標籤
4. **動態命名**：文件名和顯示名稱包含網格大小信息
5. **術語更新**：所有 "Hierarchical PID" 改為 "Hierarchical GID"

## 修改文件

### 1. `satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_pid.py`

**變更：**
- 輸出文件名：`hierarchical_gid_15deg_signaling_stats.json`（動態基於 GRID_DEG）
- JSON 新增字段：
  ```python
  "algorithm_display_name": "Hierarchical GID (15°)"
  "grid_deg": 15  # 實際網格度數
  ```

**代碼位置：**
- Lines 1285-1315: 狀態初始化和文件名設定
- Lines 1340-1370: JSON 輸出結構

### 2. `hypatia_signaling_analyzer.py`

**主要變更：**

#### a) 動態文件發現
```python
def find_hierarchical_files(self):
    """查找所有 hierarchical_gid_*deg_signaling_stats.json 文件"""
    pattern = "hierarchical_gid_*deg_signaling_stats.json"
    files = glob.glob(pattern)
    return sorted(files)
```

#### b) 獨立圖表生成
- `generate_separate_charts()`：主控方法
- `_generate_chart1_overall()`：整體對比
- `_generate_chart2_timeline()`：時間線分析
- `_generate_chart3_event_types()`：事件類型分佈（含數值標籤）
- `_generate_chart4_improvement()`：改進百分比

#### c) 輸出文件
- `chart1_overall_comparison.png`
- `chart2_timeline_analysis.png`
- `chart3_event_type_distribution.png`
- `chart4_improvement_percentage.png`

#### d) Chart 3 數值標籤
```python
for bars, counts in [(bars1, h_counts), (bars2, b_counts)]:
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(count)}',
                ha='center', va='bottom',
                fontsize=9, fontweight='bold')
```

## 使用方法

### 測試更新
```bash
# 驗證所有修改
python test_analyzer_updates.py
# 應該顯示：3/3 測試通過 ✅
```

### 運行流程

#### 步驟 1：生成信令統計數據
```bash
cd paper/satellite_networks_state
python main_25x25_fast.py algorithm_hierarchical_virtual_pid
```

**輸出文件：**
- `hierarchical_gid_15deg_signaling_stats.json` (GRID_DEG=15 時)
- `baseline_signaling_stats.json`

#### 步驟 2：生成圖表
```bash
cd ../..  # 回到項目根目錄
python hypatia_signaling_analyzer.py
```

**輸出文件：**
- `chart1_overall_comparison.png` - 總信令對比柱狀圖
- `chart2_timeline_analysis.png` - 時間線趨勢圖
- `chart3_event_type_distribution.png` - 事件類型分佈（帶數值標籤）
- `chart4_improvement_percentage.png` - 改進百分比

### 多網格大小比較

如需測試不同網格大小：

```bash
# 修改 satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_pid.py
# 找到 GRID_DEG = 15，修改為所需值

# 測試 10°
GRID_DEG = 10
python main_25x25_fast.py algorithm_hierarchical_virtual_pid
# 生成 hierarchical_gid_10deg_signaling_stats.json

# 測試 20°
GRID_DEG = 20
python main_25x25_fast.py algorithm_hierarchical_virtual_pid
# 生成 hierarchical_gid_20deg_signaling_stats.json

# 分析所有配置
python ../../hypatia_signaling_analyzer.py
# 如果有多個 hierarchical_gid_*deg 文件，會列出所有可用文件
```

## JSON 格式

### 新格式示例
```json
{
  "algorithm": "algorithm_hierarchical_virtual_pid",
  "algorithm_display_name": "Hierarchical GID (15°)",
  "grid_deg": 15,
  "timestamp": "2025-01-22T10:30:00",
  "summary": {
    "total_events": 12345,
    "topology_update": 1000,
    "routing_update": 500,
    "gsl_failure": 50,
    "total_signaling_messages": 15000
  },
  "timeline": [
    {
      "time_ms": 0,
      "topology_update": 100,
      "routing_update": 50,
      ...
    }
  ]
}
```

### 字段說明
- `algorithm_display_name`：顯示在圖表中的名稱（含網格大小）
- `grid_deg`：網格度數（數值型），用於比較分析

## 圖表詳情

### Chart 1: Overall Comparison (總體對比)
- 比較 Hierarchical GID vs Baseline 總信令數
- Y 軸：Total Signaling Messages
- 顯示具體數值和改進百分比

### Chart 2: Timeline Analysis (時間線分析)
- 信令隨時間變化趨勢
- X 軸：時間（毫秒）
- Y 軸：累計信令數
- 雙線圖：Hierarchical GID vs Baseline

### Chart 3: Event Type Distribution (事件類型分佈)
- **新增功能：數值標籤**
- 並排柱狀圖對比各事件類型
- 類型：topology_update, routing_update, gsl_failure 等
- 每個柱子頂端顯示精確數值（粗體）

### Chart 4: Improvement Percentage (改進百分比)
- 按事件類型顯示改進百分比
- 正值表示減少（綠色）
- 負值表示增加（紅色）

## 性能影響

### Floyd-Warshall vs Dijkstra
- **Floyd-Warshall**：O(V³) ≈ 3.97 billion ops
- **Dijkstra**：O(G × (V+E)logV) ≈ 8.66 million ops
- **理論加速比**：460x

### 網格大小影響
- **GRID_DEG = 10°**：更多 GID，更細粒度，可能更多路由更新
- **GRID_DEG = 15°**：平衡（當前默認）
- **GRID_DEG = 20°**：更少 GID，更少路由更新，但可能路徑次優

## 待辦事項

### ✅ 已完成
- ✅ 修改 algorithm_hierarchical_virtual_pid.py 文件名和 JSON 格式
- ✅ 重構 hypatia_signaling_analyzer.py 為獨立圖表
- ✅ 添加 Chart 3 數值標籤
- ✅ 更新所有 "PID" 為 "GID" 術語
- ✅ 創建測試腳本驗證修改

### ⏳ 待執行
- ⏳ 運行實際測試生成 hierarchical_gid_15deg_signaling_stats.json
- ⏳ 驗證 4 張圖表正確生成
- ⏳ 檢查 Chart 3 數值標籤顯示

### 🔮 未來工作
- 🔮 將相同修改應用到 algorithm_hierarchical_virtual_pid_dijkstra.py
- 🔮 測試多個網格大小配置（10°, 15°, 20°, 25°）
- 🔮 創建網格大小比較腳本（batch 測試）
- 🔮 集成 Dijkstra 優化版本性能數據

## 故障排查

### 問題：找不到 hierarchical_gid_*deg_signaling_stats.json
**解決方案：**
```bash
# 確認在正確目錄
cd paper/satellite_networks_state

# 檢查是否已生成
ls -la *.json

# 重新生成
python main_25x25_fast.py algorithm_hierarchical_virtual_pid
```

### 問題：圖表沒有數值標籤
**解決方案：**
- 檢查 `_generate_chart3_event_types()` 方法
- 確認包含 `ax.text(...)` 循環
- 重新運行：`python hypatia_signaling_analyzer.py`

### 問題：顯示 "Hierarchical PID" 而非 "Hierarchical GID"
**解決方案：**
- 檢查 JSON 文件中 `algorithm_display_name` 字段
- 確認演算法文件已更新
- 重新生成統計數據

## 相關文件

- `algorithm_hierarchical_virtual_pid.py`: 原始層級路由演算法
- `algorithm_hierarchical_virtual_pid_dijkstra.py`: Dijkstra 優化版本（未修改）
- `fstate_calculation.py`: 包含兩種 fstate 計算方法
- `hypatia_signaling_analyzer.py`: 信令分析和可視化工具
- `test_analyzer_updates.py`: 驗證腳本

## 參考資料

### 相關論文概念
- **GID (Geographical ID)**：基於經緯度的衛星分組
- **Control Signaling**：路由更新和拓撲變化消息
- **Hierarchical Routing**：使用虛擬節點減少路由複雜度

### 網格度數選擇
```
10° → 36 × 18 = 648 GIDs (高精度)
15° → 24 × 12 = 288 GIDs (平衡，默認)
20° → 18 × 9 = 162 GIDs (粗粒度)
25° → 14 × 7 = 98 GIDs (極粗)
```

---

**創建時間：** 2025-01-22  
**版本：** 1.0  
**作者：** GitHub Copilot & 用戶  
**測試狀態：** ✅ 所有驗證通過 (3/3)
