# 隨機 ISL 失效實驗 - 快速開始

## 🎯 實驗目標

研究**全網隨機分布的 ISL 失效**對衛星網路控制信令的影響

- **3 種失效概率:** 1%, 5%, 10%
- **6 種 K 值:** 1, 2, 4, 6, 8, 999
- **總實驗數:** 18 個場景

## ✅ 已完成工作

### 1. 核心功能實現

| 文件 | 修改內容 | 狀態 |
|------|---------|------|
| `satgenpy/satgen/isls/generate_plus_grid_isls.py` | ✅ 新增 `generate_plus_grid_isls_with_random_failures()` | 完成 |
| `paper/satellite_networks_state/main_helper.py` | ✅ 添加 `isls_random_p*` 識別邏輯 | 完成 |
| `satgenpy/satgen/dynamic_state/algorithm_hierarchical_virtual_gid.py` | ✅ 添加 `random_p*` 場景識別 | 完成 |

### 2. 測試驗證

```bash
python test_random_isl_failures.py
```

**測試結果：**
- ✅ Starlink (53° 非極地) 隨機失效正常
- ✅ OneWeb (87.9° 極地) 隨機失效正常
- ✅ 隨機種子可重複性驗證通過
- ✅ 極端情況 (0%/100%) 測試通過

### 3. 實驗腳本

- ✅ `run_random_failure_scenarios_20s.sh` - 批量執行 18 個實驗
- ✅ `test_random_isl_failures.py` - 功能測試
- ✅ `RANDOM_ISL_FAILURE_EXPERIMENT_GUIDE.md` - 完整指南

## 🚀 執行步驟

### 步驟 1: 測試功能（可選）

```bash
python test_random_isl_failures.py
```

### 步驟 2: 執行實驗

```bash
./run_random_failure_scenarios_20s.sh
```

**配置：**
- 模擬時長: 20 秒
- 時間步長: 100 毫秒 (200 snapshots)
- 網格大小: 27°
- 隨機種子: 42 (固定)
- 預估時間: ~4.5 小時

### 步驟 3: 合併統計（待創建）

```bash
./merge_all_random_failure_scenarios.sh
```

### 步驟 4: 生成分析（待創建）

```bash
python analyze_random_failure_scenarios.py
```

## 📁 輸出結構

```
gen_data/
├── starlink_550_isls_random_p1_27deg_k1/
├── starlink_550_isls_random_p5_27deg_k1/
└── starlink_550_isls_random_p10_27deg_k1/
    ...

analytic_result/
├── temp_grhr_random_p1_k1/
│   └── grhr_stats_*.json
├── hierarchical_gid_27deg_random_p1_k1_signaling_stats.json
├── hierarchical_gid_27deg_random_p5_k1_signaling_stats.json
└── hierarchical_gid_27deg_random_p10_k1_signaling_stats.json

k_parameter_analysis/
├── k_comparison_random_p1.png
├── k_comparison_random_p5.png
└── k_comparison_random_p10.png
```

## 🔑 關鍵特性

### ✅ 獨立性
- ❌ **舊的 30 個局部失效實驗不需要重跑**
- ✅ 完全獨立的參數命名 (`isls_random_p*` vs `isls_failure_l*`)
- ✅ 獨立的輸出目錄
- ✅ 獨立的統計文件

### ✅ 可重複性
- ✅ 固定隨機種子 (`random_seed=42`)
- ✅ 相同參數重複執行結果完全一致
- ✅ 測試腳本已驗證

### ✅ 相容性
- ✅ Starlink (53° 非極地) - 自動使用 original 版本
- ✅ OneWeb (87.9° 極地) - 自動使用 polar 版本
- ✅ 自動偵測星座類型

## 📊 與局部失效的對比

| 項目 | 局部失效 | 隨機失效 |
|------|---------|---------|
| 場景數 | 30 (5×6) | 18 (3×6) |
| 失效模式 | 特定區域密集失效 (L1-L4) | 全網隨機分布 (1%, 5%, 10%) |
| 實現方式 | 預先生成文件 | 動態生成 |
| 目錄格式 | `isls_failure_l*` | `isls_random_p*` |
| 統計前綴 | `temp_grhr_failure_*` | `temp_grhr_random_*` |
| 狀態 | ✅ 已完成 (30/30) | ⏳ 待執行 (0/18) |

## ⚠️ 注意事項

1. **執行時間：** 18 個實驗約需 4.5 小時
2. **磁碟空間：** 總計約 10-20GB
3. **可中斷：** 每個實驗獨立，可中途重啟
4. **建議環境：** 在伺服器上執行

## 📖 詳細文檔

完整指南請參考：`RANDOM_ISL_FAILURE_EXPERIMENT_GUIDE.md`

---

**狀態：** ✅ 功能實現完成，已測試驗證，可開始執行實驗
