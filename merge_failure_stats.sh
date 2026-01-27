#!/bin/bash

# 合併失效場景控制信令統計
# 為每個 K 值 × 失效場景生成統一的 JSON 文件

cd /home/kun/ssd2t/Leo/kun_hypatia/paper/satellite_networks_state

echo "======================================================"
echo "合併失效場景控制信令統計"
echo "======================================================"
echo ""

# K 值列表
K_VALUES=(1 2 4 6 8 999)

# 失效場景列表（不包含 baseline，因為已經有了）
SCENARIOS=("l1" "l2" "l3" "l4")

TOTAL=$((${#K_VALUES[@]} * ${#SCENARIOS[@]}))
CURRENT=0

echo "需要處理 ${TOTAL} 個場景"
echo ""

for K in "${K_VALUES[@]}"; do
    for SCENARIO in "${SCENARIOS[@]}"; do
        CURRENT=$((CURRENT + 1))
        
        # 構造目錄名稱
        DIR_NAME="starlink_550_isls_failure_${SCENARIO}_ground_stations_top_100_with_hsinchu_algorithm_hierarchical_virtual_gid_27deg_k${K}"
        INPUT_DIR="gen_data/${DIR_NAME}/dynamic_state_100ms_for_100s"
        
        # 輸出文件名
        OUTPUT_FILE="analytic_result/hierarchical_gid_27deg_failure_${SCENARIO}_k${K}_signaling_stats.json"
        
        # 檢查目錄是否存在
        if [ ! -d "${INPUT_DIR}" ]; then
            echo "✗ [$CURRENT/$TOTAL] 目錄不存在: ${DIR_NAME}"
            continue
        fi
        
        echo "[$CURRENT/$TOTAL] 處理: ${SCENARIO}, K=${K}"
        
        # 使用 Python 腳本合併統計數據
        python3 ../merge_signaling_stats.py \
            --input-dir "${INPUT_DIR}" \
            --output-file "${OUTPUT_FILE}" \
            --algorithm "algorithm_hierarchical_virtual_gid" \
            --display-name "Hierarchical Virtual GID (Failure ${SCENARIO}, K=${K})" \
            --grid-deg 27 \
            --k-best ${K} \
            --quiet
        
        if [ $? -eq 0 ]; then
            echo "  ✓ 已保存: ${OUTPUT_FILE}"
        else
            echo "  ✗ 失敗: ${OUTPUT_FILE}"
        fi
        
        echo ""
    done
done

echo "======================================================"
echo "合併完成！"
echo "生成的統計文件在: analytic_result/"
echo "======================================================"
