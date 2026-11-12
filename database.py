# database.py
# -*- coding: utf-8 -*-
"""
数据库操作模块 (Repository模式)
"""

import pymysql
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from config import DATABASE_CONFIG, ENVIRONMENT_CONFIG
from models import Manga, Chapter

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        try:
            self.connection = pymysql.connect(**DATABASE_CONFIG)
            logger.info("数据库连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def connect(self):
        """确保数据库连接存在"""
        if not self.connection or not self.connection.open:
            logger.info("数据库连接已断开，正在重新连接...")
            self.connection = pymysql.connect(**DATABASE_CONFIG)

    def get_current_beijing_time(self) -> str:
        """获取北京时间"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def execute_query(self, sql: str, params: tuple = None) -> List[Dict]:
        """执行查询语句"""
        try:
            self.connect()
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"查询执行失败: {e}, SQL: {sql}")
            raise

    def execute_update(self, sql: str, params: tuple = None) -> int:
        """执行更新/删除语句"""
        try:
            self.connect()
            with self.connection.cursor() as cursor:
                affected_rows = cursor.execute(sql, params)
                self.connection.commit()
                return affected_rows
        except Exception as e:
            logger.error(f"更新执行失败: {e}, SQL: {sql}")
            self.connection.rollback()
            raise

    def execute_insert(self, sql: str, params: tuple = None) -> int:
        """执行插入语句，返回插入的ID"""
        try:
            self.connect()
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
                self.connection.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"插入执行失败: {e}, SQL: {sql}")
            self.connection.rollback()
            raise

    def get_ticai_by_name(self, name: str) -> Optional[Dict]:
        sql = "SELECT * FROM qiswl_ticai WHERE name = %s"
        result = self.execute_query(sql, (name,))
        return result[0] if result else None

    def insert_ticai(self, name: str) -> Optional[int]:
        sql = "INSERT INTO qiswl_ticai (name, type, switch) VALUES (%s, %s, %s)"
        try:
            return self.execute_insert(sql, (name, 1, 1))
        except Exception:
            logger.warning(f"插入题材'{name}'可能由并发导致失败，尝试重新获取")
            existing = self.get_ticai_by_name(name)
            return existing.get('id') if existing else None

    def get_manga_by_id(self, manga_id: int) -> Optional[Dict]:
        """通过本地DB ID获取漫画信息（用于兼容旧的调用）"""
        sql = "SELECT * FROM qiswl_manhua WHERE id = %s"
        result = self.execute_query(sql, (manga_id,))
        return result[0] if result else None

    def get_manga_by_db_id(self, db_id: int) -> Optional[Manga]:
        """通过数据库ID获取漫画信息，并组装成Manga对象"""
        manga_data = self.get_manga_by_id(db_id)
        if not manga_data:
            return None
        return self._dict_to_manga_model(manga_data)

    def get_manga_by_cjid(self, cjid: str) -> Optional[Manga]:
        """通过采集ID获取漫画信息，并组装成Manga对象"""
        sql = "SELECT * FROM qiswl_manhua WHERE cjid = %s AND cjname = 'ttmh'"
        result = self.execute_query(sql, (cjid,))
        if not result: return None
        return self._dict_to_manga_model(result[0])

    def save_manga(self, manga: Manga) -> int:
        """保存Manga对象 (智能判断是插入还是更新)"""
        if manga.db_id:  # 更新
            update_data = {
                'title': manga.title, 'auther': manga.author, '`desc`': manga.description,
                'cover': manga.cover_url, 'image': manga.cover_url, 'keyword': ','.join(manga.tags),
                'mhstatus': manga.status, 'ticai_id': manga.ticai_id, 'cjid': manga.cjid,
                'last_chapter': manga.last_chapter_id, 'last_chapter_title': manga.last_chapter_title,
                'cjname': 'ttmh',
            }
            update_data = {k: v for k, v in update_data.items() if v is not None}
            self._update_record('qiswl_manhua', manga.db_id, update_data)
            return manga.db_id
        else:  # 插入
            insert_data = {
                'title': manga.title, 'auther': manga.author, '`desc`': manga.description,
                'image': manga.cover_url, 'cover': manga.cover_url, 'keyword': ','.join(manga.tags),
                'ticai_id': manga.ticai_id, 'mhstatus': manga.status, 'cjid': manga.cjid,
                'cjname': 'ttmh', 'status': 1, 'type': 1,
                'create_time': self.get_current_beijing_time(), 'update_time': self.get_current_beijing_time(),
                'tjswitch': manga.tjswitch, 'isjingpin': manga.isjingpin, 'ishot': manga.ishot,
                'issole': manga.issole, 'isnew': manga.isnew,
            }
            return self._insert_record('qiswl_manhua', insert_data)

    # --- 【核心修正：不再通过cjid，而是通过章节顺序号(sort)来判断】 ---
    def get_manga_chapter_orders(self, manhua_id: int) -> set:
        """获取漫画所有章节的顺序号(sort)集合，用于快速比对"""
        sql = "SELECT sort FROM qiswl_capter WHERE manhua_id = %s"
        results = self.execute_query(sql, (manhua_id,))
        # 确保返回的是整数集合
        return {int(row['sort']) for row in results if row.get('sort') is not None}

    def save_chapter(self, chapter: Chapter) -> int:
        """保存Chapter对象到数据库"""
        data = {
            'manhua_id': chapter.manhua_id, 'title': chapter.name, 'image': chapter.cover,
            'sort': chapter.order, 'isvip': '1' if not chapter.is_free else '0',
            'score': 0 if chapter.is_free else 58, 'imagelist': ','.join(chapter.image_list),
            'cjid': chapter.id, 'cjname': 'ttmh', 'switch': 1, 'type': 1,
            'create_time': self.get_current_beijing_time(), 'update_time': self.get_current_beijing_time()
        }
        return self._insert_record('qiswl_capter', data)

    def _dict_to_manga_model(self, data: Dict) -> Manga:
        """将从数据库查出的字典转换为Manga对象"""
        return Manga(
            db_id=data['id'], cjid=data['cjid'], title=data['title'],
            author=data.get('auther', ''), description=data.get('desc', ''),
            cover_url=data.get('cover', ''), tags=(data.get('keyword') or '').split(','),
            status=data.get('mhstatus', 0), ticai_id=data.get('ticai_id'),
            last_chapter_id=data.get('last_chapter'), last_chapter_title=data.get('last_chapter_title'),
            tjswitch=data.get('tjswitch', 0), isjingpin=data.get('isjingpin', 0),
            ishot=data.get('ishot', 0), issole=data.get('issole', 0), isnew=data.get('isnew', 0),
            ticai_name=None, vip_status_text='', vip_code=-1
        )

    def _insert_record(self, table_name: str, data: Dict[str, Any]) -> int:
        """通用插入方法"""
        fields = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        sql = f"INSERT INTO {table_name} ({fields}) VALUES ({placeholders})"
        return self.execute_insert(sql, tuple(data.values()))

    def _update_record(self, table_name: str, record_id: int, data: Dict[str, Any]):
        """通用更新方法"""
        data['update_time'] = self.get_current_beijing_time()
        set_clauses = [f"{key} = %s" for key in data.keys()]
        sql = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE id = %s"
        params = list(data.values()) + [record_id]
        self.execute_update(sql, tuple(params))

    def get_unfinished_manga_for_update(self) -> List[Dict]:
        """获取所有未完结的ttmh渠道漫画（支持时间过滤）"""
        sync_start_time = ENVIRONMENT_CONFIG.get('sync_start_time')

        if sync_start_time:
            sql = "SELECT * FROM qiswl_manhua WHERE cjname = 'ttmh' AND mhstatus = 0 AND update_time >= %s ORDER BY update_time DESC"
            try:
                result = self.execute_query(sql, (sync_start_time,))
                logger.info(f"查询到 {len(result)} 部符合[时间控制]条件的未完结漫画需要检测更新")
                return result
            except Exception as e:
                logger.error(f"按时间查询未完结漫画失败: {e}")
                return []
        else:
            sql = "SELECT * FROM qiswl_manhua WHERE cjname = 'ttmh' AND mhstatus = 0 ORDER BY update_time DESC"
            try:
                result = self.execute_query(sql)
                logger.info(f"查询到 {len(result)} 部未完结的漫画需要检测更新")
                return result
            except Exception as e:
                logger.error(f"查询所有未完结漫画失败: {e}")
                return []

    def close(self):
        """关闭数据库连接"""
        if self.connection and self.connection.open:
            self.connection.close()
            logger.info("数据库连接已关闭")