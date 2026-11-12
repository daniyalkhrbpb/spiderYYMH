#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
漫画采集器便捷操作脚本
提供数字选择菜单，方便用户进行各种操作
"""

import sys
import os
import subprocess
from pathlib import Path

def print_banner():
    """打印程序标题"""
    print("=" * 60)
    print("              漫画采集器 - 便捷操作界面")
    print("=" * 60)
    print()

def print_menu():
    """打印操作菜单"""
    print("请选择操作:")
    print("1. 添加新漫画")
    print("2. 更新指定漫画")
    print("3. 批量更新所有未完结漫画")
    print("4. 完整采集漫画（包含指定章节范围）")
    print("5. 漫画章节手动采集")
    print("6. 查看系统状态")
    print("7. 查看使用帮助")
    print("0. 退出程序")
    print("-" * 60)

def run_spider_command(command):
    """运行spider.py命令"""
    try:
        # 确保使用当前Python解释器
        python_cmd = sys.executable
        script_path = Path(__file__).parent / "spider.py"

        # 构建完整命令
        full_command = [python_cmd, str(script_path)] + command

        print(f"执行命令: {' '.join(full_command[2:])}")  # 只显示spider.py后面的部分
        print("-" * 60)

        # 执行命令
        result = subprocess.run(full_command, capture_output=False)

        print("-" * 60)
        if result.returncode == 0:
            print("✅ 操作执行成功")
        else:
            print("❌ 操作执行失败")

        return result.returncode == 0

    except Exception as e:
        print(f"❌ 执行命令时发生错误: {e}")
        return False

def add_manga():
    """添加新漫画"""
    print("=== 添加新漫画 ===")
    comic_id = input("请输入源站漫画ID: ").strip()

    if not comic_id:
        print("❌ 漫画ID不能为空")
        return False

    if not comic_id.isdigit():
        print("❌ 漫画ID必须是数字")
        return False

    return run_spider_command(["add", comic_id])

def update_specific_manga():
    """更新指定漫画"""
    print("=== 更新指定漫画 ===")
    db_manga_id = input("请输入本地数据库漫画ID: ").strip()

    if not db_manga_id:
        print("❌ 数据库漫画ID不能为空")
        return False

    if not db_manga_id.isdigit():
        print("❌ 数据库漫画ID必须是数字")
        return False

    return run_spider_command(["update", db_manga_id])

def update_all_manga():
    """批量更新所有未完结漫画"""
    print("=== 批量更新所有未完结漫画 ===")
    confirm = input("此操作将检测所有未完结漫画的更新，可能需要较长时间，是否继续？(Y/N): ").strip().lower()

    if confirm not in ['y', 'yes']:
        print("操作已取消")
        return False

    return run_spider_command(["update"])

def collect_manga():
    """完整采集漫画"""
    print("=== 完整采集漫画 ===")
    comic_id = input("请输入源站漫画ID: ").strip()

    if not comic_id:
        print("❌ 漫画ID不能为空")
        return False

    if not comic_id.isdigit():
        print("❌ 漫画ID必须是数字")
        return False

    # 询问起始章节
    start_chapter = input("请输入起始章节 (直接回车从第1章开始): ").strip()
    if start_chapter and not start_chapter.isdigit():
        print("❌ 起始章节必须是数字")
        return False

    # 询问数据库漫画ID
    db_manga_id = input("请输入本地数据库漫画ID (直接回车创建新漫画): ").strip()
    if db_manga_id and not db_manga_id.isdigit():
        print("❌ 数据库漫画ID必须是数字")
        return False

    # 构建命令
    command = ["collect", comic_id]

    if start_chapter:
        command.extend(["--start", start_chapter])

    if db_manga_id:
        command.extend(["--db-id", db_manga_id])

    return run_spider_command(command)


def force_collect_ui():
    """强制采集交互界面"""
    print("=== 漫画章节手工采集 ===")
    print("功能: 输入【源站章节ID】 。")
    print("适用: 修复漏章、错章、补采特定章节。")
    print("-" * 40)

    db_id = input("1. 请输入本地数据库漫画ID: ").strip()
    if not db_id.isdigit():
        print("❌ ID必须是数字")
        return False

    source_id = input("2. 请输入源站漫画ID : ").strip()
    if not source_id.isdigit():
        print("❌ 源站ID必须是数字")
        return False

    # 这里直接要求输入章节ID
    chapter_id = input("3. 请输入源站章节ID: ").strip()
    if not chapter_id.isdigit():
        print("❌ 章节ID必须是数字")
        return False

    # 构建命令
    command = ["force_collect", db_id, source_id, chapter_id]
    return run_spider_command(command)

def show_system_status():
    """查看系统状态"""
    print("=== 系统状态 ===")

    try:
        print("\n📊 当前环境配置:")
        # 当前环境配置
        from config import ENVIRONMENT_CONFIG
        mode_text = "下载" if ENVIRONMENT_CONFIG['is_download_image'] == 1 else "不下载"
        print(f"🔧 漫画图片下载: {mode_text}")
        print()

        # 检查数据库连接
        from database import Database
        db = Database()
        1
        print("📊 数据库统计:")

        # 查询漫画总数
        total_manga = db.execute_query("SELECT COUNT(*) as count FROM qiswl_manhua WHERE cjname = 'ttmh'")
        print(f"  总漫画数: {total_manga[0]['count']} 部")

        # 查询未完结漫画数
        unfinished_manga = db.execute_query("SELECT COUNT(*) as count FROM qiswl_manhua WHERE cjname = 'ttmh' AND mhstatus = 0")
        print(f"  未完结漫画: {unfinished_manga[0]['count']} 部")

        # 查询已完结漫画数
        finished_manga = db.execute_query("SELECT COUNT(*) as count FROM qiswl_manhua WHERE cjname = 'ttmh' AND mhstatus = 1")
        print(f"  已完结漫画: {finished_manga[0]['count']} 部")

        # 查询章节总数
        total_chapters = db.execute_query("SELECT COUNT(*) as count FROM qiswl_capter WHERE cjname = 'ttmh'")
        print(f"  总章节数: {total_chapters[0]['count']} 章")

        # 查询最近更新的漫画
        recent_manga = db.execute_query("""
            SELECT title, update_time FROM qiswl_manhua 
            WHERE cjname = 'ttmh' 
            ORDER BY update_time DESC 
            LIMIT 10
        """)

        print("\n📅 最近更新的漫画:")
        for manga in recent_manga:
            print(f"  {manga['title']} - {manga['update_time']}")

        db.close()

        print("\n💾 磁盘使用情况:")
        try:
            from config import IMAGE_CONFIG
            import shutil

            total, used, free = shutil.disk_usage(IMAGE_CONFIG['base_path'])
            print(f"  图片目录: {IMAGE_CONFIG['base_path']}")
            print(f"  总空间: {total // (1024**3)} GB")
            print(f"  已使用: {used // (1024**3)} GB")
            print(f"  剩余空间: {free // (1024**3)} GB")
        except Exception as e:
            print(f"  无法获取磁盘信息: {e}")

        return True

    except Exception as e:
        print(f"❌ 获取系统状态失败: {e}")
        return False

def show_help():
    """显示使用帮助"""
    print("=== 使用帮助 ===")
    print()
    print("🔧 命令行使用方式:")
    print("  python spider.py add 1811           # 添加源站漫画ID为1811的漫画")
    print("  python spider.py update 123        # 更新本地数据库ID为123的漫画")
    print("  python spider.py update            # 更新所有未完结的ttmh渠道漫画")
    print("  python spider.py collect 1811      # 完整采集漫画")
    print()
    print("📝 操作流程:")
    print("  1. 使用 '添加新漫画' 添加想要采集的漫画")
    print("  2. 使用 '更新指定漫画' 或 '批量更新' 获取最新章节")
    print("  3. 定期运行批量更新保持漫画最新")
    print()
    print("⚠️  注意事项:")
    print("  • 首次添加漫画只创建漫画记录，需要再次更新才能获取章节")
    print("  • 批量更新会检测所有未完结漫画，时间较长请耐心等待")
    print("  • 确保网络连接稳定，避免下载中断")
    print("  • 定期检查日志文件了解运行状态")
    print()
    print("📂 重要文件:")
    print("  • config.py - 配置文件，包含数据库和网站配置")
    print("  • spider.log - 日志文件，记录详细运行信息")
    print("  • requirements.txt - 依赖包列表")
    print()

def get_user_choice():
    """获取用户选择"""
    try:
        choice = input("请输入选项 (0-6): ").strip()
        return choice
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
        return "0"
    except EOFError:
        return "0"

def main():
    """主函数"""
    while True:
        print_banner()
        print_menu()

        choice = get_user_choice()
        print()

        if choice == "0":
            print("感谢使用，再见！")
            break
        elif choice == "1":
            add_manga()
        elif choice == "2":
            update_specific_manga()
        elif choice == "3":
            update_all_manga()
        elif choice == "4":
            collect_manga()
        elif choice == "5":
            force_collect_ui()
        elif choice == "6":
            show_system_status()
        elif choice == "7":
            show_help()
        else:
            print("❌ 无效选项，请输入 0-6 之间的数字")

        if choice != "0":
            print()
            input("按回车键继续...")
            print()

if __name__ == "__main__":
    main()