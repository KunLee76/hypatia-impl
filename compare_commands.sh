#!/bin/bash
# 比較三種演算法的執行指令

echo "============================================="
echo "三種演算法指令比較"
echo "============================================="
echo ""

cat << 'EOF'
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Floyd-Warshall Baseline (無分群)                                    │
└─────────────────────────────────────────────────────────────────────────┘
指令：
    python main_starlink_550.py \
        20 100 \
        isls_plus_grid \
        ground_stations_top_100 \
        algorithm_free_one_only_over_isls_with_stats \
        10

參數數量：6 個
特點：全域最短路徑，無階層化

┌─────────────────────────────────────────────────────────────────────────┐
│ 2. LoHi Baseline (6×10 平面區塊分群)                                   │
└─────────────────────────────────────────────────────────────────────────┘
指令：
    python main_starlink_550.py \
        20 100 \
        isls_plus_grid \
        ground_stations_top_100 \
        algorithm_lohi \
        10

參數數量：6 個
特點：固定 6×10 分群，強制管理跳點
注意：不需要 grid_deg 參數！

┌─────────────────────────────────────────────────────────────────────────┐
│ 3. GID (網格分群 - 你的演算法)                                         │
└─────────────────────────────────────────────────────────────────────────┘
指令：
    python main_starlink_550.py \
        20 100 \
        isls_plus_grid \
        ground_stations_top_100 \
        algorithm_hierarchical_virtual_gid_dijkstra \
        10 \
        21    ← 第 7 個參數：網格大小（度）

參數數量：7 個
特點：動態網格分群，可調整網格大小
注意：必須提供 grid_deg 參數！

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
參數對照表
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

位置  參數名稱          Floyd-Warshall    LoHi         GID
────────────────────────────────────────────────────────────────────────
 1    duration_s              20            20           20
 2    time_step_ms           100           100          100
 3    isl_config      isls_plus_grid  isls_plus_grid  isls_plus_grid
 4    gs_config       gs_top_100      gs_top_100      gs_top_100
 5    algorithm       ...free_one...  algorithm_lohi  ...gid_dijkstra
 6    num_threads            10            10           10
 7    grid_deg               -             -            21 ← 必須！
────────────────────────────────────────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
關鍵差異
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

特性            Floyd-Warshall          LoHi                GID
────────────────────────────────────────────────────────────────────────
分群方式        無分群                  6×10 平面區塊       網格（可調）
群大小          N/A                     固定 60 顆         動態變化
參數數量        6                       6                   7
grid_deg        不適用                  不需要              必須
管理跳點        無                      強制                無
統計檔案        *_free_one_*.json      lohi_*_p6_s10.json  *_21deg*.json
────────────────────────────────────────────────────────────────────────

EOF

echo ""
echo "============================================="
echo "快速參考"
echo "============================================="
echo ""
echo "你之前的指令："
echo "  python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_pid 10 21"
echo ""
echo "對應的新指令："
echo ""
echo "1. GID (更新後的名稱)："
echo "   python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_hierarchical_virtual_gid_dijkstra 10 21"
echo ""
echo "2. LoHi (新的 baseline)："
echo "   python main_starlink_550.py 20 100 isls_plus_grid ground_stations_top_100 algorithm_lohi 10"
echo "   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 注意：只有 6 個參數！"
echo ""
