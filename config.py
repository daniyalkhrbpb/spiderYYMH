# -*- coding: utf-8 -*-
"""
配置文件 - 只包含配置信息，不包含任何代码逻辑
"""

# 数据库配置
DATABASE_CONFIG = {
    'host': '193.218.200.71',
    'user': 'yymh_com',
    'password': 'SWyx4DpEWsB5KHa4',
    'database': 'yymh_com',
    'charset': 'utf8mb4',
    'port': 3306,
    'autocommit': True
}

# 网站配置
SITE_CONFIG = {
    # 主要域名
    'base_url': 'https://www.yymh15.cc',
    'referer': 'https://www.yymh16.cc/',
    
    # 备用域名配置
    'backup_domains': [
        'https://www.yymh10.cc',
        'https://www.yymh11.cc',
        'https://www.yymh12.cc',
        'https://www.yymh13.cc',
        'https://www.yymh14.cc',
        'https://www.yymh17.cc',
        'https://www.yymh18.cc'
    ],
    
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'site_name': 'ttmh',
    
    # 请求配置
    'request_interval': 1.0,  # 请求间隔，单位秒
    'request_timeout': 10,    # 请求超时，单位秒
    'max_retries': 3          # 最大重试次数
}

# Cookie配置 - 需要更新为最新的Cookie
COOKIE = 'PHPSESSID=mnqq41t1s1369l8lm1pbfril2f; reaua=sdaofu; reauava=https%3A%2F%2Fstatic.ccdi1.click%2Fstatic%2Fserimgs%2Favatar%2F9.jpg; reauathf=4e30e07f47ca207da1343388d076414a; reauathe=1e9f2f80e469359b96b38f5ae18de047; reauathe=1e9f2f80e469359b96b38f5ae18de047; reauathn=d2d8231b3a9fc6f31071256bb861df0b; reauathx=bc1db39f0433bd9a604043c56c3a837a; reauath3=a52551df9448033ec9b0a24c211eb1f0; reauatho=cff82596f12ceb62fc647fb97c55d0a5; reauathp=74c7d424de32780b7569daad79c2659c; reauathq=57742a177e634e41f78decb3510743d1; reauathb=04697ed6070263d55f80a26bfb73e6f5; reauathj=208f59e8bdb790b5f5cffe68f576dcd8; history_cookie_ppm=null'

# 图片配置
IMAGE_CONFIG = {
    # 图片保存的绝对路径前缀
    'absolute_path_prefix': '/www/wwwroot/yymh.com',
    # 图片保存的绝对路径
    'base_path': '/www/wwwroot/yymh.com/bookimages',
    # 网站URL前缀，用于访问本地图片
    'url_prefix': '/bookimages'
}

# 下载配置
DOWNLOAD_CONFIG = {
    # 每批次处理的图片数量
    'batch_size': 10,
    # 同时下载的线程数
    'concurrent_downloads': 4,
    # URL刷新间隔（秒）
    'url_refresh_interval': 120,  # 2分钟
    # 下载重试次数
    'download_max_retries': 3,
    # 批次间延迟（毫秒）
    'batch_delay_min': 500,
    'batch_delay_max': 1500,
    # 请求间延迟（毫秒）
    'request_delay': 300
}

# 环境配置
ENVIRONMENT_CONFIG = {
    # 是否下载图片 (1=下载，0=不下载) ，便于功能测试,不然测试功能时下载漫画太耗时间
    'is_download_image': 1,
    'sync_start_time': '2025-08-01 00:00:00'
}

# 日志配置
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'spider.log',
    'max_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5
}

# 水印配置
WATERMARK_CONFIG = {
    # 是否启用水印功能 True开启 False关闭
    'enabled': True,

    # 水印模式: 'first'=第一张, 'last'=最后一张, 'all'=每一张, 'random'=随机一张
    'mode': 'last',

    # 随机数量
    'random_count': 1,

    # 水印内容 (支持占位符 {chapter_id})
    'text': 'www.yymh.im',

    # 水印模板图片路径 (如果设置了模板，会优先使用图片水印模板而不使用文字水印)
    # 根目录下的路径示例：'template_path': './水印.jpg',
    'template_path': '',

    # 水印位置: 'top_left', 'top_right', 'bottom_left', 'bottom_right', 'center'
    'position': 'bottom_right',

    # 水印透明度 (0.0-1.0)
    'opacity': 0.8,

    # 水印大小比例 (相对于图片的比例, 0.05-0.3)
    'scale': 0.2,

    # 文字水印设置
    'font_size': 35,
    'font_color': (255, 255, 255),  # RGB颜色

    # 边距 (像素)
    'margin': 120
}