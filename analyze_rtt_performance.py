#!/usr/bin/env python3
"""
RTT 性能分析腳本
分析不同網格大小、不同算法的 RTT 表現
找出最佳配置
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple
import statistics

# 配置
DATA_DIR = Path("paper/satgenpy_analysis/data")
OUTPUT_DIR = Path("paper/satgenpy_analysis/rtt_analysis_results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 城市對應
CITY_NAMES = {
    1584: "Tokyo",
    1585: "Delhi",
    1586: "Shanghai",
    1593: "New_York"
}

def parse_rtt_file(file_path: Path) -> Dict:
    """
    解析 RTT 文件
    返回統計數據：平均、最小、最大、標準差
    """
    if not file_path.exists():
        return None
    
    rtt_values = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                time_ns, rtt_ns = line.split(',')
                rtt_ms = float(rtt_ns) / 1e6  # 轉換為毫秒
                rtt_values.append(rtt_ms)
            except ValueError:
                continue
    
    if not rtt_values:
        return None
    
    return {
        "count": len(rtt_values),
        "mean": statistics.mean(rtt_values),
        "median": statistics.median(rtt_values),
        "min": min(rtt_values),
        "max": max(rtt_values),
        "stdev": statistics.stdev(rtt_values) if len(rtt_values) > 1 else 0,
        "variance": statistics.variance(rtt_values) if len(rtt_values) > 1 else 0,
        "raw_values": rtt_values
    }

def extract_info_from_path(dir_path: Path) -> Tuple[str, int, str]:
    """
    從目錄名稱提取算法類型和網格大小
    返回: (algorithm_type, grid_deg, full_name)
    """
    dir_name = dir_path.name
    
    # 判斷算法類型
    if 'algorithm_lohi' in dir_name:
        # LoHi 不使用網格
        return 'LoHi', None, dir_name
    elif 'free_one_only_over_isls' in dir_name:
        # Baseline 不使用網格
        return 'Baseline', None, dir_name
    
    # 提取網格大小（GID/Dijkstra 才有）
    match = re.search(r'_(\d+)deg$', dir_name)
    if not match:
        return None, None, dir_name
    
    grid_deg = int(match.group(1))
    
    # 判斷是 GID 還是 Dijkstra
    if 'dijkstra' in dir_name:
        algo_type = 'Dijkstra'
    elif 'hierarchical_virtual_gid' in dir_name or 'hierarchical_virtual_pid' in dir_name:
        algo_type = 'GID'
    else:
        algo_type = 'Unknown'
    
    return algo_type, grid_deg, dir_name

def scan_all_results() -> Dict:
    """
    掃描所有結果目錄
    返回結構化的數據
    """
    results = {
        'Baseline': {},
        'GID': {},
        'LoHi': {}
    }
    
    if not DATA_DIR.exists():
        print(f"❌ 數據目錄不存在: {DATA_DIR}")
        return results
    
    # 掃描所有子目錄
    for subdir in sorted(DATA_DIR.iterdir()):
        if not subdir.is_dir():
            continue
        
        algo_type, grid_deg, dir_name = extract_info_from_path(subdir)
        if algo_type is None:
            continue
        
        # 檢查是否有 RTT 數據
        rtt_data_dir = subdir / "100ms_for_20s" / "manual" / "data"
        if not rtt_data_dir.exists():
            continue
        
        # 讀取所有 RTT 文件
        rtt_files = list(rtt_data_dir.glob("networkx_rtt_*.txt"))
        if not rtt_files:
            continue
        
        # 解析每個 RTT 文件
        route_stats = {}
        for rtt_file in rtt_files:
            # 提取 src 和 dst
            match = re.search(r'networkx_rtt_(\d+)_to_(\d+)\.txt', rtt_file.name)
            if not match:
                continue
            
            src, dst = int(match.group(1)), int(match.group(2))
            src_name = CITY_NAMES.get(src, str(src))
            dst_name = CITY_NAMES.get(dst, str(dst))
            route_name = f"{src_name}_to_{dst_name}"
            
            stats = parse_rtt_file(rtt_file)
            if stats:
                route_stats[route_name] = stats
        
        if route_stats:
            if algo_type in ['Baseline', 'LoHi']:
                # Baseline 和 LoHi 沒有網格大小
                results[algo_type]['default'] = {
                    'dir_name': dir_name,
                    'routes': route_stats
                }
            elif algo_type == 'GID' and grid_deg == 27:
                # 只保留 GID 27°
                results[algo_type][grid_deg] = {
                    'dir_name': dir_name,
                    'routes': route_stats
                }
    
    return results

def generate_summary_report(results: Dict) -> str:
    """
    生成摘要報告
    """
    lines = []
    lines.append("=" * 80)
    lines.append("RTT 性能分析報告")
    lines.append("=" * 80)
    lines.append("")
    
    # 統計數據
    total_configs = 0
    for algo_type, configs in results.items():
        total_configs += len(configs)
    
    lines.append(f"分析的配置數量: {total_configs}")
    lines.append(f"  - Baseline: {len(results.get('Baseline', {}))}")
    lines.append(f"  - GID (27°): {len(results.get('GID', {}))}")
    lines.append(f"  - LoHi: {len(results.get('LoHi', {}))}")
    lines.append("")
    
    return "\n".join(lines)

def generate_detailed_report(results: Dict) -> str:
    """
    生成詳細報告
    """
    lines = []
    
    # 按路由對分組
    route_names = set()
    for algo_type, configs in results.items():
        for config_key, config_data in configs.items():
            if isinstance(config_data, dict) and 'routes' in config_data:
                route_names.update(config_data['routes'].keys())
    
    route_names = sorted(route_names)
    
    for route_name in route_names:
        lines.append("=" * 80)
        lines.append(f"路由: {route_name}")
        lines.append("=" * 80)
        lines.append("")
        
        # 收集該路由的所有數據
        route_data = []
        
        # Baseline
        if 'default' in results.get('Baseline', {}):
            baseline_routes = results['Baseline']['default'].get('routes', {})
            if route_name in baseline_routes:
                stats = baseline_routes[route_name]
                route_data.append(('Baseline', None, stats))
        
        # LoHi
        if 'default' in results.get('LoHi', {}):
            lohi_routes = results['LoHi']['default'].get('routes', {})
            if route_name in lohi_routes:
                stats = lohi_routes[route_name]
                route_data.append(('LoHi', None, stats))
        
        # GID
        for grid_deg in sorted([k for k in results.get('GID', {}).keys() if isinstance(k, int)]):
            gid_routes = results['GID'][grid_deg].get('routes', {})
            if route_name in gid_routes:
                stats = gid_routes[route_name]
                route_data.append(('GID', grid_deg, stats))
        
        if not route_data:
            lines.append("  (無數據)")
            lines.append("")
            continue
        
        # 表頭
        lines.append(f"{'算法':<20} {'網格':<8} {'平均RTT':>12} {'中位數':>12} {'最小值':>12} {'最大值':>12} {'標準差':>12}")
        lines.append("-" * 92)
        
        # 找出最佳配置
        best_mean = min(route_data, key=lambda x: x[2]['mean'])
        best_median = min(route_data, key=lambda x: x[2]['median'])
        best_min = min(route_data, key=lambda x: x[2]['min'])
        
        # 數據行
        for algo, grid, stats in route_data:
            grid_str = f"{grid}°" if grid else "N/A"
            
            # 標記最佳值
            mean_marker = " ★" if (algo, grid) == (best_mean[0], best_mean[1]) else ""
            median_marker = " ★" if (algo, grid) == (best_median[0], best_median[1]) else ""
            min_marker = " ★" if (algo, grid) == (best_min[0], best_min[1]) else ""
            
            lines.append(
                f"{algo:<20} {grid_str:<8} "
                f"{stats['mean']:>11.2f}{mean_marker:<2} "
                f"{stats['median']:>11.2f}{median_marker:<2} "
                f"{stats['min']:>11.2f}{min_marker:<2} "
                f"{stats['max']:>12.2f} "
                f"{stats['stdev']:>12.2f}"
            )
        
        lines.append("")
        lines.append(f"最佳平均RTT: {best_mean[0]} {best_mean[1]}° - {best_mean[2]['mean']:.2f} ms")
        lines.append(f"最佳中位數RTT: {best_median[0]} {best_median[1]}° - {best_median[2]['median']:.2f} ms")
        lines.append(f"最佳最小RTT: {best_min[0]} {best_min[1]}° - {best_min[2]['min']:.2f} ms")
        lines.append("")
    
    return "\n".join(lines)

def generate_ranking_report(results: Dict) -> str:
    """
    生成排名報告
    """
    lines = []
    lines.append("=" * 80)
    lines.append("整體排名 (按平均 RTT)")
    lines.append("=" * 80)
    lines.append("")
    
    # 收集所有配置的平均 RTT
    all_configs = []
    
    # Baseline
    if 'default' in results.get('Baseline', {}):
        baseline_routes = results['Baseline']['default'].get('routes', {})
        if baseline_routes:
            avg_rtt = statistics.mean([s['mean'] for s in baseline_routes.values()])
            all_configs.append(('Baseline', None, avg_rtt, len(baseline_routes)))
    
    # LoHi
    if 'default' in results.get('LoHi', {}):
        lohi_routes = results['LoHi']['default'].get('routes', {})
        if lohi_routes:
            avg_rtt = statistics.mean([s['mean'] for s in lohi_routes.values()])
            all_configs.append(('LoHi', None, avg_rtt, len(lohi_routes)))
    
    # GID
    for grid_deg in sorted([k for k in results.get('GID', {}).keys() if isinstance(k, int)]):
        gid_routes = results['GID'][grid_deg].get('routes', {})
        if gid_routes:
            avg_rtt = statistics.mean([s['mean'] for s in gid_routes.values()])
            all_configs.append(('GID', grid_deg, avg_rtt, len(gid_routes)))
    
    # 按平均 RTT 排序
    all_configs.sort(key=lambda x: x[2])
    
    # 輸出排名
    lines.append(f"{'排名':<6} {'算法':<20} {'網格':<8} {'平均RTT':>12} {'路由數':>8}")
    lines.append("-" * 60)
    
    for rank, (algo, grid, avg_rtt, route_count) in enumerate(all_configs, 1):
        grid_str = f"{grid}°" if grid else "N/A"
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else ""
        lines.append(f"{rank:<6} {algo:<20} {grid_str:<8} {avg_rtt:>12.2f} {route_count:>8} {medal}")
    
    lines.append("")
    
    # 最佳配置
    if all_configs:
        best = all_configs[0]
        lines.append("🏆 最佳整體配置:")
        lines.append(f"   算法: {best[0]}")
        lines.append(f"   網格大小: {best[1]}°" if best[1] else "   網格大小: N/A")
        lines.append(f"   平均RTT: {best[2]:.2f} ms")
        lines.append("")
    
    return "\n".join(lines)

def save_json_results(results: Dict, output_file: Path):
    """
    保存 JSON 格式的原始數據（不包含 raw_values）
    """
    # 清理數據（移除 raw_values 以減小文件大小）
    clean_results = {}
    for algo_type, configs in results.items():
        clean_results[algo_type] = {}
        for config_key, config_data in configs.items():
            if isinstance(config_data, dict) and 'routes' in config_data:
                clean_routes = {}
                for route_name, stats in config_data['routes'].items():
                    clean_stats = {k: v for k, v in stats.items() if k != 'raw_values'}
                    clean_routes[route_name] = clean_stats
                clean_results[algo_type][str(config_key)] = {
                    'dir_name': config_data['dir_name'],
                    'routes': clean_routes
                }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(clean_results, f, indent=2, ensure_ascii=False)
    
    print(f"✅ JSON 數據已保存: {output_file}")

def main():
    print("=" * 80)
    print("RTT 性能分析工具")
    print("=" * 80)
    print()
    
    # 掃描所有結果
    print("🔍 掃描數據目錄...")
    results = scan_all_results()
    
    if not any(results.values()):
        print("❌ 未找到任何 RTT 數據")
        return
    
    print(f"✅ 找到數據:")
    print(f"   - Baseline: {len(results.get('Baseline', {}))}")
    print(f"   - GID (27°): {len(results.get('GID', {}))}")
    print(f"   - LoHi: {len(results.get('LoHi', {}))}")
    print()
    
    # 生成報告
    print("📊 生成分析報告...")
    
    # 摘要報告
    summary = generate_summary_report(results)
    summary_file = OUTPUT_DIR / "rtt_summary.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary)
    print(f"✅ 摘要報告: {summary_file}")
    
    # 詳細報告
    detailed = generate_detailed_report(results)
    detailed_file = OUTPUT_DIR / "rtt_detailed_analysis.txt"
    with open(detailed_file, 'w', encoding='utf-8') as f:
        f.write(detailed)
    print(f"✅ 詳細報告: {detailed_file}")
    
    # 排名報告
    ranking = generate_ranking_report(results)
    ranking_file = OUTPUT_DIR / "rtt_ranking.txt"
    with open(ranking_file, 'w', encoding='utf-8') as f:
        f.write(ranking)
    print(f"✅ 排名報告: {ranking_file}")
    
    # 完整報告
    full_report = summary + "\n\n" + ranking + "\n\n" + detailed
    full_report_file = OUTPUT_DIR / "rtt_full_report.txt"
    with open(full_report_file, 'w', encoding='utf-8') as f:
        f.write(full_report)
    print(f"✅ 完整報告: {full_report_file}")
    
    # JSON 數據
    json_file = OUTPUT_DIR / "rtt_analysis_data.json"
    save_json_results(results, json_file)
    
    print()
    print("=" * 80)
    print("🎉 分析完成！")
    print("=" * 80)
    print()
    print("查看報告:")
    print(f"  cat {full_report_file}")
    print()
    print("或直接查看排名:")
    print(f"  cat {ranking_file}")

if __name__ == "__main__":
    main()
