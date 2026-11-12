# models.py
# -*- coding: utf-8 -*-
"""
数据模型模块 - 定义程序核心的数据结构
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Chapter:
    """章节数据模型"""
    id: str
    name: str
    order: int
    cover: str
    is_free: bool
    gold: str
    update_time: str

    db_id: Optional[int] = None
    manhua_id: Optional[int] = None
    image_list: List[str] = field(default_factory=list)


@dataclass
class Manga:
    """漫画数据模型"""
    # --- 源站数据 ---
    cjid: str
    title: str
    author: str
    description: str
    cover_url: str
    tags: List[str]
    ticai_name: Optional[str]
    status: int
    vip_status_text: str
    vip_code: int
    chapters: List[Chapter] = field(default_factory=list)

    # --- 本地数据库数据 ---
    db_id: Optional[int] = None
    ticai_id: Optional[int] = None
    last_chapter_id: Optional[str] = None
    last_chapter_title: Optional[str] = None
    tjswitch: int = 0  # 推荐
    isjingpin: int = 0  # 精品
    ishot: int = 0  # 热门
    issole: int = 0  # 独家
    isnew: int = 0  # 新作