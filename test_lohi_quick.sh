#!/bin/bash
# LoHi 演算法快速啟動指南

echo "======================================"
echo "LoHi Algorithm Quick Start"
echo "======================================"

# 1. 運行單元測試
echo -e "\n[1] Running unit tests..."
python3 test_algorithm_lohi.py
if [ $? -eq 0 ]; then
    echo "✓ Unit tests passed"
else
    echo "✗ Unit tests failed"
    exit 1
fi

# 2. 驗證統計輸出
echo -e "\n[2] Testing statistics output..."
python3 test_lohi_stats.py
if [ $? -eq 0 ]; then
    echo "✓ Statistics tests passed"
else
    echo "✗ Statistics tests failed"
    exit 1
fi

# 3. 驗證語法
echo -e "\n[3] Checking Python syntax..."
python3 -m py_compile satgenpy/satgen/dynamic_state/algorithm_lohi.py
python3 -m py_compile satgenpy/satgen/dynamic_state/generate_dynamic_state.py
if [ $? -eq 0 ]; then
    echo "✓ Syntax check passed"
else
    echo "✗ Syntax check failed"
    exit 1
fi

echo -e "\n======================================"
echo "✓ All checks passed!"
echo "======================================"

echo -e "\nNext steps:"
echo "  1. Generate dynamic state:"
echo "     cd paper/satellite_networks_state"
echo "     # 修改 generate script 使用 algorithm=algorithm_lohi"
echo ""
echo "  2. Run simulation:"
echo "     cd ../../ns3-sat-sim"
echo "     # 執行模擬實驗"
echo ""
echo "  3. Analyze results:"
echo "     cd ../paper/satgenpy_analysis"
echo "     # 比較三種演算法性能"
echo ""
echo "Environment variables (optional):"
echo "  export LOHI_BETA_Q=1.0              # Queue weight"
echo "  export LOHI_BETA_S=0.0              # Static offset"
echo "  export LOHI_ENFORCE_MGMT_HOP=1      # Force management hop"
echo "  export LOHI_TG_MODE=constant        # Group-level cost model"
echo "  export LOHI_TG_CONST_NG=10          # Estimated DATA objects"
echo "  export LOHI_TG_CONST_LAVG=1500      # Avg object size (bytes)"
echo "  export LOHI_LINK_BW_BPS=1000000000  # 1 Gbps"
echo "  export LOHI_TG_SCALE=1.0            # Scaling factor"
