# downloader.py
# -*- coding: utf-8 -*-
"""
多线程下载模块 - 【最终完整版】
"""
import io
import os
import time
import random
import logging
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Callable
from config import SITE_CONFIG, IMAGE_CONFIG, DOWNLOAD_CONFIG, ENVIRONMENT_CONFIG, WATERMARK_CONFIG
from WatermarkProcessor import create_watermark_processor
from PIL import Image

logger = logging.getLogger(__name__)


class ImageDownloader:
    def __init__(self, base_url: str = None):
        self.session = requests.Session()
        self.base_url = base_url or SITE_CONFIG['base_url']
        self.setup_session()
        self.watermark_processor = create_watermark_processor(WATERMARK_CONFIG)
        if self.watermark_processor and WATERMARK_CONFIG.get('enabled', False):
            logger.info(f"水印功能已启用，模式: {WATERMARK_CONFIG.get('mode', 'first')}")

    def setup_session(self):
        """设置session的默认配置"""
        self.session.headers.update({
            'User-Agent': SITE_CONFIG['user_agent'],
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="124", "Google Chrome";v="124"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        })

    def ensure_dir(self, dir_path: str):
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    def download_single_image(self, image_url: str, comic_id: str, chapter_id: str, index: int, referer_url: str) -> \
    Optional[str]:
        """下载单张图片到本地（不带重试）"""
        try:
            if isinstance(image_url, dict):
                image_url = image_url.get('url') or image_url.get('src')

            if not image_url or not isinstance(image_url, str): return None
            headers = {'Referer': referer_url}

            save_dir = os.path.join(IMAGE_CONFIG['base_path'], str(comic_id), str(chapter_id))
            self.ensure_dir(save_dir)
            file_name = f"{index}.webp"
            save_path = os.path.join(save_dir, file_name)

            #if os.path.exists(save_path): return save_path
            if os.path.exists(save_path) and chapter_id != 'cover':
                return save_path

            response = self.session.get(image_url, timeout=30, stream=True, headers=headers)
            response.raise_for_status()

            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            image.save(save_path, format="WEBP", quality=80, method=6)

            logger.debug(f"图片下载成功: {save_path}")
            return save_path

        except Exception as e:
            raise Exception(f"下载图片失败: {image_url}, Referer: {referer_url}, 错误: {e}")

    def _download_with_retry(self, image_url: str, comic_id: str, chapter_id: str, index: int, referer_url: str) -> \
    Optional[str]:
        """带重试逻辑的图片下载方法"""
        max_retries = DOWNLOAD_CONFIG['download_max_retries']
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.warning(f"图片 {index} 下载失败，正在进行第 {attempt} 次重试...")
                    time.sleep(1 * attempt)

                return self.download_single_image(image_url, comic_id, chapter_id, index, referer_url)
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"图片 {index} 下载失败，已达到最大重试次数: {e}")
                    return None
        return None

    def download_chapter_images(self, image_urls: List[str], comic_id: str, chapter_id: str, chapter_url: str,
                                refresh_callback: Optional[Callable] = None) -> List[str]:
        """多线程下载章节所有图片（恢复分批、延迟和URL刷新）"""
        total_images = len(image_urls)
        logger.info(f"开始下载章节 {chapter_id} 的 {total_images} 张图片")

        if not image_urls or ENVIRONMENT_CONFIG['is_download_image'] == 0:
            if ENVIRONMENT_CONFIG['is_download_image'] == 0: logger.info("当前配置跳过图片下载...")
            return []

        # 从配置中读取参数
        batch_size = DOWNLOAD_CONFIG['batch_size']
        concurrent_downloads = DOWNLOAD_CONFIG['concurrent_downloads']
        url_refresh_interval = DOWNLOAD_CONFIG['url_refresh_interval']

        local_paths = [''] * total_images

        current_urls = list(image_urls)
        last_refresh_time = time.time()

        batch_count = (total_images + batch_size - 1) // batch_size
        logger.info(
            f"将 {total_images} 张图片分成 {batch_count} 批处理，每批最多 {batch_size} 张，并发数: {concurrent_downloads}")

        for batch_index in range(batch_count):
            if refresh_callback and time.time() - last_refresh_time >= url_refresh_interval:
                logger.info(f"下载耗时超过 {url_refresh_interval} 秒，尝试刷新图片链接...")
                try:
                    new_urls = refresh_callback()
                    if new_urls and len(new_urls) == total_images:
                        current_urls = new_urls
                        logger.info("✅ 成功刷新图片链接！")
                    else:
                        logger.warning("刷新链接失败或返回的图片数量不匹配，将继续使用旧链接")
                except Exception as e:
                    logger.error(f"执行URL刷新回调时出错: {e}")
                last_refresh_time = time.time()

            batch_start = batch_index * batch_size
            batch_end = min(batch_start + batch_size, total_images)
            logger.info(f"开始下载第 {batch_index + 1}/{batch_count} 批 (图片 {batch_start + 1}-{batch_end})")

            batch_items = [{'index': i, 'url': current_urls[i]} for i in range(batch_start, batch_end)]

            self._download_batch_with_threadpool(batch_items, comic_id, chapter_id, local_paths, concurrent_downloads,
                                                 chapter_url)

            if batch_index < batch_count - 1:
                delay = random.randint(DOWNLOAD_CONFIG['batch_delay_min'], DOWNLOAD_CONFIG['batch_delay_max']) / 1000
                logger.info(f"批次 {batch_index + 1} 完成，随机延迟 {delay:.2f} 秒后继续...")
                time.sleep(delay)

        success_count = sum(1 for path in local_paths if path)
        success_rate = (success_count / total_images * 100) if total_images > 0 else 0
        logger.info(f"章节 {chapter_id} 全部批次下载完成: {success_count}/{total_images} 张成功 ({success_rate:.1f}%)")

        if self.watermark_processor and success_count > 0:
            local_paths = self.watermark_processor.process_chapter_images(local_paths, chapter_id)

        return local_paths

    def _download_batch_with_threadpool(self, batch_items: List[Dict], comic_id: str, chapter_id: str,
                                        local_paths: List[str], concurrent_downloads: int, chapter_url: str):
        """使用线程池下载一批图片"""
        with ThreadPoolExecutor(max_workers=concurrent_downloads) as executor:
            future_to_item = {
                executor.submit(self._download_with_retry, item['url'], comic_id, chapter_id, item['index'] + 1,
                                chapter_url): item
                for item in batch_items
            }

            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    local_path = future.result()
                    if local_path:
                        local_paths[item['index']] = local_path
                        logger.debug(f"图片 {item['index'] + 1}/{len(local_paths)} 下载成功")
                except Exception as e:
                    logger.error(f"图片 {item['index'] + 1}/{len(local_paths)} 下载出现最终异常: {e}")

                time.sleep(DOWNLOAD_CONFIG['request_delay'] / 1000)

    def get_relative_path(self, absolute_path: Optional[str]) -> str:
        """将绝对路径转换为相对路径"""
        if not absolute_path: return ''
        try:
            base_path = Path(IMAGE_CONFIG['absolute_path_prefix'])
            relative_path = Path(absolute_path).relative_to(base_path)
            return '/' + str(relative_path).replace('\\', '/')
        except ValueError:
            logger.warning(f"路径 {absolute_path} 不在基础路径下，无法转为相对路径")
            return absolute_path