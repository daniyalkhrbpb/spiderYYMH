#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
漫画采集器主程序 - 支持简化命令行参数
"""

import sys
import logging
import argparse
from pathlib import Path
from logging.handlers import RotatingFileHandler

from config import LOG_CONFIG, DATABASE_CONFIG, SITE_CONFIG
from database import Database
from processor import MangaProcessor
from spider_core import SpiderCore


# (setup_logging, ensure_working_domain, add_manga, update_manga 函数保持不变)
def setup_logging():
    """设置日志配置"""
    log_format = logging.Formatter(LOG_CONFIG['format'])
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_CONFIG['level']))
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    try:
        file_handler = RotatingFileHandler(
            LOG_CONFIG['file'], maxBytes=LOG_CONFIG['max_size'],
            backupCount=LOG_CONFIG['backup_count'], encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"无法创建日志文件: {e}")


def ensure_working_domain():
    """确保使用可用的网站域名 - 统一入口点"""
    print('正在检查可用的网站域名...')
    try:
        spider = SpiderCore()
        working_domain = spider.get_working_domain()
        SITE_CONFIG['base_url'] = working_domain
        SITE_CONFIG['referer'] = working_domain + '/'
        print(f'将使用域名: {working_domain}')
        return working_domain
    except Exception as e:
        print(f'域名检测失败: {e}')
        logging.error(f'域名检测失败: {e}')
        print(f'将使用默认域名: {SITE_CONFIG["base_url"]}')
        return SITE_CONFIG['base_url']


def add_manga(comic_id: str):
    """添加新漫画"""
    print(f"=== 添加漫画 (源站ID: {comic_id}) ===")
    ensure_working_domain()
    processor = None
    try:
        processor = MangaProcessor()
        manga_object = processor.create_new_manga(comic_id)
        if manga_object:
            print(f"✅ 操作成功完成: {manga_object.title} (数据库ID: {manga_object.db_id})")
            print(f"提示: 漫画已入库但暂无章节内容，请运行更新命令获取章节:")
            print(f"python spider.py update {manga_object.db_id}")
            return True
        else:
            print("❌ 添加漫画失败")
            return False
    except Exception as e:
        print(f"❌ 添加漫画时发生错误: {e}")
        logging.error(f"添加漫画失败: {e}")
        return False
    finally:
        if processor:
            processor.close()


def update_manga(db_manga_id: str = None):
    """更新漫画"""
    if db_manga_id:
        print(f"=== 更新指定漫画 (数据库ID: {db_manga_id}) ===")
    else:
        print("=== 批量更新所有未完结漫画 ===")
    ensure_working_domain()
    processor = None
    try:
        processor = MangaProcessor()
        if db_manga_id:
            manga_info = processor.db.get_manga_by_id(int(db_manga_id))
            if not manga_info:
                print(f"❌ 找不到数据库ID为 {db_manga_id} 的漫画")
                return False

            print(f"开始更新漫画: {manga_info['title']}")
            is_updated = processor.process_single_manga_update(manga_info)
            if is_updated:
                print(f"✅ 漫画 {manga_info['title']} 更新完成")
            else:
                print(f"ℹ️ 漫画 {manga_info['title']} 没有新内容或仅元数据更新")
            return True
        else:
            result = processor.process_manga_updates()
            print(f"\n=== 更新结果 ===")
            print(f"总计检测: {result['total']} 部漫画")
            print(f"有更新: {result['updated']} 部漫画")
            print(f"发生错误: {result['error']} 部漫画")
            if result['total'] > 0:
                success_rate = (result['total'] - result['error']) / result['total'] * 100
                print(f"成功率: {success_rate:.1f}%")
            return result['error'] == 0
    except Exception as e:
        print(f"❌ 更新漫画时发生错误: {e}")
        logging.error(f"更新漫画失败: {e}")
        return False
    finally:
        if processor:
            processor.close()


def collect_manga(comic_id: str, start_chapter: int = 0, db_manga_id: int = None):
    """采集漫画（完整功能，适配新架构）"""
    print(f"=== 采集漫画 (源站ID: {comic_id}) ===")
    ensure_working_domain()
    processor = None
    try:
        processor = MangaProcessor()
        # 调用processor中新的完整采集方法
        success = processor.process_full_collection(comic_id, start_chapter, db_manga_id)

        if success:
            print("✅ 漫画采集完成")
            return True
        else:
            print("❌ 漫画采集失败")
            return False
    except Exception as e:
        print(f"❌ 采集漫画时发生错误: {e}")
        logging.error(f"采集漫画失败: {e}")
        return False
    finally:
        if processor:
            processor.close()


def force_collect_manga(db_manga_id: int, comic_id: str, chapter_spec: str):
    """强行采集指定章节（人工干预模式）"""
    print(f"=== 手工采集漫画 (数据库本地ID: {db_manga_id}, 源站漫画ID: {comic_id}, 源站章节ID: {chapter_spec}) ===")
    ensure_working_domain()
    processor = None
    try:
        processor = MangaProcessor()
        # 调用processor中新的强制采集方法
        success = processor.process_force_collection(db_manga_id, comic_id, chapter_spec)

        if success:
            print("✅ 漫画手工采集操作完成")
            return True
        else:
            print("❌ 漫画手工采集操作中止或失败")
            return False
    except Exception as e:
        print(f"❌ 漫画手工采集时发生错误: {e}")
        logging.error(f"漫画手工采集失败: {e}")
        return False
    finally:
        if processor:
            processor.close()


def main():
    """主函数"""
    setup_logging()

    parser = argparse.ArgumentParser(
        description='漫画采集器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python spider.py add 1811           # 添加源站漫画ID为1811的漫画
  python spider.py update 123        # 更新本地数据库ID为123的漫画  
  python spider.py update            # 更新所有未完结的ttmh渠道漫画
  python spider.py collect 1300      # 完整采集漫画(源站ID为1300)
  python spider.py collect 1300 --start 5 --db-id 123  # 从第5章开始采集到指定数据库漫画
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    add_parser = subparsers.add_parser('add', help='添加新漫画')
    add_parser.add_argument('comic_id', help='源站漫画ID')

    update_parser = subparsers.add_parser('update', help='更新漫画')
    update_parser.add_argument('db_manga_id', nargs='?', help='本地数据库漫画ID（可选，不提供则更新所有）')

    collect_parser = subparsers.add_parser('collect', help='完整采集漫画')
    collect_parser.add_argument('comic_id', help='源站漫画ID')
    collect_parser.add_argument('--start', type=int, default=0, help='起始章节号（从1开始）')
    collect_parser.add_argument('--db-id', type=int, help='本地数据库漫画ID（可选，不提供则创建新漫画）')

    force_parser = subparsers.add_parser('force_collect', help='强行采集指定章节')
    force_parser.add_argument('db_manga_id', type=int, help='本地数据库漫画ID')
    force_parser.add_argument('comic_id', help='源站漫画ID')
    force_parser.add_argument('chapter_id', help='源站章节ID')

    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()

    try:
        if args.command == 'add':
            sys.exit(0 if add_manga(args.comic_id) else 1)
        elif args.command == 'update':
            sys.exit(0 if update_manga(args.db_manga_id) else 1)
        elif args.command == 'collect':
            sys.exit(0 if collect_manga(args.comic_id, args.start, args.db_id) else 1)
        elif args.command == 'force_collect':
            sys.exit(0 if force_collect_manga(args.db_manga_id, args.comic_id, args.chapter_id) else 1)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
        sys.exit(1)


if __name__ == '__main__':
    main()