#!/bin/bash
################################################################################
# 自動化網格尺寸實驗腳本
# 用途：測試不同網格大小對 hierarchical 演算法的影響
################################################################################

set -e  # 遇到錯誤立即停止

# ============================================================================
# 實驗參數設定
# ============================================================================

# 網格尺寸範圍（從 15° 到 30°，可以根據需要調整）
GRID_SIZES=(15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30)

# 演算法列表
ALGORITHMS=(
    "algorithm_hierarchical_virtual_pid"
    "algorithm_hierarchical_virtual_pid_dijkstra"
)

# 模擬參數
DURATION_S=20          # 模擬時長（秒）
TIME_STEP_MS=100        # 時間步長（毫秒）
ISL_TYPE="isls_plus_grid"
GROUND_STATIONS="ground_stations_top_100"
NUM_THREADS=10           # 執行緒數量（可根據 CPU 核心數調整）

# ============================================================================
# 顏色輸出設定
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# 日誌函數
# ============================================================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================================
# 計算總任務數
# ============================================================================
TOTAL_TASKS=$((${#GRID_SIZES[@]} * ${#ALGORITHMS[@]}))
CURRENT_TASK=0

# ============================================================================
# 記錄開始時間
# ============================================================================
START_TIME=$(date +%s)
log_info "實驗開始於: $(date)"
log_info "總任務數: ${TOTAL_TASKS} (${#GRID_SIZES[@]} 個網格尺寸 × ${#ALGORITHMS[@]} 個演算法)"
echo ""

# ============================================================================
# 主要執行迴圈
# ============================================================================
for grid in "${GRID_SIZES[@]}"; do
    echo "=========================================================================="
    echo "  網格尺寸: ${grid}°×${grid}°"
    echo "  PID 數量: 約 $((360/grid)) × $((180/grid)) = $(((360/grid) * (180/grid))) 個"
    echo "=========================================================================="
    
    for algo in "${ALGORITHMS[@]}"; do
        CURRENT_TASK=$((CURRENT_TASK + 1))
        
        # 計算進度
        PROGRESS=$((CURRENT_TASK * 100 / TOTAL_TASKS))
        
        log_info "[${CURRENT_TASK}/${TOTAL_TASKS}] (${PROGRESS}%) 執行演算法: ${algo} | Grid: ${grid}°"
        
        # 記錄任務開始時間
        TASK_START=$(date +%s)
        
        # 執行模擬（序列執行，不用 & 背景執行）
        if python main_starlink_550.py \
            ${DURATION_S} \
            ${TIME_STEP_MS} \
            ${ISL_TYPE} \
            ${GROUND_STATIONS} \
            ${algo} \
            ${NUM_THREADS} \
            ${grid}; then
            
            # 計算任務執行時間
            TASK_END=$(date +%s)
            TASK_DURATION=$((TASK_END - TASK_START))
            TASK_MIN=$((TASK_DURATION / 60))
            TASK_SEC=$((TASK_DURATION % 60))
            
            log_success "完成 ${algo} (Grid: ${grid}°) - 耗時: ${TASK_MIN}m ${TASK_SEC}s"
            
            # 估算剩餘時間
            ELAPSED=$((TASK_END - START_TIME))
            AVG_TIME=$((ELAPSED / CURRENT_TASK))
            REMAINING_TASKS=$((TOTAL_TASKS - CURRENT_TASK))
            ETA=$((AVG_TIME * REMAINING_TASKS))
            ETA_MIN=$((ETA / 60))
            ETA_SEC=$((ETA % 60))
            
            log_info "預計剩餘時間: ${ETA_MIN}m ${ETA_SEC}s"
            
        else
            log_error "任務失敗: ${algo} (Grid: ${grid}°)"
            log_warning "繼續執行下一個任務..."
        fi
        
        echo ""
    done
    
    echo ""
done

# ============================================================================
# 實驗完成統計
# ============================================================================
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
TOTAL_HOURS=$((TOTAL_DURATION / 3600))
TOTAL_MIN=$(((TOTAL_DURATION % 3600) / 60))
TOTAL_SEC=$((TOTAL_DURATION % 60))

echo "=========================================================================="
log_success "所有實驗完成！"
echo "=========================================================================="
echo "  開始時間: $(date -d @${START_TIME})"
echo "  結束時間: $(date -d @${END_TIME})"
echo "  總耗時:   ${TOTAL_HOURS}h ${TOTAL_MIN}m ${TOTAL_SEC}s"
echo "  完成任務: ${TOTAL_TASKS} 個"
echo "=========================================================================="

# ============================================================================
# 列出生成的目錄
# ============================================================================
log_info "生成的資料目錄:"
echo ""
ls -lh gen_data/ | grep hierarchical | grep deg

echo ""
log_info "實驗結果已保存在 gen_data/ 目錄中"
log_info "你可以使用 hypatia_multi_algorithm_analyzer.py 進行分析"
