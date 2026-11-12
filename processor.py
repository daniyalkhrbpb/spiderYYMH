# processor.py
# -*- coding: utf-8 -*-
"""
处理器模块(服务层) - 负责核心业务逻辑的编排
"""

import logging
from typing import Dict, List, Optional
from database import Database
from spider_core import SpiderCore
from downloader import ImageDownloader
from models import Manga, Chapter

logger = logging.getLogger(__name__)


class MangaProcessor:
    def __init__(self):
        self.db = Database()
        self.spider = SpiderCore()
        self.downloader = ImageDownloader(self.spider.base_url)

    def _get_or_create_ticai_id(self, ticai_name: str) -> Optional[int]:
        """根据题材名称获取或创建题材ID"""
        if not ticai_name: return None
        logger.info(f"处理漫画题材: '{ticai_name}'")
        try:
            ticai_db = self.db.get_ticai_by_name(ticai_name)
            if ticai_db:
                return ticai_db.get('id')
            else:
                logger.info(f"题材 '{ticai_name}' 不存在，正在创建...")
                return self.db.insert_ticai(ticai_name)
        except Exception as e:
            logger.error(f"处理题材 '{ticai_name}' 失败: {e}")
            return None

    def _sync_nondestructive_metadata(self, local_manga: Manga, source_manga: Manga) -> bool:
        """只同步无害的元数据（如题材），并返回一个布尔值表示是否有变更。"""
        has_changed = False
        if not local_manga.ticai_id and source_manga.ticai_name:
            logger.info(f"漫画 '{local_manga.title}' 本地题材为空，尝试从源站更新...")
            new_ticai_id = self._get_or_create_ticai_id(source_manga.ticai_name)
            if new_ticai_id:
                local_manga.ticai_id = new_ticai_id
                has_changed = True

        if not local_manga.author and source_manga.author:
            logger.info(f"漫画 '{local_manga.title}' 作者为空，尝试从源站更新...")
            local_manga.author = source_manga.author
            has_changed = True
        if (not local_manga.tags or local_manga.tags == ['']) and source_manga.tags:
            logger.info(f"漫画 '{local_manga.title}' 标签为空，尝试从源站更新...")
            local_manga.tags = source_manga.tags
            has_changed = True

        return has_changed

    def process_single_manga_update(self, manga_in_db: Dict) -> bool:
        """处理单个漫画的更新检测"""
        cjid = manga_in_db['cjid']
        title = manga_in_db['title']
        logger.info(f"开始更新漫画: {manga_in_db['title']} (采集ID: {cjid})")

        try:
            source_manga = self.spider.get_manga_info(cjid)
            if not source_manga: return False

            local_manga = self.db.get_manga_by_cjid(cjid)
            if not local_manga:
                logger.error(f"严重错误：在更新时找不到数据库中的漫画记录 (采集ID: {cjid})")
                return False

            metadata_changed = self._sync_nondestructive_metadata(local_manga, source_manga)

            existing_orders = self.db.get_manga_chapter_orders(local_manga.db_id)
            new_chapters = [ch for ch in source_manga.chapters if ch.order not in existing_orders]
            has_new_chapters = len(new_chapters) > 0

            if has_new_chapters:
                logger.info(f"漫画 '{local_manga.title}' 发现 {len(new_chapters)} 个新章节，开始处理...")
                for chapter in sorted(new_chapters, key=lambda c: c.order):
                    self._process_new_chapter(local_manga, cjid, chapter)

                if source_manga.cover_url:
                    manga_url = f"{self.spider.base_url}/100/comic/{cjid}"
                    # logger.info(f"正在更新漫画 '{title}' 的封面图...")
                    abs_cover_path = self.downloader.download_single_image(
                        source_manga.cover_url,
                        cjid,
                        'cover',
                        0,
                        referer_url=manga_url
                    )

                    if abs_cover_path:
                        # 获取下载后的相对路径并同步到数据库记录
                        local_manga.cover_url = self.downloader.get_relative_path(abs_cover_path)

            status_changed = False
            if local_manga.status == 0 and source_manga.status == 1 and not has_new_chapters:
                logger.info(f"✅ 源站已完结且本地已追平所有章节，将漫画 '{local_manga.title}' 状态更新为已完结")
                local_manga.status = 1
                status_changed = True

            if has_new_chapters or metadata_changed or status_changed:
                logger.info(f"漫画 '{local_manga.title}' 数据有变更，执行数据库保存...")
                latest_source_chapter = max(source_manga.chapters, key=lambda c: c.order, default=None)
                if latest_source_chapter:
                    local_manga.last_chapter_id = latest_source_chapter.id
                    local_manga.last_chapter_title = latest_source_chapter.name

                self.db.save_manga(local_manga)
            else:
                logger.info(f"漫画 '{local_manga.title}' 数据无任何变更，跳过数据库保存。")

            return has_new_chapters

        except Exception as e:
            logger.error(f"处理漫画 {manga_in_db['title']} 更新失败: {e}")
            return False

    def _process_new_chapter(self, local_manga: Manga, cjid: str, chapter: Chapter):
        """处理单个新章节的下载和入库"""
        logger.info(f"处理新章节: {chapter.name} (Order: {chapter.order})")
        chapter.manhua_id = local_manga.db_id
        chapter_url = f"{self.spider.base_url}/view/{cjid}/{chapter.id}"

        if chapter.cover:
            try:
                local_cover_path = self.downloader.download_single_image(
                    chapter.cover, cjid, f"{chapter.id}_cover", 0, referer_url=chapter_url
                )
                chapter.cover = self.downloader.get_relative_path(local_cover_path)
            except Exception as e:
                logger.error(f"下载章节 '{chapter.name}' 封面失败: {e}")
                chapter.cover = ''

        image_urls = self.spider.get_comic_detail(cjid, chapter.id)
        if image_urls is None:
            logger.warning(f"获取章节 '{chapter.name}' 图片列表失败，将创建空章节记录。")
            image_urls = []

        def refresh_url_callback():
            """定义一个在下载器内部调用的URL刷新函数"""
            return self.spider.get_comic_detail(cjid, chapter.id)

        local_image_paths = self.downloader.download_chapter_images(
            image_urls, cjid, chapter.id, chapter_url,
            refresh_callback=refresh_url_callback
        )
        chapter.image_list = [self.downloader.get_relative_path(p) for p in local_image_paths if p]

        if not chapter.cover and chapter.image_list:
            chapter.cover = chapter.image_list[0]

        self.db.save_chapter(chapter)

    def create_new_manga(self, comic_id: str) -> Optional[Manga]:
        """创建新漫画"""
        logger.info(f"尝试创建新漫画，采集ID: {comic_id}")

        existing_manga = self.db.get_manga_by_cjid(comic_id)
        if existing_manga:
            logger.info(f"漫画 '{existing_manga.title}' 已存在于数据库 (DB ID: {existing_manga.db_id})")
            return existing_manga

        source_manga = self.spider.get_manga_info(comic_id)
        if not source_manga:
            logger.error(f"无法从源站获取漫画 {comic_id} 的信息")
            return None

        if source_manga.ticai_name:
            source_manga.ticai_id = self._get_or_create_ticai_id(source_manga.ticai_name)

        if source_manga.cover_url:
            manga_url = f"{self.spider.base_url}/100/comic/{comic_id}"
            local_cover = self.downloader.download_single_image(source_manga.cover_url, comic_id, 'cover', 0,
                                                                referer_url=manga_url)
            source_manga.cover_url = self.downloader.get_relative_path(local_cover)

        if source_manga.vip_code == 1:
            logger.info(f"漫画 '{source_manga.title}' 为非VIP作品，自动设置推广标记...")
            source_manga.tjswitch = 1
            source_manga.isjingpin = 1
            source_manga.ishot = 1
            source_manga.issole = 1
            source_manga.isnew = 1

        new_manga_id = self.db.save_manga(source_manga)
        source_manga.db_id = new_manga_id
        logger.info(f"✅ 成功创建漫画 '{source_manga.title}' 到数据库, ID: {new_manga_id}")

        return source_manga

    def process_manga_updates(self) -> Dict[str, int]:
        """处理所有未完结漫画的更新检测"""
        logger.info("开始批量检测所有未完结漫画的更新")
        mangas_to_update = self.db.get_unfinished_manga_for_update()

        if not mangas_to_update:
            logger.info("没有找到需要更新的漫画")
            return {'total': 0, 'updated': 0, 'error': 0}

        total, updated, error = len(mangas_to_update), 0, 0
        for manga_dict in mangas_to_update:
            try:
                if self.process_single_manga_update(manga_dict):
                    updated += 1
            except Exception as e:
                logger.error(f"处理漫画 {manga_dict['title']} 时发生致命错误: {e}")
                error += 1

        logger.info(f"批量更新完成: 总计 {total} 部，有新章节 {updated} 部，失败 {error} 部")
        return {'total': total, 'updated': updated, 'error': error}

    def process_full_collection(self, comic_id: str, start_chapter: int = 0, db_manga_id: Optional[int] = None) -> bool:
        """处理完整采集，是 'add' 和 'update' 的功能合集"""
        logger.info(f"开始完整采集漫画 (源站ID: {comic_id}), 起始章节: {start_chapter or '第1章'}")
        try:
            local_manga, source_manga, has_new_chapters, chapters_to_process = self._prepare_collection_data(comic_id,
                                                                                                             start_chapter,
                                                                                                             db_manga_id)
            if local_manga is None or source_manga is None:
                # 在 prepare 阶段已经记录了详细日志，这里直接返回
                return False

            if has_new_chapters:
                for chapter in sorted(chapters_to_process, key=lambda c: c.order):
                    self._process_new_chapter(local_manga, local_manga.cjid, chapter)

            status_changed = False
            if local_manga.status == 0 and source_manga.status == 1 and not has_new_chapters:
                logger.info(f"✅ 源站已完结且本地已追平所有章节，将漫画 '{local_manga.title}' 状态更新为已完结")
                local_manga.status = 1
                status_changed = True

            metadata_changed = (local_manga.cjid != comic_id) or (
                        local_manga.ticai_id is None and source_manga.ticai_name is not None)

            if has_new_chapters or status_changed or metadata_changed:
                latest_chapter = max(source_manga.chapters, key=lambda c: c.order, default=None)
                if latest_chapter:
                    local_manga.last_chapter_id = latest_chapter.id
                    local_manga.last_chapter_title = latest_chapter.name
                self.db.save_manga(local_manga)
                logger.info(f"漫画 '{local_manga.title}' (采集ID: {local_manga.cjid}) 已保存最新状态。")
            else:
                logger.info(f"漫画 '{local_manga.title}' 数据无任何变更，跳过数据库保存。")

            return True

        except Exception as e:
            logger.error(f"完整采集漫画 {comic_id} 过程中发生错误: {e}")
            return False

    def _prepare_collection_data(self, comic_id, start_chapter, db_manga_id):
        """为 process_full_collection 准备和校验数据"""
        local_manga = None
        if db_manga_id:
            local_manga = self.db.get_manga_by_db_id(db_manga_id)
        if not local_manga:
            local_manga = self.create_new_manga(comic_id)
        if not local_manga: return None, None, False, []

        if str(local_manga.cjid) != str(comic_id):
            logger.info(f"检测到采集ID变更: 从 {local_manga.cjid} -> {comic_id}")
            local_manga.cjid = comic_id

        source_manga = self.spider.get_manga_info(local_manga.cjid)
        if not source_manga: return local_manga, None, False, []

        self._sync_nondestructive_metadata(local_manga, source_manga)

        existing_orders = self.db.get_manga_chapter_orders(local_manga.db_id)
        chapters_to_process = [ch for ch in source_manga.chapters if
                               ch.order not in existing_orders and ch.order >= start_chapter]
        has_new_chapters = len(chapters_to_process) > 0

        return local_manga, source_manga, has_new_chapters, chapters_to_process


    def process_force_collection(self, db_manga_id: int, source_comic_id: str, target_chapter_id: str) -> bool:
        """
        强制采集指定ID的章节 (精准模式)
        :param target_chapter_id: 源站的章节ID (例如 '119016')
        """
        # 1. 验证本地漫画
        local_manga = self.db.get_manga_by_db_id(db_manga_id)
        if not local_manga:
            print(f"❌ 错误: 本地数据库中找不到ID为 {db_manga_id} 的漫画")
            return False

        print(f"=== 正在处理: {local_manga.title} (本地数据库漫画ID: {db_manga_id}) ===")

        # 2. 获取源站数据
        print(f"📡 正在获取源站数据 (ID: {source_comic_id})...")
        source_manga = self.spider.get_manga_info(source_comic_id)
        if not source_manga:
            print(f"❌ 错误: 无法获取源站漫画ID {source_comic_id} 的数据")
            return False

        # 3. 精确查找目标章节
        target_chapter = None
        for ch in source_manga.chapters:
            if str(ch.id) == str(target_chapter_id):
                target_chapter = ch
                break

        if not target_chapter:
            print(f"❌ 错误: 在源站漫画中未找到ID为 [{target_chapter_id}] 的章节")
            print(f"   提示: 请检查源站URL中的章节ID是否正确")
            return False

        print(f"✅ 找到目标章节: 第{target_chapter.order}话 - {target_chapter.name} (ID: {target_chapter.id})")

        # 检查ID是否存在 仅做提示
        cjid_sql = "SELECT id, title FROM qiswl_capter WHERE cjid = %s AND manhua_id = %s"
        existing_by_id = self.db.execute_query(cjid_sql, (target_chapter_id, local_manga.db_id))

        if existing_by_id:
            print(f"⚠️  警告: 该章节ID [{target_chapter_id}] 本地已存在！(标题: {existing_by_id[0]['title']})")
            confirm = input("   >>> 是否强行采集该章节? (y/n): ").strip().lower()
            if confirm != 'y':
                print("   操作已取消")
                return False

        # 5. 执行采集
        print(f"📥 开始下载资源...")
        try:
            # 直接调用核心下载入库逻辑
            self._process_new_chapter(local_manga, source_comic_id, target_chapter)
            print(f"🎉 成功采集并入库: {target_chapter.name}")
            return True

        except Exception as e:
            print(f"❌ 采集失败: {e}")
            logger.error(f"手工采集章节 {target_chapter.name} 失败: {e}")
            return False

    def close(self):
        """关闭资源"""
        if self.db:
            self.db.close()