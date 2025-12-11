#!/bin/bash
# Batch RTT Comparison Script
# 批次生成 LoHi vs GRHR 的 RTT 比較圖

# Configuration
DATA_DIR="paper/satgenpy_analysis/data"
CONSTELLATION="oneweb_1200"  # oneweb_1200, starlink_550, etc.
DURATION=20  # seconds
SRC_NODE=720  # Tokyo

# Destination nodes
DEST_NODES=(721 722 729)

echo "========================================================================"
echo "Batch RTT Comparison: LoHi vs GRHR"
echo "========================================================================"
echo "Constellation: ${CONSTELLATION}"
echo "Data directory: ${DATA_DIR}"
echo "Duration: ${DURATION}s"
echo "Source node: ${SRC_NODE} (Tokyo)"
echo "Destination nodes: ${DEST_NODES[@]}"
echo "========================================================================"
echo ""

# Change to project root
cd /home/kun/ssd2t/Leo/kun_hypatia

# Generate comparison for each destination
for DEST in "${DEST_NODES[@]}"; do
    echo "📊 Generating comparison: ${SRC_NODE} → ${DEST}..."
    python paper/satgenpy_analysis/compare_algorithms_rtt.py \
        ${DATA_DIR} ${CONSTELLATION} ${DURATION} ${SRC_NODE} ${DEST}
    echo ""
done

echo "========================================================================"
echo "✅ All comparisons completed!"
echo "========================================================================"
echo "Output directory: ${DATA_DIR}/algorithm_comparison/"
echo ""
echo "Generated files:"
for DEST in "${DEST_NODES[@]}"; do
    echo "  - rtt_comparison_${SRC_NODE}_to_${DEST}_${DURATION}s.pdf"
done
echo "========================================================================"
