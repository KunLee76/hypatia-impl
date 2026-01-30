#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单的统计文件合并脚本 - 专门用于随机失效场景

直接合并temp_grhr_random_*目录下的所有grhr_stats_*.json文件
"""

import json
import glob
import os
import sys
from collections import defaultdict

def merge_stats_files(temp_dir, output_file):
    """合并指定目录下的所有统计文件"""
    
    # 查找所有统计文件
    pattern = os.path.join(temp_dir, "grhr_stats_pid*_tid*.json")
    files = glob.glob(pattern)
    
    if not files:
        print(f"  ✗ 未找到统计文件: {pattern}")
        return False
    
    print(f"  找到 {len(files)} 个统计文件")
    
    # 合并统计数据
    merged_data = {
        'routing_updates': 0,
        'gateway_updates': 0,
        'gid_rebuilds': 0,
        'topology_changes': 0,
        'total_messages': 0,
        'total_bytes': 0,
        'timeline': []
    }
    
    # 读取并合并所有文件
    for filepath in sorted(files):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # 检查数据格式：可能在summary字段里或顶层
            if 'summary' in data:
                # 新格式：数据在summary里
                summary = data['summary']
                merged_data['total_messages'] += summary.get('total_events', 0)
                merged_data['total_bytes'] += summary.get('total_bytes', 0)
                
                # 从by_type里提取各种事件计数
                by_type = summary.get('by_type', {})
                merged_data['routing_updates'] += by_type.get('routing_update', {}).get('count', 0)
                merged_data['gateway_updates'] += by_type.get('gateway_update', {}).get('count', 0)
                merged_data['gid_rebuilds'] += by_type.get('gid_rebuild', {}).get('count', 0)
                merged_data['topology_changes'] += by_type.get('topology_change', {}).get('count', 0)
            else:
                # 旧格式：数据在顶层
                merged_data['routing_updates'] += data.get('routing_updates', 0)
                merged_data['gateway_updates'] += data.get('gateway_updates', 0)
                merged_data['gid_rebuilds'] += data.get('gid_rebuilds', 0)
                merged_data['topology_changes'] += data.get('topology_changes', 0)
                merged_data['total_messages'] += data.get('total_messages', 0)
                merged_data['total_bytes'] += data.get('total_bytes', 0)
            
            # 合并timeline
            if 'timeline' in data:
                merged_data['timeline'].extend(data['timeline'])
            
        except Exception as e:
            print(f"  ⚠ 读取文件失败 {filepath}: {e}")
            continue
    
    # 按时间排序timeline
    if merged_data['timeline']:
        merged_data['timeline'].sort(key=lambda x: (x.get('snapshot', 0), x.get('sim_time_ms', 0)))
    
    # 去重：移除所有重复的事件
    # 问题：每个process都处理完整的时间范围（0到自己的max_snapshot），导致大量重复
    # 例如：Process 1处理0-20，Process 2处理0-40，...，导致snapshot 0-20被所有processes重复记录
    # 解决：使用(snapshot, event_type, time_ms, detail)作为唯一键，只保留第一次出现的事件
    if merged_data['timeline']:
        deduplicated_timeline = []
        seen_events = set()  # 记录已见过的事件
        
        original_count = len(merged_data['timeline'])
        duplicate_count = 0
        
        for event in merged_data['timeline']:
            # 创建事件的唯一标识
            snapshot = event.get('snapshot', 0)
            event_type = event.get('event', '')
            time_ms = event.get('time_ms', 0) or event.get('sim_time_ms', 0)
            
            # 对于detail，只取关键字段来识别唯一性
            detail = event.get('detail', {})
            detail_key = tuple(sorted((k, v) for k, v in detail.items() if isinstance(v, (int, str, float))))
            
            event_key = (snapshot, event_type, time_ms, detail_key)
            
            # 如果已经见过这个事件，跳过
            if event_key in seen_events:
                # 更新统计：减少重复计数
                if event_type == 'gid_rebuild':
                    merged_data['gid_rebuilds'] -= 1
                elif event_type == 'gateway_update':
                    merged_data['gateway_updates'] -= 1
                elif event_type == 'routing_update':
                    merged_data['routing_updates'] -= 1
                elif event_type == 'topology_change':
                    merged_data['topology_changes'] -= 1
                
                merged_data['total_messages'] -= 1
                duplicate_count += 1
                continue
            
            seen_events.add(event_key)
            deduplicated_timeline.append(event)
        
        merged_data['timeline'] = deduplicated_timeline
        print(f"  去重后timeline事件数: {len(deduplicated_timeline)} (原始: {original_count}, 移除重复: {duplicate_count})")
    
    # 写入输出文件
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(merged_data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ 合并完成: {output_file}")
        return True
        
    except Exception as e:
        print(f"  ✗ 写入失败: {e}")
        return False


def main():
    if len(sys.argv) != 3:
        print("用法: python merge_random_stats_simple.py <temp_dir> <output_file>")
        sys.exit(1)
    
    temp_dir = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(temp_dir):
        print(f"✗ 目录不存在: {temp_dir}")
        sys.exit(1)
    
    success = merge_stats_files(temp_dir, output_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
