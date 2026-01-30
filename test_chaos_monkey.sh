#!/bin/bash

# Chaos Monkey 测试脚本
# 测试场景: Random P1 (1% failure rate), K=1, 20秒模拟
# 目的: 验证间歇性ISL失效机制是否正常工作

set -e

# 激活conda环境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate kun_hypatia

echo "=========================================="
echo "Chaos Monkey 测试"
echo "=========================================="
echo "场景: Random P1 K1 (1% ISL failure rate)"
echo "时长: 20秒"
echo "时间步长: 100ms"
echo "失效间隔: 2秒 (20 snapshots)"
echo "=========================================="
echo ""

# 设置环境变量
export ENABLE_CHAOS_MONKEY=true
export CHAOS_FAILURE_RATE=0.01  # 1% for P1
export CHAOS_INTERVAL_SNAPSHOTS=20  # 每2秒 (20个snapshots @ 100ms)
export K_BEST_GATEWAYS=1  # K=1
export SATGEN_GRID_DEG=27  # Grid degree
export CHAOS_LOG_FILE="../../logs/chaos_monkey_test_p1_k1.log"  # 相对于paper/satellite_networks_state

echo "环境变量设置:"
echo "  ENABLE_CHAOS_MONKEY = $ENABLE_CHAOS_MONKEY"
echo "  CHAOS_FAILURE_RATE = $CHAOS_FAILURE_RATE (1%)"
echo "  CHAOS_INTERVAL_SNAPSHOTS = $CHAOS_INTERVAL_SNAPSHOTS (2 seconds)"
echo "  K_BEST_GATEWAYS = $K_BEST_GATEWAYS"
echo "  SATGEN_GRID_DEG = $SATGEN_GRID_DEG"
echo "  CHAOS_LOG_FILE = $CHAOS_LOG_FILE"
echo ""

# 创建日志目录
mkdir -p logs

# 清理旧的日志文件
if [ -f "$CHAOS_LOG_FILE" ]; then
    rm "$CHAOS_LOG_FILE"
    echo "已清理旧的Chaos Monkey日志"
fi

# 切换到正确的目录
cd paper/satellite_networks_state

echo "开始运行测试..."
echo ""

# 运行模拟
# 参数: duration(s) time_step(ms) isls gs_stations algorithm num_threads grid_deg k_best
python main_oneweb_1200.py \
    20 \
    100 \
    isls_plus_grid \
    ground_stations_top_100 \
    algorithm_hierarchical_virtual_gid \
    4 \
    27 \
    1

echo ""
echo "=========================================="
echo "测试完成！"
echo "=========================================="
echo ""

# 返回根目录
cd ../..

# 检查Chaos Monkey日志（使用绝对路径）
LOG_FILE_CHECK="logs/chaos_monkey_test_p1_k1.log"
if [ -f "$LOG_FILE_CHECK" ]; then
    echo "Chaos Monkey日志文件已生成: $LOG_FILE_CHECK"
    echo ""
    echo "日志统计:"
    
    # 统计注入次数（使用正确的日志格式）
    injection_count=$(grep -c "CHAOS_MONKEY.*Snapshot=" "$LOG_FILE_CHECK" || echo "0")
    echo "  • ISL失效注入次数: $injection_count"
    
    # 统计总共移除的ISL数量
    total_removed=$(grep "ISL removed:" "$LOG_FILE_CHECK" | wc -l || echo "0")
    echo "  • 总共移除的ISL数: $total_removed"
    
    # 计算预期注入次数 (20秒 / 2秒间隔 = 10次)
    expected_injections=10
    echo "  • 预期注入次数: $expected_injections"
    
    echo ""
    echo "最近3次注入的详细信息:"
    grep "CHAOS_MONKEY.*Snapshot=" "$LOG_FILE_CHECK" | tail -3
    
    echo ""
    echo "=========================================="
    echo "验证要点:"
    echo "=========================================="
    echo "1. 注入次数应该约为 $expected_injections 次 (实际: $injection_count)"
    echo "2. 每次注入应该移除不同的ISL (检查日志中的ISL ID)"
    echo "3. 每次应该移除约 1% 的ISL (约14条)"
    echo "4. 控制信令统计应该显示更多的GID rebuilds和路由更新"
    echo ""
    
    if [ "$injection_count" -ge 8 ]; then
        echo "✅ Chaos Monkey工作正常！注入次数在预期范围内"
    else
        echo "⚠️  警告：注入次数少于预期，请检查实现"
    fi
else
    echo "❌ 错误：Chaos Monkey日志文件未生成"
    echo "   可能原因："
    echo "   1. ENABLE_CHAOS_MONKEY 环境变量未正确设置"
    echo "   2. 算法代码中的Chaos Monkey未被调用"
    echo "   3. 日志路径错误"
    echo ""
    echo "   尝试的日志路径: $LOG_FILE_CHECK"
fi

echo ""
echo "完整日志路径: logs/chaos_monkey_test_p1_k1.log"
echo "生成数据目录: paper/satellite_networks_state/gen_data/"
