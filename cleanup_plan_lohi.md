# algorithm_lohi.py 清理計畫

## 🎯 目標
1. 移除未使用的函數
2. 整合重複的 import 到檔案最頂端
3. 移除函數內部的 import
4. 保持程式碼整潔且易於維護

## 📋 需要清理的項目

### 1. 未使用的函數 (共 5 個)

| 函數名稱 | 行數範圍 | 說明 | 動作 |
|---------|---------|------|------|
| `_dijkstra_in_pid` | ? | 舊版的 PID 內部 Dijkstra | ❌ 刪除 |
| `_first_step` | 1041 | 未使用的路由函數 | ❌ 刪除 |
| `_build_intra_group_tree` | ? | 舊版的群內樹狀結構 | ❌ 刪除 |
| `_geo_greedy_next_hop` | ? | 地理貪婪路由（未使用） | ❌ 刪除 |
| `_noop_log` | ? | 空的 log 函數 | ❌ 刪除 |

### 2. 重複的 import

| Import 語句 | 出現次數 | 位置 | 動作 |
|------------|---------|------|------|
| `import math` | 2 次 | 行 26, 1681 | ✅ 保留頂端，刪除 1681 |
| `import networkx as nx` | 2 次 | 行 30, 1569 | ✅ 保留頂端，刪除 1569 |
| `import random` | 1 次 | 行 671 (函數內) | ✅ 移到頂端 |

### 3. 函數內部的 import

| 位置 | Import | 動作 |
|-----|--------|------|
| 行 671 | `import random` | ✅ 移到檔案頂端 |
| 行 1569 | `import networkx as nx` | ❌ 刪除（頂端已有）|
| 行 1681 | `import math` | ❌ 刪除（頂端已有）|

## 📝 清理步驟

### Step 1: 統一 imports 到頂端
```python
# 現有的 (行 24-31)
from dataclasses import dataclass
from typing import Dict, Set, Tuple, List, Optional, Callable, Any
import math
import os
import json
import datetime as _dt
import networkx as nx
import heapq

# 新增
import random  # 從行 671 移上來
```

### Step 2: 刪除重複的 imports
- 刪除行 671: `import random`
- 刪除行 1569: `import networkx as nx`
- 刪除行 1681: `import math`

### Step 3: 刪除未使用的函數
需要先找到確切行數，然後刪除：
1. `_dijkstra_in_pid`
2. `_first_step` (行 1041 附近)
3. `_build_intra_group_tree`
4. `_geo_greedy_next_hop`
5. `_noop_log`

## ✅ 預期結果

### 清理前
- 總行數: 1734
- Import 語句: 分散在多處
- 未使用函數: 5 個

### 清理後
- 總行數: ~1600-1650 (減少約 80-130 行)
- Import 語句: 統一在頂端 (行 24-32)
- 未使用函數: 0 個
- 程式碼: 更整潔、易維護

## 🔍 驗證方法

1. **語法檢查**:
   ```bash
   python -m py_compile satgenpy/satgen/dynamic_state/algorithm_lohi.py
   ```

2. **Import 檢查**:
   ```bash
   grep -n "^import\|^from.*import\|    import\|    from.*import" algorithm_lohi.py
   ```

3. **功能測試**:
   ```bash
   # 重新執行 LoHi 測試，確保結果不變
   conda run -n kun_hypatia python main_starlink_550.py 1 100 \
     isls_plus_grid ground_stations_top_100 algorithm_lohi 1
   ```

4. **比較輸出**:
   - Loops 應該還是 0%
   - 路由邏輯不變
   - 執行時間相近

