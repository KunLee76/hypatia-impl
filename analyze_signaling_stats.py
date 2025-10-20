#!/usr/bin/env python3
"""
控制信令統計分析和可視化工具

這個模塊提供了分析Hypatia衛星路由算法控制信令開銷的工具。
主要功能：
1. 加載和比較不同算法的控制信令統計
2. 時間窗口分析
3. 可視化圖表生成
4. 性能報告生成

使用示例：
    python analyze_signaling_stats.py --algo1 hierarchical_pid --algo2 baseline
"""

import argparse
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 添加satgenpy路徑以導入算法模塊
sys.path.append('satgenpy')

def load_stats_from_csv(csv_content):
    """
    從CSV內容加載事件時間軸數據
    
    Args:
        csv_content: CSV格式的字符串內容
    
    Returns:
        pandas.DataFrame: 包含事件數據的DataFrame
    """
    import io
    df = pd.read_csv(io.StringIO(csv_content))
    
    # 轉換時間為datetime對象（假設time_ms是相對於某個起始時間的偏移）
    df['timestamp'] = pd.to_datetime(df['time_ms'], unit='ms')
    
    return df

def load_algorithm_stats(algo_name, stats_dir="test_log_output"):
    """
    加載特定算法的統計數據
    
    Args:
        algo_name: 算法名稱
        stats_dir: 統計數據目錄
    
    Returns:
        dict: 包含統計數據的字典，格式：
            {
                "summary": {...},  # 摘要統計
                "timeline": DataFrame  # 時間軸數據
            }
    """
    stats_path = Path(stats_dir) / f"{algo_name}_signaling_stats.txt"
    
    if not stats_path.exists():
        raise FileNotFoundError(f"找不到統計文件: {stats_path}")
    
    with open(stats_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析文件內容
    lines = content.split('\n')
    
    # 找到CSV時間軸部分
    csv_start = None
    for i, line in enumerate(lines):
        if line.strip() == "=== 事件時間軸 ===":
            csv_start = i + 1
            break
    
    if csv_start is None:
        raise ValueError("統計文件格式錯誤：找不到事件時間軸部分")
    
    # 提取CSV數據
    csv_content = '\n'.join(lines[csv_start:])
    timeline_df = load_stats_from_csv(csv_content)
    
    # 解析摘要部分（簡單版本，可以根據需要擴展）
    summary = {"loaded_from": str(stats_path)}
    
    return {
        "summary": summary,
        "timeline": timeline_df
    }

def analyze_time_window(df, start_time=None, end_time=None, window_size_ms=None):
    """
    分析特定時間窗口的統計數據
    
    Args:
        df: 事件DataFrame
        start_time: 開始時間（datetime或毫秒）
        end_time: 結束時間（datetime或毫秒）
        window_size_ms: 窗口大小（毫秒），如果指定則忽略end_time
    
    Returns:
        dict: 時間窗口分析結果
    """
    if df.empty:
        return {"total_events": 0, "total_bytes": 0, "by_type": {}}
    
    # 過濾時間窗口
    filtered_df = df.copy()
    
    if start_time is not None:
        if isinstance(start_time, (int, float)):
            start_time = pd.to_datetime(start_time, unit='ms')
        filtered_df = filtered_df[filtered_df['timestamp'] >= start_time]
    
    if end_time is not None:
        if isinstance(end_time, (int, float)):
            end_time = pd.to_datetime(end_time, unit='ms')
        filtered_df = filtered_df[filtered_df['timestamp'] <= end_time]
    elif window_size_ms is not None and start_time is not None:
        if isinstance(start_time, (int, float)):
            end_time = pd.to_datetime(start_time + window_size_ms, unit='ms')
        else:
            end_time = start_time + timedelta(milliseconds=window_size_ms)
        filtered_df = filtered_df[filtered_df['timestamp'] <= end_time]
    
    # 計算統計
    total_events = len(filtered_df)
    total_bytes = filtered_df['bytes'].sum()
    
    # 按類型統計
    by_type = {}
    for event_type in filtered_df['event_type'].unique():
        type_df = filtered_df[filtered_df['event_type'] == event_type]
        by_type[event_type] = {
            "count": len(type_df),
            "bytes": type_df['bytes'].sum(),
            "avg_bytes_per_event": type_df['bytes'].mean() if len(type_df) > 0 else 0
        }
    
    return {
        "total_events": total_events,
        "total_bytes": total_bytes,
        "by_type": by_type,
        "time_window": {
            "start": start_time,
            "end": end_time,
            "filtered_records": len(filtered_df)
        }
    }

def plot_signaling_overhead(stats_dict, output_path=None, time_window_ms=1000):
    """
    繪製控制信令開銷隨時間變化的圖表
    
    Args:
        stats_dict: 算法統計數據字典 {algo_name: stats_data}
        output_path: 輸出圖片路徑
        time_window_ms: 時間窗口大小（毫秒）
    """
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('控制信令開銷分析', fontsize=16)
    
    # 設置中文字體（如果可用）
    try:
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
    except:
        pass
    
    algo_names = list(stats_dict.keys())
    colors = ['blue', 'red', 'green', 'orange'][:len(algo_names)]
    
    # 子圖1: 累積字節數
    ax1 = axes[0, 0]
    for i, (algo_name, stats) in enumerate(stats_dict.items()):
        df = stats['timeline']
        if not df.empty:
            # 計算累積字節數
            df_sorted = df.sort_values('time_ms')
            cumulative_bytes = df_sorted['bytes'].cumsum()
            ax1.plot(df_sorted['time_ms']/1000, cumulative_bytes, 
                    label=algo_name, color=colors[i], linewidth=2)
    
    ax1.set_title('累積控制信令字節數')
    ax1.set_xlabel('時間 (秒)')
    ax1.set_ylabel('累積字節數')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 子圖2: 每種事件類型的總數
    ax2 = axes[0, 1]
    event_types = set()
    for stats in stats_dict.values():
        if not stats['timeline'].empty:
            event_types.update(stats['timeline']['event_type'].unique())
    
    event_types = sorted(list(event_types))
    x_pos = range(len(event_types))
    width = 0.8 / len(algo_names)
    
    for i, (algo_name, stats) in enumerate(stats_dict.items()):
        df = stats['timeline']
        counts = []
        for event_type in event_types:
            count = len(df[df['event_type'] == event_type]) if not df.empty else 0
            counts.append(count)
        
        x_positions = [x + i * width for x in x_pos]
        ax2.bar(x_positions, counts, width, label=algo_name, color=colors[i], alpha=0.7)
    
    ax2.set_title('各類型事件總數')
    ax2.set_xlabel('事件類型')
    ax2.set_ylabel('事件數量')
    ax2.set_xticks([x + width * (len(algo_names) - 1) / 2 for x in x_pos])
    ax2.set_xticklabels(event_types, rotation=45)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 子圖3: 時間窗口內的平均開銷
    ax3 = axes[1, 0]
    window_stats = {}
    
    for algo_name, stats in stats_dict.items():
        df = stats['timeline']
        if df.empty:
            continue
            
        # 計算滑動窗口統計
        min_time = df['time_ms'].min()
        max_time = df['time_ms'].max()
        
        windows = []
        window_bytes = []
        
        current_time = min_time
        while current_time < max_time:
            window_end = current_time + time_window_ms
            window_df = df[(df['time_ms'] >= current_time) & (df['time_ms'] < window_end)]
            
            if not window_df.empty:
                windows.append(current_time / 1000)  # 轉換為秒
                window_bytes.append(window_df['bytes'].sum())
            
            current_time += time_window_ms // 2  # 50% 重疊
        
        if windows:
            ax3.plot(windows, window_bytes, label=algo_name, 
                    color=colors[list(stats_dict.keys()).index(algo_name)], 
                    marker='o', markersize=3)
    
    ax3.set_title(f'滑動窗口控制開銷 ({time_window_ms}ms窗口)')
    ax3.set_xlabel('時間 (秒)')
    ax3.set_ylabel('窗口內字節數')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 子圖4: 算法比較摘要
    ax4 = axes[1, 1]
    ax4.axis('off')  # 隱藏軸
    
    summary_text = "算法性能比較摘要:\n\n"
    for algo_name, stats in stats_dict.items():
        df = stats['timeline']
        if not df.empty:
            total_events = len(df)
            total_bytes = df['bytes'].sum()
            avg_bytes_per_event = total_bytes / total_events if total_events > 0 else 0
            
            summary_text += f"{algo_name}:\n"
            summary_text += f"  總事件: {total_events}\n"
            summary_text += f"  總字節: {total_bytes:,}\n"
            summary_text += f"  平均/事件: {avg_bytes_per_event:.1f} bytes\n\n"
        else:
            summary_text += f"{algo_name}: 無數據\n\n"
    
    ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes, 
             verticalalignment='top', fontsize=10, fontfamily='monospace')
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"圖表已保存到: {output_path}")
    
    plt.show()

def compare_algorithms(algo1_stats, algo2_stats, output_path=None):
    """
    詳細比較兩個算法的控制信令開銷
    
    Args:
        algo1_stats: 算法1的統計數據
        algo2_stats: 算法2的統計數據  
        output_path: 報告輸出路徑
    """
    df1 = algo1_stats['timeline']
    df2 = algo2_stats['timeline']
    
    comparison = {
        "algorithm_1": {
            "total_events": len(df1) if not df1.empty else 0,
            "total_bytes": df1['bytes'].sum() if not df1.empty else 0,
            "event_types": {}
        },
        "algorithm_2": {
            "total_events": len(df2) if not df2.empty else 0,
            "total_bytes": df2['bytes'].sum() if not df2.empty else 0,
            "event_types": {}
        }
    }
    
    # 按事件類型分析
    all_event_types = set()
    if not df1.empty:
        all_event_types.update(df1['event_type'].unique())
    if not df2.empty:
        all_event_types.update(df2['event_type'].unique())
    
    for event_type in all_event_types:
        # 算法1
        df1_type = df1[df1['event_type'] == event_type] if not df1.empty else pd.DataFrame()
        count1 = len(df1_type)
        bytes1 = df1_type['bytes'].sum() if not df1_type.empty else 0
        
        # 算法2
        df2_type = df2[df2['event_type'] == event_type] if not df2.empty else pd.DataFrame()
        count2 = len(df2_type)
        bytes2 = df2_type['bytes'].sum() if not df2_type.empty else 0
        
        comparison["algorithm_1"]["event_types"][event_type] = {
            "count": count1, "bytes": bytes1
        }
        comparison["algorithm_2"]["event_types"][event_type] = {
            "count": count2, "bytes": bytes2
        }
    
    # 計算差異
    total_bytes_diff = comparison["algorithm_2"]["total_bytes"] - comparison["algorithm_1"]["total_bytes"]
    total_events_diff = comparison["algorithm_2"]["total_events"] - comparison["algorithm_1"]["total_events"]
    
    comparison["differences"] = {
        "total_bytes_diff": total_bytes_diff,
        "total_events_diff": total_events_diff,
        "bytes_percentage": (total_bytes_diff / comparison["algorithm_1"]["total_bytes"] * 100) if comparison["algorithm_1"]["total_bytes"] > 0 else float('inf')
    }
    
    # 生成報告
    report = f"""
控制信令算法比較報告
=====================

算法1統計:
  總事件數: {comparison['algorithm_1']['total_events']:,}
  總字節數: {comparison['algorithm_1']['total_bytes']:,}

算法2統計:
  總事件數: {comparison['algorithm_2']['total_events']:,}
  總字節數: {comparison['algorithm_2']['total_bytes']:,}

差異分析:
  字節差異: {total_bytes_diff:,} ({comparison['differences']['bytes_percentage']:.2f}%)
  事件差異: {total_events_diff:,}

按事件類型分析:
"""
    
    for event_type in sorted(all_event_types):
        stats1 = comparison["algorithm_1"]["event_types"][event_type]
        stats2 = comparison["algorithm_2"]["event_types"][event_type]
        bytes_diff = stats2["bytes"] - stats1["bytes"]
        count_diff = stats2["count"] - stats1["count"]
        
        report += f"""
  {event_type}:
    算法1: {stats1['count']} 事件, {stats1['bytes']} 字節
    算法2: {stats2['count']} 事件, {stats2['bytes']} 字節
    差異: {count_diff:+} 事件, {bytes_diff:+} 字節
"""
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"比較報告已保存到: {output_path}")
    else:
        print(report)
    
    return comparison

def main():
    parser = argparse.ArgumentParser(description='分析控制信令統計數據')
    parser.add_argument('--algo1', required=True, help='第一個算法名稱')
    parser.add_argument('--algo2', help='第二個算法名稱（用於比較）')
    parser.add_argument('--stats-dir', default='test_log_output', help='統計數據目錄')
    parser.add_argument('--plot', action='store_true', help='生成可視化圖表')
    parser.add_argument('--output', help='輸出文件路徑前綴')
    parser.add_argument('--time-window', type=int, default=1000, help='時間窗口大小（毫秒）')
    
    args = parser.parse_args()
    
    try:
        # 加載算法1數據
        algo1_stats = load_algorithm_stats(args.algo1, args.stats_dir)
        print(f"成功加載 {args.algo1} 的統計數據")
        
        stats_dict = {args.algo1: algo1_stats}
        
        # 如果指定了第二個算法，加載並比較
        if args.algo2:
            algo2_stats = load_algorithm_stats(args.algo2, args.stats_dir)
            print(f"成功加載 {args.algo2} 的統計數據")
            stats_dict[args.algo2] = algo2_stats
            
            # 生成比較報告
            compare_output = f"{args.output}_comparison.txt" if args.output else None
            compare_algorithms(algo1_stats, algo2_stats, compare_output)
        
        # 生成可視化圖表
        if args.plot:
            plot_output = f"{args.output}_plot.png" if args.output else None
            plot_signaling_overhead(stats_dict, plot_output, args.time_window)
        
        print("分析完成!")
        
    except Exception as e:
        print(f"錯誤: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()