# LoHi 演算法實作總結

## 概述
依照文獻 "Load-Aware Hierarchical Information-Centric Routing for Large-Scale LEO Satellite Networks" 實作 LoHi 路由演算法，作為 `algorithm_hierarchical_virtual_gid` 的文獻 baseline。

## 實作重點

### 1. 分群機制（p×s = 6×10）
- **固定分群模式**：6 個連續軌道平面 × 每平面連續 10 顆衛星
- **群定義**：
  - `plane_block_id = plane_id // 6`
  - `seg_id_in_plane = pos_in_plane // 10`
  - `group_key = (plane_block_id, seg_id_in_plane)`
- **特性**：
  - 群成員固定（基於星座結構）
  - 群會隨軌道移動
  - 每群約 60 顆衛星（6 × 10）

### 2. 群內負載感知
- **權重計算**：`weight = geo_len_m + β_q × queue_delay + β_s`
- **僅群內應用**：跨群邊保留原始 `geo_len_m`
- **參數**：
  - `BETA_Q`：佇列延遲權重係數（預設 1.0）
  - `BETA_S`：靜態偏移（預設 0.0）

### 3. 管理衛星（Management Satellite）
- **選擇策略**：
  1. 優先選擇群內度數最高的衛星
  2. 若有多個，選擇 ID 最小的（確保穩定性）
- **強制跳點（ENFORCE_MGMT_HOP=True）**：
  - 每進入/離開一個群都必須經過管理衛星
  - 路徑模式：當前衛星 → 管理衛星 → 邊界衛星
  - 目的：增加路徑長度，符合文獻實作，便於與 GID 比較

### 4. 群圖（Group Graph）建構
- **節點**：每個 PID/群
- **邊**：兩群間存在至少一條實體 ISL 即建邊
- **edge_meta 結構**：
  ```python
  {
    (pid_a, pid_b): {
      'pid_id': int,           # 群際邏輯 PID ID（用於統計）
      'links': int,            # 實體 ISL 數量
      'isl_pairs': [(u,v), ...]  # 所有跨群 ISL 的端點對
    }
  }
  ```
- **成本模式**：
  - `hop`：固定成本 1（預設）
  - `invlinks`：成本 = 1/links（偏好多連結）
  - 加入群級常數化模型：`cost = base + Tg_scale × Tg`

### 5. 群級傳輸成本模型（Tg）
由於不實作 GET/ICN 的完整內容緩存機制，採用簡化的常數化模型：

```python
Tg = (N_g × L_avg × 8) / (A_links × BW)
```

**參數**：
- `N_g`：每個 GET 請求預估的 DATA 物件數（預設 10）
- `L_avg`：平均 DATA 物件大小（預設 1500 bytes）
- `A_links`：該群邊的實體 ISL 數量
- `BW`：單條 ISL 頻寬（預設 1 Gbps）

**環境變數**：
- `LOHI_TG_MODE`：`constant`（預設）或 `off`
- `LOHI_TG_CONST_NG`：N_g 值（預設 10）
- `LOHI_TG_CONST_LAVG`：L_avg 值（預設 1500）
- `LOHI_LINK_BW_BPS`：頻寬（預設 1e9）
- `LOHI_TG_SCALE`：縮放係數（預設 1.0）

### 6. 邊界衛星選擇
- **策略**：選擇 `geo_len_m` 最短的跨群 ISL
- **方向保證**：確保 `u` 在 `src_pid`，`v` 在 `next_pid`

### 7. 路由表生成
- **格式**：First-hop routing table
  - `fstate[(u, dst)] = [(next_hop, if_idx)]`
- **邏輯**：
  1. 在群圖上計算 src_pid → dst_pid 的最短路徑
  2. 對每一跳：
     - 若需管理跳點且當前不是管理衛星 → 先跳到管理衛星
     - 否則 → 跳到邊界衛星（跨群）或目標衛星（同群）
  3. 群內使用 Dijkstra 最短路徑

### 8. 控制信令統計
記錄三類事件：

#### a. `pid_rebuild`（群重建）
- **觸發**：衛星的群歸屬變化
- **計算**：變動群的數量
- **字節數**：`changed_pids × 64`

#### b. `topology_change`（拓撲變化）
- **觸發**：群圖邊的增減
- **計算**：`|當前邊集 - 前次邊集|`
- **字節數**：`|delta| × 16`

#### c. `routing_update`（路由更新）
- **觸發**：fstate 變化
- **計算**：`(u, dst) → next_hop` 對的變化數
- **字節數**：`changed × 16`

### 9. 統計輸出格式
```json
{
  "algorithm": "algorithm_lohi_pure",
  "p": 6,
  "s": 10,
  "timestamp": "2024-xx-xx...",
  "summary": {
    "total_events": int,
    "total_bytes": int,
    "pid_rebuilds": int,
    "routing_updates": int,
    "topology_changes": int
  },
  "timeline": [
    {
      "snapshot": int,
      "sim_time_ms": int,
      "event": str,
      "count": int,
      "bytes": int,
      "detail": {...}
    }
  ]
}
```

**輸出位置**：`analytic_result/lohi_signaling_stats_pure_p6_s10.json`

## 關鍵差異：LoHi vs GID

| 特性 | LoHi | GID |
|------|------|-----|
| 分群依據 | 平面區塊（p×s） | 地理位置（網格） |
| 群大小 | 固定 60 顆 | 動態變化 |
| 管理跳點 | 強制 | 無（直接跨群） |
| 負載感知 | 僅群內 | 可選 |
| 群級成本 | 簡化模型 Tg | 無 |
| 統計欄位 | pid_rebuilds | gid_rebuilds |

## 環境變數配置

```bash
# 群內負載感知
export LOHI_BETA_Q=1.0         # 佇列權重
export LOHI_BETA_S=0.0         # 靜態偏移

# 管理衛星跳點
export LOHI_ENFORCE_MGMT_HOP=1  # 1=強制，0=關閉

# 群級成本模型
export LOHI_TG_MODE=constant    # constant 或 off
export LOHI_TG_CONST_NG=10      # 預估 DATA 物件數
export LOHI_TG_CONST_LAVG=1500  # 平均物件大小（bytes）
export LOHI_LINK_BW_BPS=1000000000  # 1 Gbps
export LOHI_TG_SCALE=1.0        # 縮放係數
```

## 使用方式

### 1. 在配置文件中指定演算法
```bash
dynamic_state_algorithm="algorithm_lohi"
```

### 2. 程式碼調用
```python
from satgen.dynamic_state.algorithm_lohi import algorithm_lohi, init

# 初始化（僅首次）
init()

# 每個時間快照調用
result = algorithm_lohi(
    output_dynamic_state_dir,
    time_since_epoch_ns,
    satellites,
    ground_stations,
    sat_net_graph_only_satellites_with_isls,
    ground_station_satellites_in_range,
    num_isls_per_sat,
    sat_neighbor_to_if,
    list_gsl_interfaces_info,
    prev_output,
    enable_verbose_logs,
    epoch=epoch,
    time_step_ns=time_step_ns
)
```

## 測試驗證

### 單元測試
```bash
python3 test_algorithm_lohi.py
```

**測試內容**：
1. ✓ 星座配置推斷（1584 → 72×22, 1156 → 34×34）
2. ✓ Plane-block 分群邏輯
3. ✓ 群圖建構與 edge_meta
4. ✓ 邊界衛星選擇

### 統計輸出測試
```bash
python3 test_lohi_stats.py
```

**驗證項目**：
- ✓ JSON 格式正確
- ✓ 事件記錄完整
- ✓ 字節數計算正確
- ✓ 與 GID 格式相容

## 檔案清單

### 核心實作
- `satgenpy/satgen/dynamic_state/algorithm_lohi.py` (735 行)
  - `VirtualPIDRouterPlaneBlock`：p×s 分群器
  - `GroupPlanner`：群圖管理
  - `BorderSelector`：邊界選擇
  - `ControlSignalingStats`：統計收集
  - `algorithm_lohi`：主函數

### 整合
- `satgenpy/satgen/dynamic_state/generate_dynamic_state.py`
  - 新增 `algorithm_lohi` 分支
  - 自動初始化

### 測試
- `test_algorithm_lohi.py`：核心功能單元測試
- `test_lohi_stats.py`：統計輸出格式測試

## 後續工作

### 1. 實際模擬
```bash
# 生成動態狀態
cd paper/satellite_networks_state
bash generate_starlink_550_lohi.sh

# 執行 NS-3 模擬
cd ../../ns3-sat-sim
bash run_lohi_experiment.sh
```

### 2. 性能比較
使用現有分析腳本比較三種演算法：
- `algorithm_free_one_only_over_isls_with_stats`（Floyd-Warshall baseline）
- `algorithm_lohi`（文獻 baseline）
- `algorithm_hierarchical_virtual_gid`（你的演算法）

### 3. 繪圖與分析
```bash
cd paper/satgenpy_analysis
python3 compare_three_algorithms.py
```

**比較指標**：
- 平均/最大跳數
- 路徑延遲
- 控制信令開銷
- 路由更新頻率

## 文獻對照

本實作基於以下文獻：
> Load-Aware Hierarchical Information-Centric Routing for Large-Scale LEO Satellite Networks

**對應關係**：
- Section III.A：分群機制 → `VirtualPIDRouterPlaneBlock`
- Section III.B：群內路由 → Dijkstra + 負載感知權重
- Section III.C：群間路由 → `GroupPlanner.shortest_group_path()`
- Section III.D：邊界選擇 → `BorderSelector.pick_border_pair()`
- Section IV：性能評估 → 控制信令統計

## 已知限制

1. **未實作 ICN 內容緩存**：使用簡化的群級成本模型 Tg
2. **管理衛星固定**：基於度數，不會動態調整
3. **負載感知僅群內**：跨群邊使用固定成本
4. **星座配置推斷**：依賴常見配置，非通用

## 總結

✅ **完成項目**：
1. ✓ 完整實作 LoHi 核心邏輯（p×s 分群、管理跳點、群圖、負載感知）
2. ✓ 修復 bug（BorderSelector 方向驗證）
3. ✓ 整合到 generate_dynamic_state.py
4. ✓ 單元測試驗證通過
5. ✓ 統計輸出格式與 GID 相容

✅ **可用於**：
- 作為 algorithm_hierarchical_virtual_gid 的文獻 baseline
- 與 Floyd-Warshall 和 GID 進行三方比較
- 論文中展示你的演算法優於文獻方法

🎯 **下一步**：執行完整模擬並進行性能比較，為論文準備數據和圖表。
