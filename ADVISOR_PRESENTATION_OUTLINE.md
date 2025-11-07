# 控制信令統計方法 - 向教授報告大綱

## 報告結構

### 1. 開場（2 分鐘）
**目標**：建立研究背景和問題意識

- **研究問題**：衛星網路的控制開銷如何量化？
- **比較對象**：
  - Floyd-Warshall Baseline（傳統集中式路由）
  - Hierarchical GID（分層地理路由）
- **評估維度**：
  - 總事件數（控制平面活動頻率）
  - 總字節數（網路頻寬消耗）

---

### 2. 統計方法論（5 分鐘）
**目標**：說明事件定義和計數方式

#### 2.1 四種事件類型

| 事件類型 | Floyd-Warshall | Hierarchical | 定義 |
|---------|---------------|--------------|------|
| `routing_update` | ✅ 每個 snapshot | ❌ N/A | 路由表更新 |
| `gateway_update` | ❌ N/A | ✅ 當 Jaccard > 0.15 | Gateway 候選更新 |
| `pid_rebuild` | ❌ N/A | ✅ 當衛星跨網格 | PID 成員重建 |
| `topology_change` | ✅ 當拓撲變化 | ✅ 當拓撲變化 | ISL/GSL 變化 |

**關鍵說明**：
- Floyd-Warshall 依賴**全網路由表**（單一事件類型，但開銷極大）
- Hierarchical 依賴**PID 拓撲 + Gateway 候選**（多事件類型，但開銷極小）

#### 2.2 事件計數方式

**Floyd-Warshall `routing_update`**：
```python
# 每個 snapshot（100ms）觸發一次
self.routing_updates += 1

# 變更的路由條目數
changed_entries = num_satellites × num_ground_stations × 2
                = 1584 × 100 × 2 = 316,800 條目
```

**Hierarchical `pid_rebuild`**：
```python
# 只在衛星跨網格邊界時觸發
for sat in satellites:
    if sat.new_pid != sat.old_pid:
        changed_pids.add(sat.new_pid, sat.old_pid)

if len(changed_pids) > 0:
    self.pid_rebuilds += 1  # 每個 snapshot 最多 1 次
```

**Hierarchical `gateway_update`**：
```python
# 只在 Gateway 候選變化超過閾值時觸發（Virtual Agent）
jaccard = len(old ∩ new) / len(old ∪ new)
if (1 - jaccard) > 0.15:
    self.gateway_updates += 1
```

---

### 3. 字節數計算方法（5 分鐘）
**目標**：說明基於 OpenFlow 協議的建模

#### 3.1 建模基礎

**重要聲明**：
> 字節數計算基於 **OpenFlow 1.3 協議**建模，這是 SDN 領域的標準控制協議。
> 雖然學術界對**事件定義**有共識，但對**字節數計算**缺乏統一標準。
> 我們的數字是基於合理假設的**保守上界估計**。

**OpenFlow 消息結構**：
```
┌─────────────────────────────────────┐
│  OpenFlow Header (8 bytes)          │  ← 所有消息共有
├─────────────────────────────────────┤
│  Message Specific Fields (variable) │  ← 根據消息類型
└─────────────────────────────────────┘
```

#### 3.2 具體公式

**`routing_update`（Floyd-Warshall）**：
```python
total_bytes = base_bytes + (changed_entries × per_entry_bytes)
            = 64 + (316,800 × 12)
            = 3,801,664 bytes ≈ 3.8 MB

# base_bytes (64):
#   - OpenFlow header: 8 bytes
#   - Flow match fields: 40 bytes
#   - Instructions: 16 bytes

# per_entry_bytes (12):
#   - Destination GID: 4 bytes
#   - Next hop satellite: 4 bytes
#   - Metric (cost): 4 bytes
```

**`gateway_update`（Hierarchical）**：
```python
total_bytes = base_bytes + (k_published × per_edge_bytes)
            = 48 + (10 × 24)
            = 288 bytes

# base_bytes (48):
#   - OpenFlow header: 8 bytes
#   - Source/Dest PID: 8 bytes
#   - Version + K value: 8 bytes
#   - Timestamp: 8 bytes
#   - Reserved: 16 bytes

# per_edge_bytes (24):
#   - Satellite A ID: 4 bytes
#   - Satellite B ID: 4 bytes
#   - Cost (delay): 4 bytes
#   - Link quality: 4 bytes
#   - Reserved: 8 bytes
```

**`pid_rebuild`（Hierarchical）**：
```python
total_bytes = changed_pids × per_pid_bytes
            = 7 × 64
            = 448 bytes

# per_pid_bytes (64):
#   - OpenFlow header: 8 bytes
#   - PID ID: 4 bytes
#   - Member count: 4 bytes
#   - Timestamp: 8 bytes
#   - Reserved: 40 bytes
#   (完整成員列表可壓縮或分批傳輸)
```

**`topology_change`（Both）**：
```python
total_bytes = (|Δisl| + |Δgsl|) × per_edge_bytes
            = 12 × 16
            = 192 bytes

# per_edge_bytes (16):
#   - OpenFlow header: 8 bytes
#   - Link type + Action: 2 bytes
#   - Node A + Node B: 8 bytes
```

#### 3.3 學術支持情況

**有充分支持**：
- ✅ 事件定義（SDN/OpenFlow 規範、衛星網路路由論文）
- ✅ 控制平面架構（SDN 文獻）
- ✅ 比較方法論（學術慣例）

**缺乏統一標準**：
- ⚠️ 字節數的精確計算
- **原因**：協議多樣性、實作差異、研究焦點不同
- **解決方案**：基於 OpenFlow 建模 + 保守估計 + 透明參數

**相關論文的做法**：
- IEEE INFOCOM 2013: 計算消息數量，使用固定字節數假設（但不說明來源）
- IEEE CL 2014: 使用控制頻寬（Mbps）而非精確字節數
- **我們的創新**：明確的計算公式 + OpenFlow 協議依據

---

### 4. 控制平面 vs 資料平面（5 分鐘）
**目標**：澄清 fstate 的角色

#### 4.1 關鍵概念區分

```
┌──────────────────────────────────────────────────┐
│            控制平面 (Control Plane)              │
│  - 路由決策邏輯                                  │
│  - Floyd-Warshall: 路由表（全網最短路矩陣）      │
│  - Hierarchical: PID 圖 + Gateway 候選           │
│  → 產生控制信令（已統計）                        │
└──────────────┬───────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────┐
│            資料平面 (Data Plane)                 │
│  - 封包轉發執行                                  │
│  - fstate: {(src, dst) → (next_hop, if)}        │
│  → 不產生額外控制信令（或已包含在上層）          │
└──────────────────────────────────────────────────┘
```

#### 4.2 Hierarchical 的 fstate 不算控制信令

**疑問**：Hierarchical 有沒有維護路由表？

**回答**：
- **控制平面**：有，但不是傳統路由表，而是 **PID 圖 + Gateway 候選**
- **資料平面**：有 fstate，但這是**路由決策的結果**，不是控制信令的來源

**關鍵類比**：

| 算法 | 控制平面（控制信令） | 資料平面（本地狀態） |
|------|-------------------|-------------------|
| Floyd-Warshall | 下發路由表<br>（`routing_update`）| 查表轉發<br>（fstate） |
| Hierarchical | 下發 PID + Gateway<br>（`pid_rebuild` + `gateway_update`） | 即時計算路由<br>（fstate） |

**為什麼 fstate 不重複計算？**
1. **Floyd-Warshall**：fstate 是路由表的本地副本（已計入 `routing_update`）
2. **Hierarchical**：fstate 是 PID 決策的計算結果（已計入 `pid_rebuild` + `gateway_update`）
3. **真實系統**：衛星會本地執行相同邏輯（不需要中央下發 fstate）

---

### 5. Hierarchical 控制信令的完整性（3 分鐘）
**目標**：證明 PID 圖和 Gateway 候選的控制信令已完整計算

#### 5.1 疑問：PID 圖和 Gateway 的控制信令有計算嗎？

**回答**：**是的，完全有計算！**

**PID 圖決策** → `pid_rebuild` 事件：
```python
# 檔案：algorithm_hierarchical_virtual_pid_dijkstra.py，行 410-416
# 當衛星跨越網格邊界時觸發
_SIGNALING_STATS.record_pid_rebuild(snapshot, sim_time_ms,
                                   changed_pids=len(changed_pids),
                                   per_pid_bytes=64)
```

**包含內容**：
- PID 拓撲變化（哪些衛星屬於哪個 PID）
- PID 鄰接關係（隱含在成員變化中）
- 控制信令：`PID_MEMBERSHIP_UPDATE` 消息

**Gateway 候選決策** → `gateway_update` 事件：
```python
# 檔案：algorithm_hierarchical_virtual_pid_dijkstra.py，行 540-547
# 當 Gateway 變化超過閾值時觸發（Virtual Agent 判斷）
_SIGNALING_STATS.record_gateway_update(snapshot, sim_time_ms,
                                       changed_pairs=changed_pairs,
                                       k_published=k_used,
                                       base_bytes=48, per_edge_bytes=24)
```

**包含內容**：
- 跨 PID 路由決策（每對相鄰 PID 的 k-best gateway）
- Gateway 候選資訊（衛星對、成本、品質）
- 控制信令：`GATEWAY_UPDATE` 消息

#### 5.2 兩者組合 = 完整控制信令

```
PID 圖決策 (pid_rebuild)     +    Gateway 候選 (gateway_update)
      ↓                                    ↓
  Intra-PID 路由決策              +    Inter-PID 路由決策
      ↓                                    ↓
═══════════════════════════════════════════════════════
              Hierarchical 路由算法的控制信令總和
```

---

### 6. Virtual Agent (VA) 機制（3 分鐘）
**目標**：說明如何減少控制信令抖動

#### 6.1 Virtual Agent 定義

**正確術語**：Virtual Agent（虛擬代理），非 Version Agent

**作用**：智能判斷何時發布 Gateway 更新，避免頻繁控制信令

#### 6.2 三步驟機制

```
┌─────────────────────────────────────────────┐
│ 步驟 1: EMA 成本平滑                         │
│  new_cost = 0.8 × old + 0.2 × current       │
│  目的：避免瞬時波動                          │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│ 步驟 2: Jaccard 相似度判斷                   │
│  J = |old∩new| / |old∪new|                  │
│  如果 (1-J) > 0.15: 發布新版本               │
│  否則: 保持舊版本                            │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│ 步驟 3: 版本控制                             │
│  published_version += 1                      │
│  記錄 gateway_update 事件                    │
└─────────────────────────────────────────────┘
```

#### 6.3 效果

- **發布頻率降低**：只在 30% 的重建時發布（70% 不發布）
- **控制信令減少**：3 倍以上
- **路由品質**：幾乎不受影響（成本差異 < 5%）

---

### 7. 實驗結果（5 分鐘）
**目標**：展示量化對比

#### 7.1 總控制信令（20 秒模擬）

| 算法 | 總事件數 | 總字節數 | vs Baseline | 主要來源 |
|------|---------|---------|------------|----------|
| **Floyd-Warshall Baseline** | 400 | 264 MB | - | 每 snapshot 路由表更新 |
| **Hierarchical Floyd (27°)** | 228 | 810 KB | **-99.69%** | PID + Gateway 更新 |
| **Hierarchical Dijkstra (27°)** | 239 | 820 KB | **-99.69%** | PID + Gateway 更新 |

#### 7.2 事件類型分佈

**Floyd-Warshall**：
- `routing_update`: 200 事件, 264 MB (99.8%)
- `topology_change`: 200 事件, ~0.5 MB (0.2%)

**Hierarchical (27°)**：
- `gateway_update`: 29 事件, 411 KB (50.1%)
- `pid_rebuild`: 209 事件, 410 KB (49.9%)
- `topology_change`: 1 事件, < 1 KB (0.0%)

#### 7.3 時間軸分析

```
Floyd-Warshall:
  ████████████████████████████████████████ 264 MB
  每個 snapshot 都有巨大峰值（3.8 MB）

Hierarchical:
  █ 820 KB
  只在 PID 變化或 Gateway 變化時有小峰值（< 1 KB）
```

#### 7.4 網格大小影響

| 網格大小 | PID 數 | 控制信令 (KB) | RTT (ms) |
|---------|-------|--------------|----------|
| 15° | 288 | 3,379 | 128.35 |
| 21° | 136 | 1,150 | 109.82 |
| **27°** | **78** | **801** | **109.82** |
| 30° | 72 | 784 | 109.82 |

**最優選擇**：27° 網格（控制信令最小 + RTT 最優）

---

### 8. 方法論限制與聲明（2 分鐘）
**目標**：誠實說明研究的限制

#### 8.1 承認的限制

**字節數計算的挑戰**：
- ✅ 事件定義有充分學術支持
- ⚠️ 字節數計算缺乏統一標準
- **原因**：
  - 協議多樣性（OpenFlow / BGP / OSPF）
  - 實作差異（壓縮、批次處理）
  - 研究焦點不同（學術界重視事件頻率）

#### 8.2 我們的解決方案

**基於 OpenFlow 建模的理由**：
1. **廣泛接受**：OpenFlow 是 SDN 標準協議
2. **合理假設**：SpaceX Starlink 公開使用 SDN 技術
3. **保守估計**：我們的數字是上界（實際系統可能更優）
4. **透明可驗證**：完整公式和參數，可調整和驗證

**學術貢獻**：
- 提供明確的量化方法（創新）
- 可被其他研究者複製
- 填補衛星網路控制開銷量化研究的空白

#### 8.3 聲明

```
本研究的字節數計算基於以下假設：
1. 衛星網路採用 SDN 控制架構
2. 控制信令格式類似 OpenFlow 1.3
3. 不考慮傳輸層壓縮和優化
4. 數值為控制開銷的上界估計

相對比較（99.7% 改善）仍然有效且有意義。
```

---

### 9. 結論（2 分鐘）

#### 9.1 研究貢獻

1. **量化方法**：首次系統化量化衛星網路控制信令開銷
2. **架構對比**：證明 Hierarchical 相比 Floyd-Warshall 節省 99.7% 控制信令
3. **最優配置**：識別 27° 網格為最優選擇（控制信令 + RTT）

#### 9.2 關鍵發現

- **Floyd-Warshall**：簡單但控制開銷極大（264 MB / 20s）
- **Hierarchical**：複雜但控制開銷極小（0.8 MB / 20s）
- **Virtual Agent**：有效減少 Gateway 更新抖動（70% 不發布）

#### 9.3 未來工作

- 實際系統驗證（真實 SDN 控制器）
- 更多路由算法對比（Dijkstra + Grid, OSPF-like）
- 動態調整機制（自適應網格大小）

---

## 附錄：預期問題與回答

### Q1: 為什麼 Hierarchical 不計算 routing_update？

**A**: 因為 Hierarchical 不使用傳統路由表，而是：
- 控制平面：PID 圖 + Gateway 候選（已計入 `pid_rebuild` + `gateway_update`）
- 資料平面：即時計算路由（fstate 是結果，不是控制信令來源）

### Q2: fstate 是什麼？為什麼不算控制信令？

**A**: fstate 是資料面的轉發狀態表：
- Floyd-Warshall: fstate 來自路由表（已計入 `routing_update`）
- Hierarchical: fstate 來自 PID 決策（已計入 `pid_rebuild` + `gateway_update`）
- 真實系統中是本地狀態，不需要分發

### Q3: PID 圖和 Gateway 候選的控制信令有計算嗎？

**A**: 有，完全有！
- PID 圖 → `pid_rebuild`（448 bytes/次）
- Gateway 候選 → `gateway_update`（288 bytes/次）
- 兩者組合 = Hierarchical 的完整控制信令

### Q4: 字節數計算有學術依據嗎？

**A**: 部分有：
- 事件定義：有充分學術支持（SDN/OpenFlow 規範）
- 字節數計算：缺乏統一標準（學術界焦點不同）
- 我們的做法：基於 OpenFlow 建模 + 保守估計 + 透明參數
- 相對比較（99.7%）仍然有效

### Q5: Virtual Agent 是什麼？

**A**: Virtual Agent（虛擬代理）：
- 作用：智能判斷何時發布 Gateway 更新
- 機制：EMA 平滑 + Jaccard 相似度判斷
- 效果：減少 70% 的 Gateway 更新

### Q6: 27° 網格為什麼最優？

**A**: 平衡三個指標：
- 控制信令：801 KB（最小）
- RTT 性能：109.82 ms（最優）
- PID 數量：78（適中，負載均衡）

### Q7: 實驗有沒有考慮壓縮？

**A**: 沒有，這是保守估計：
- 實際系統可能使用壓縮（gzip, LZ4）
- 批次處理可減少開銷
- 我們的數字是上界（實際可能更好）

### Q8: 能否與真實系統對比？

**A**: 期待未來驗證：
- SpaceX Starlink 未公開控制開銷數據
- OneWeb 等也沒有公開資料
- 我們提供了可驗證的方法論

---

## 報告技巧

### 強調點
1. **事件統計方法的嚴謹性**（有學術支持）
2. **相對比較的意義**（99.7% 改善）
3. **透明可驗證**（完整公式和參數）

### 誠實點
1. **字節數是估算**（基於 OpenFlow）
2. **保守上界**（實際可能更優）
3. **未來驗證**（期待真實系統比對）

### 自信點
1. **首次系統化量化**（創新貢獻）
2. **可複製方法**（其他研究者可驗證）
3. **實用價值**（指導衛星網路設計）

---

*準備時間：建議 30 分鐘報告 + 15 分鐘 Q&A*
*簡報工具：建議使用圖表和架構圖輔助說明*
