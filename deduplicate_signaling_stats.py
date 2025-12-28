#!/usr/bin/env python3
"""
控制信令統計數據去重工具

問題根因：平行處理時多個worker在相同snapshot記錄到全域_SIGNALING_STATS物件，造成重複

解決方案：
1. 根據 (snapshot, time_ms, event) 去重 timeline events
2. 保留第一次出現的事件（通常數據較完整）
3. 重新計算 summary 統計
4. 備份原始檔案
"""

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def deduplicate_timeline(timeline):
    """
    去重 timeline events
    
    唯一鍵: (snapshot, time_ms, event)
    策略: 保留第一次出現的事件
    
    Returns:
        deduplicated_timeline: 去重後的事件列表
        removed_count: 被移除的重複事件數
    """
    seen = set()
    deduplicated = []
    removed = 0
    
    for event in timeline:
        # 建立唯一鍵
        key = (event['snapshot'], event['time_ms'], event['event'])
        
        if key not in seen:
            seen.add(key)
            deduplicated.append(event)
        else:
            removed += 1
            # 記錄重複的事件以供檢查
            # print(f"[DUPLICATE] Removed: snapshot={event['snapshot']}, "
            #       f"time_ms={event['time_ms']}, event={event['event']}")
    
    return deduplicated, removed


def recalculate_summary(timeline):
    """
    根據去重後的 timeline 重新計算 summary
    
    Returns:
        summary: 更新後的統計摘要
    """
    by_type = defaultdict(lambda: {'count': 0, 'bytes': 0})
    total_bytes = 0
    total_count = 0
    
    for event in timeline:
        event_type = event['event']
        count = event.get('count', 1)
        event_bytes = event.get('bytes', 0)
        
        by_type[event_type]['count'] += count
        by_type[event_type]['bytes'] += event_bytes
        total_bytes += event_bytes
        total_count += count
    
    return {
        'total_events': total_count,
        'total_bytes': total_bytes,
        'by_type': dict(by_type)
    }


def deduplicate_json_file(input_path, output_path=None, create_backup=True):
    """
    去重單一 JSON 統計檔案
    
    Args:
        input_path: 輸入檔案路徑
        output_path: 輸出檔案路徑（若為None則覆寫原檔案）
        create_backup: 是否建立備份檔案
    
    Returns:
        dict: 去重統計資訊
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"找不到檔案: {input_path}")
    
    # 讀取原始數據
    print(f"\n📖 讀取檔案: {input_path.name}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 備份原始檔案
    if create_backup:
        backup_path = input_path.parent / f"{input_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        print(f"💾 建立備份: {backup_path.name}")
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    # 原始統計
    original_timeline = data.get('timeline', [])
    original_summary = data.get('summary', {})
    
    print(f"📊 原始數據:")
    print(f"   Timeline events: {len(original_timeline)}")
    print(f"   Summary total_events: {original_summary.get('total_events', 'N/A')}")
    print(f"   Summary by_type: {original_summary.get('by_type', {})}")
    
    # 去重 timeline
    deduplicated_timeline, removed_count = deduplicate_timeline(original_timeline)
    
    # 重新計算 summary
    new_summary = recalculate_summary(deduplicated_timeline)
    
    # 保留原始 summary 中的其他欄位
    for key in original_summary:
        if key not in ['total_events', 'total_bytes', 'by_type']:
            new_summary[key] = original_summary[key]
    
    # 更新數據
    data['timeline'] = deduplicated_timeline
    data['summary'] = new_summary
    
    # 添加去重記錄
    data['deduplication_info'] = {
        'timestamp': datetime.now().isoformat(),
        'original_timeline_length': len(original_timeline),
        'deduplicated_timeline_length': len(deduplicated_timeline),
        'removed_duplicates': removed_count,
        'original_summary': original_summary
    }
    
    # 寫入檔案
    if output_path is None:
        output_path = input_path
    else:
        output_path = Path(output_path)
    
    print(f"\n✨ 去重結果:")
    print(f"   Timeline events: {len(original_timeline)} → {len(deduplicated_timeline)}")
    print(f"   移除重複: {removed_count} 筆")
    print(f"   Summary total_events: {original_summary.get('total_events', 'N/A')} → {new_summary['total_events']}")
    
    # 檢查 by_type 變化
    print(f"\n📋 各事件類型變化:")
    all_event_types = set(original_summary.get('by_type', {}).keys()) | set(new_summary['by_type'].keys())
    for event_type in sorted(all_event_types):
        old_count = original_summary.get('by_type', {}).get(event_type, {}).get('count', 0)
        new_count = new_summary['by_type'].get(event_type, {}).get('count', 0)
        if old_count != new_count:
            print(f"   {event_type}: {old_count} → {new_count} (-{old_count - new_count})")
    
    print(f"\n💾 寫入檔案: {output_path.name}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return {
        'input_path': str(input_path),
        'output_path': str(output_path),
        'backup_path': str(backup_path) if create_backup else None,
        'original_events': len(original_timeline),
        'deduplicated_events': len(deduplicated_timeline),
        'removed_duplicates': removed_count
    }


def deduplicate_all_in_directory(directory, pattern='*_signaling_stats*.json', create_backup=True):
    """
    去重目錄中所有符合pattern的JSON檔案
    
    Args:
        directory: 目錄路徑
        pattern: 檔案匹配模式
        create_backup: 是否建立備份
    
    Returns:
        list: 所有檔案的去重結果
    """
    directory = Path(directory)
    
    if not directory.exists():
        raise FileNotFoundError(f"找不到目錄: {directory}")
    
    json_files = list(directory.glob(pattern))
    
    if not json_files:
        print(f"⚠️  在 {directory} 中找不到符合 '{pattern}' 的檔案")
        return []
    
    print(f"\n🔍 找到 {len(json_files)} 個檔案:")
    for f in json_files:
        print(f"   - {f.name}")
    
    results = []
    
    for json_file in json_files:
        try:
            result = deduplicate_json_file(json_file, create_backup=create_backup)
            results.append(result)
        except Exception as e:
            print(f"\n❌ 處理 {json_file.name} 時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
    
    return results


def main():
    """主程式"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='控制信令統計數據去重工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 去重單一檔案
  python deduplicate_signaling_stats.py -f hierarchical_gid_27deg_signaling_stats.json
  
  # 去重整個目錄的所有統計檔案
  python deduplicate_signaling_stats.py -d paper/satellite_networks_state/analytic_result
  
  # 不建立備份檔案（危險！）
  python deduplicate_signaling_stats.py -d analytic_result --no-backup
        """
    )
    
    parser.add_argument('-f', '--file', type=str, help='單一檔案路徑')
    parser.add_argument('-d', '--directory', type=str, help='目錄路徑（處理所有符合pattern的檔案）')
    parser.add_argument('-p', '--pattern', type=str, default='*_signaling_stats*.json',
                        help='檔案匹配模式（預設: *_signaling_stats*.json）')
    parser.add_argument('--no-backup', action='store_true', help='不建立備份檔案')
    
    args = parser.parse_args()
    
    create_backup = not args.no_backup
    
    print("="*70)
    print("控制信令統計數據去重工具")
    print("="*70)
    
    if args.file:
        # 處理單一檔案
        result = deduplicate_json_file(args.file, create_backup=create_backup)
        print("\n✅ 去重完成!")
        
    elif args.directory:
        # 處理整個目錄
        results = deduplicate_all_in_directory(args.directory, args.pattern, create_backup)
        
        if results:
            print("\n"+"="*70)
            print("📊 總結")
            print("="*70)
            total_removed = sum(r['removed_duplicates'] for r in results)
            print(f"處理檔案數: {len(results)}")
            print(f"總共移除重複: {total_removed} 筆")
            print("\n✅ 所有檔案去重完成!")
    else:
        parser.print_help()
        print("\n⚠️  請指定 -f (單一檔案) 或 -d (目錄)")


if __name__ == '__main__':
    main()
