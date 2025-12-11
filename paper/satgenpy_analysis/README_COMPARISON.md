# RTT Algorithm Comparison Tools

此目錄包含用於比較 LoHi 和 GRHR 演算法 RTT 性能的工具。

## 📊 工具列表

### 1. `compare_algorithms_rtt.py`
單一路徑的 RTT 比較腳本。

**功能**:
- 讀取 LoHi 和 GRHR 的 RTT 數據
- 繪製雙線比較圖（橘紅色 = LoHi，綠色 = GRHR）
- 顯示統計摘要（最小、最大、平均 RTT）
- 計算性能改善百分比

**使用方式**:
```bash
python compare_algorithms_rtt.py <data_dir> <constellation> <duration_s> <src_id> <dst_id>
```

**範例**:
```bash
# 比較 OneWeb 1200: Tokyo (720) → Delhi (721) 的 20 秒 RTT 數據
python compare_algorithms_rtt.py data oneweb_1200 20 720 721

# 比較 OneWeb 1200: Tokyo (720) → Shanghai (722) 的 20 秒 RTT 數據
python compare_algorithms_rtt.py data oneweb_1200 20 720 722

# 比較 Starlink 550 的數據
python compare_algorithms_rtt.py data starlink_550 20 720 721
```

**輸出**:
- PDF 圖檔: `data/algorithm_comparison/rtt_comparison_{src}_to_{dst}_{duration}s.pdf`
- 終端機顯示統計摘要

### 2. `batch_compare_rtt.sh`
批次生成多個比較圖的 Bash 腳本。

**功能**:
- 自動為多個目的地節點生成比較圖
- 預設配置: Tokyo (720) → [721, 722, 729]

**使用方式**:
```bash
./batch_compare_rtt.sh
```

**客製化**:
編輯 `batch_compare_rtt.sh` 中的參數：
```bash
DATA_DIR="paper/satgenpy_analysis/data"
CONSTELLATION="oneweb_1200"  # 指定星座: oneweb_1200, starlink_550, etc.
DURATION=20  # 修改模擬時長
SRC_NODE=720  # 修改來源節點 (Tokyo)
DEST_NODES=(721 722 729)  # 修改目的地節點列表 (Delhi, Shanghai, New York)
```

## 📈 圖表說明

### 顏色編碼
- **橘紅色線條** (orangered): LoHi 演算法
- **綠色線條** (green): GRHR 演算法

### 標記樣式
- **圓點** (○): LoHi 數據點
- **方塊** (□): GRHR 數據點
### 圖表元素
- **X 軸**: 時間（秒），刻度間隔 2 秒
- **Y 軸**: RTT（毫秒）
- **標題**: {constellation_name}: {src_name} → {dst_name}
  - 例如: "oneweb_1200: Tokyo → Delhi"
- **圖例**: 右上角或最佳位置
- **網格**: 淡灰色虛線 (alpha=0.3)佳位置
- **網格**: 淡灰色虛線

## 📁 檔案結構

```
paper/satgenpy_analysis/
├── compare_algorithms_rtt.py          # 單一比較腳本
├── batch_compare_rtt.sh               # 批次處理腳本
├── README_COMPARISON.md               # 本說明檔
└── data/
    ├── algorithm_comparison/          # 輸出目錄
    │   ├── rtt_comparison_720_to_721_20s.pdf
    │   ├── rtt_comparison_720_to_722_20s.pdf
    │   └── rtt_comparison_720_to_729_20s.pdf
    ├── oneweb_1200_..._algorithm_lohi/
    │   └── 100ms_for_20s/manual/data/
    │       └── networkx_rtt_720_to_*.txt  # LoHi 數據
    └── oneweb_1200_..._algorithm_hierarchical_virtual_gid_27deg/
        └── 100ms_for_20s/manual/data/
            └── networkx_rtt_720_to_*.txt  # GRHR 數據
```

## 📊 統計輸出範例

```
======================================================================
Statistics Summary:
======================================================================

LoHi:
  - Data points: 200
  - Min RTT: 69.74 ms
  - Max RTT: 74.84 ms
  - Avg RTT: 72.13 ms

GRHR:
  - Data points: 200
  - Min RTT: 52.47 ms
  - Max RTT: 56.33 ms
  - Avg RTT: 55.79 ms

Comparison:
  🎯 GRHR is 22.7% better than LoHi
======================================================================
```

## 🎯 實驗結果摘要（基於 OneWeb 1200，20秒模擬）

| 路徑 | LoHi 平均 RTT | GRHR 平均 RTT | 改善幅度 |
|------|---------------|---------------|----------|
| 720 → 721 | 72.13 ms | 55.79 ms | **22.7%** |
| 720 → 722 | 49.98 ms | 21.06 ms | **57.9%** |
| 720 → 729 | 134.40 ms | 112.15 ms | **16.6%** |

**結論**: GRHR 在所有測試路徑上都顯著優於 LoHi，改善幅度介於 16.6% 到 57.9% 之間。

## 🔧 依賴套件

```python
matplotlib  # 繪圖
```

確保已安裝：
```bash
pip install matplotlib
```

## 📝 注意事項

1. **數據路徑**: 腳本假設數據位於標準目錄結構中
2. **檔名格式**: `networkx_rtt_{src}_to_{dst}.txt`
3. **數據格式**: 每行格式為 `time_ns,rtt_ns`
4. **Unreachable 處理**: RTT = 0 視為 Unreachable，不計入統計
5. **輸出格式**: PDF (300 DPI，適合論文使用)
## 🚀 快速開始

```bash
# 1. 進入分析目錄
cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satgenpy_analysis

# 2. 單一比較 (明確指定星座)
python compare_algorithms_rtt.py data oneweb_1200 20 720 721

# 3. 批次處理 (需先編輯 batch_compare_rtt.sh 設定星座)
./batch_compare_rtt.sh

# 4. 查看結果
ls -lh data/algorithm_comparison/
```

## 🔧 地面站 ID 對應

**OneWeb 1200 星座**:
- 衛星 ID: 0-719 (共 720 顆，實際上是 1200 顆但這裡配置為 720)
- 地面站 ID: 720-820 (共 101 個)
- 對應關係: `node_id - 720 = ground_stations.txt 中的索引`

範例:
- Node 720 → ground_stations.txt 第 0 行 → Tokyo
- Node 721 → ground_stations.txt 第 1 行 → Delhi
- Node 729 → ground_stations.txt 第 9 行 → New York Newark-lh data/algorithm_comparison/
```

## 📧 問題回報

如有問題或建議，請聯繫開發者。
