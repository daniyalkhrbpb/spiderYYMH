# spider_core.py
# -*- coding: utf-8 -*-
"""
爬虫核心模块 - 【生产版】
获取并解析源站数据，返回结构化的数据模型
"""

import requests
import json
import re
import time
import logging
from typing import Optional
from config import SITE_CONFIG, COOKIE
from models import Manga, Chapter
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SpiderCore:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = SITE_CONFIG['base_url']
        self.setup_session()

    def setup_session(self):
        """设置session的默认配置"""
        self.session.headers.update({
            'User-Agent': SITE_CONFIG['user_agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="124", "Google Chrome";v="124"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
        })

    def get_working_domain(self) -> str:
        """获取可用的网站域名"""
        try:
            logger.info(f"测试主域名: {self.base_url}")
            response = self.session.get(self.base_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"主域名 {self.base_url} 可用")
                return self.base_url
        except Exception as e:
            logger.warning(f"主域名不可用: {e}")

        for domain in SITE_CONFIG['backup_domains']:
            try:
                logger.info(f"测试备用域名: {domain}")
                response = self.session.get(domain, timeout=5)
                if response.status_code == 200:
                    logger.info(f"找到可用的备用域名: {domain}")
                    self.base_url = domain
                    return domain
            except Exception as e:
                logger.warning(f"备用域名 {domain} 不可用: {e}")

        logger.error("所有域名都不可用")
        raise ConnectionError("所有配置的域名均无法访问！")

    def request_with_retry(self, url: str, max_retries: int = None) -> requests.Response:
        """带重试的请求方法"""
        if max_retries is None:
            max_retries = SITE_CONFIG['max_retries']

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    delay = SITE_CONFIG['request_interval'] * (2 ** (attempt - 1))
                    time.sleep(delay)

                response = self.session.get(
                    url,
                    timeout=SITE_CONFIG['request_timeout'],
                    headers={'Referer': SITE_CONFIG['referer'], 'Cookie': COOKIE}
                )
                response.raise_for_status()
                return response
            except Exception as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries + 1})，准备重试: {e}")
        raise Exception(f"请求最终失败: {url}")

    def get_manga_info(self, comic_id: str) -> Optional[Manga]:
        """获取漫画的完整信息，返回一个Manga数据对象"""
        url = f"{self.base_url}/100/comic/{comic_id}"
        logger.info(f"请求漫画详情页: {url}")
        try:
            response = self.request_with_retry(url)
            html = response.text

            title_match = re.search(r'<div class="BarTit" id="comicName">(.*?)</div>', html)
            title = title_match.group(1).strip() if title_match else ''

            author_match = re.search(r'class="pd introName"[^>]*>(.*?)<', html)
            author = author_match.group(1).strip() if author_match else ''

            cover_match = re.search(r'<div class="pic" id="Cover">\s*<img src="([^"]+)"', html)
            cover_url = cover_match.group(1) if cover_match else ''

            desc_match = re.search(r'<p class="txtDesc autoHeight">(.*?)</p>', html, re.DOTALL)
            description = re.sub(r'<br\s*/?>', '\n', desc_match.group(1).strip()).split('<')[0].strip() if desc_match else ''

            # tags = re.findall(r'<a class="pd" href="/tags/tag/\d+">(.*?)</a>', html)
            #
            # ticai_match = re.search(r'<a class="pd" href="/tags/zone/\d+">([^<]+)</a>', html)
            # manga_ticai = ticai_match.group(1).strip() if ticai_match else None

            txt_items = re.findall(r'<p class="txtItme">([\s\S]*?)</p>', html)
            tags = []
            manga_ticai = None

            if len(txt_items) >= 3:
                tags_raw = re.findall(r'class="pd"[^>]*>([^<]+)<', txt_items[1])
                tags = [t.strip() for t in tags_raw if t.strip()]

                ticai_raw = re.findall(r'class="pd"[^>]*>([^<]+)<', txt_items[2])
                clean_ticai = [t.strip() for t in ticai_raw if t.strip()]
                if clean_ticai:
                    manga_ticai = clean_ticai[0]

            status_match = re.search(r'<a class="pd" href="/tags/end/(\d+)">', html)
            manga_status = int(status_match.group(1)) if status_match else 0
            vip_match = re.search(r'<span>((?:非)?VIP作品\(.*?\))</span>', html)
            vip_status_text = vip_match.group(1).strip() if vip_match else "未知"
            vip_code = 1 if "非VIP" in vip_status_text else (0 if "VIP" in vip_status_text else -1)

            json_match = re.search(r'initIntroData\(([\s\S]*?)\);', html)
            if not json_match: raise Exception(f'漫画 {comic_id} 页面找不到章节JSON数据')
            chapters_data = json.loads(json_match.group(1))[0]['data']

            chapters = [
                Chapter(id=str(c['id']), name=c['chapter_name'], order=int(c['chapter_order']),
                        cover=c['chapter_cover'], is_free=(c['is_free'] == 1),
                        gold=str(c['gold']), update_time=c['update_time']) for c in chapters_data
            ]

            return Manga(cjid=comic_id, title=title or f"漫画ID_{comic_id}", author=author, description=description,
                         cover_url=cover_url, tags=tags, ticai_name=manga_ticai, status=manga_status,
                         vip_status_text=vip_status_text, vip_code=vip_code, chapters=chapters)
        except Exception as e:
            logger.error(f"获取并解析漫画 {comic_id} 信息失败: {e}")
            return None

    def get_comic_detail(self, comic_id: str, chapter_id: str) -> Optional[list]:
        """获取章节详情页的图片列表"""
        url = f"{self.base_url}/view/{comic_id}/{chapter_id}"
        logger.info(f"请求章节图片列表: {url}")
        try:
            time.sleep(0.5)
            response = self.request_with_retry(url)
            html = response.text

            # 规则1: 优先匹配最具体的JS变量
            match = re.search(r'=\s*({.*?pages":\[.*?].*?});', html)
            if match:
                try:
                    json_str = match.group(1)
                    data = json.loads(json_str)

                    if 'volume' in data and 'pages' in data['volume']:
                        image_list = data['volume']['pages']
                        if isinstance(image_list, list):
                            logger.debug(f"通过JS变量成功提取到 {len(image_list)} 张图片")
                            return image_list
                except Exception as e:
                    logger.error(f"解析JSON时发生错误: {e}")

            # 规则2: 匹配懒加载的 data-original 属性
            img_tags = re.findall(r'<img[^>]+data-original="([^"]+)"', html)
            if img_tags:
                logger.debug(f"通过data-original属性成功提取到 {len(img_tags)} 张图片")
                return img_tags

            # 规则3: 最后的兜底规则，匹配普通 src 属性
            img_tags_src = re.findall(r'<img[^>]+src="([^"]+)"', html)
            if img_tags_src:
                valid_images = [src for src in img_tags_src if 'klm/' in src or 'abc/' in src]
                if valid_images:
                    logger.debug(f"通过普通src属性成功提取到 {len(valid_images)} 张图片")
                    return valid_images

            # --- 【核心修改】移除了保存HTML文件的调试代码 ---
            raise Exception("无法找到章节图片数据")

        except Exception as e:
            logger.error(f"获取章节 {chapter_id} 详情失败: {e}")
            return None