# -*- coding: utf-8 -*-
"""
水印处理模块 - 为漫画图片添加水印
"""

import os
import random
import logging
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

logger = logging.getLogger(__name__)

class WatermarkProcessor:
    """水印处理器"""

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get('enabled', False)
        self.watermark_text = config.get('text', '')
        self.mode = config.get('mode', 'first')  # first, last, all, random
        self.random_count = config.get('random_count', 1)
        if self.random_count < 1:
            self.random_count = 1
        self.template_path = config.get('template_path', '')
        self.position = config.get('position', 'bottom_right')  # bottom_right, bottom_left, top_right, top_left, center
        self.opacity = config.get('opacity', 0.8)
        self.scale = config.get('scale', 0.1)  # 水印相对于图片的大小比例
        self.font_size = config.get('font_size', 32)
        self.font_color = config.get('font_color', (255, 255, 255))
        self.margin = config.get('margin', 20)  # 边距

        # 加载水印模板
        self.watermark_template = None
        if self.template_path and os.path.exists(self.template_path):
            try:
                self.watermark_template = Image.open(self.template_path).convert("RGBA")
                logger.info(f"成功加载水印模板: {self.template_path}")
            except Exception as e:
                logger.error(f"加载水印模板失败: {e}")

    def should_add_watermark(self, image_index: int, total_images: int) -> bool:
        """判断是否应该为指定索引的图片添加水印"""
        if not self.enabled:
            return False

        if self.mode == 'first':
            return image_index == 0
        elif self.mode == 'last':
            return image_index == total_images - 1
        elif self.mode == 'all':
            return True
        elif self.mode == 'random':
            return hasattr(self, '_random_indices') and image_index in self._random_indices

        return False

    def set_random_index(self, total_images: int):
        if self.mode == 'random' and total_images > 0:
            count = min(self.random_count, total_images)
            self._random_indices = random.sample(range(total_images), count)
            logger.info(f"随机水印模式：选择第 {[idx + 1 for idx in self._random_indices]} 张图片添加水印")

    def add_watermark_to_image(self, image_path: str, chapter_id: str = '') -> bool:
        """为单张图片添加水印"""
        try:
            if not os.path.exists(image_path):
                logger.error(f"图片文件不存在: {image_path}")
                return False

            # 打开原图
            with Image.open(image_path).convert("RGBA") as base_image:
                # 创建一个与原图相同大小的透明图层
                overlay = Image.new('RGBA', base_image.size, (0, 0, 0, 0))

                # 添加水印
                if self.watermark_template:
                    # 使用模板水印
                    overlay = self._add_template_watermark(overlay, base_image.size)
                elif self.watermark_text:
                    # 使用文字水印
                    overlay = self._add_text_watermark(overlay, base_image.size, chapter_id)

                # 合并图层
                watermarked = Image.alpha_composite(base_image, overlay)

                # 转换为RGB并保存
                final_image = watermarked.convert('RGB')
                final_image.save(image_path, 'JPEG', quality=95, optimize=True)

                logger.debug(f"成功添加水印: {image_path}")
                return True

        except Exception as e:
            logger.error(f"添加水印失败 {image_path}: {e}")
            return False

    def _add_template_watermark(self, overlay: Image.Image, base_size: tuple) -> Image.Image:
        """添加模板水印"""
        if not self.watermark_template:
            return overlay

        # 计算水印大小
        base_width, base_height = base_size
        watermark_width = int(min(base_width, base_height) * self.scale)
        watermark_height = int(self.watermark_template.height * watermark_width / self.watermark_template.width)

        # 调整水印模板大小
        watermark = self.watermark_template.resize((watermark_width, watermark_height), Image.Resampling.LANCZOS)

        # 调整透明度
        if self.opacity < 1.0:
            alpha = watermark.split()[-1]
            alpha = alpha.point(lambda p: int(p * self.opacity))
            watermark.putalpha(alpha)

        # 计算水印位置
        x, y = self._calculate_position(base_size, (watermark_width, watermark_height))

        # 粘贴水印
        overlay.paste(watermark, (x, y), watermark)

        return overlay

    def _add_text_watermark(self, overlay: Image.Image, base_size: tuple, chapter_id: str = '') -> Image.Image:
        """添加文字水印"""
        draw = ImageDraw.Draw(overlay)

        # 替换文本中的占位符
        text = self.watermark_text.replace('{chapter_id}', str(chapter_id))

        # 尝试加载字体
        try:
            # 尝试加载系统字体
            font_paths = [
                # Windows
                "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
                "C:/Windows/Fonts/simhei.ttf",  # 黑体
                # Linux
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                # macOS
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/Arial.ttf"
            ]

            font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        font = ImageFont.truetype(font_path, self.font_size)
                        break
                    except:
                        continue

            if not font:
                font = ImageFont.load_default()

        except Exception as e:
            logger.warning(f"加载字体失败，使用默认字体: {e}")
            font = ImageFont.load_default()

        # 获取文本大小
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 计算文字位置
        x, y = self._calculate_position(base_size, (text_width, text_height))

        # 添加文字描边效果
        stroke_width = max(1, self.font_size // 16)

        # 绘制文字
        draw.text((x, y), text, font=font, fill=(*self.font_color, int(255 * self.opacity)),
                  stroke_width=stroke_width, stroke_fill=(0, 0, 0, int(255 * self.opacity * 0.8)))

        return overlay

    def _calculate_position(self, base_size: tuple, watermark_size: tuple) -> tuple:
        """计算水印位置"""
        base_width, base_height = base_size
        mark_width, mark_height = watermark_size

        if self.position == 'top_left':
            x, y = self.margin, self.margin
        elif self.position == 'top_right':
            x, y = base_width - mark_width - self.margin, self.margin
        elif self.position == 'bottom_left':
            x, y = self.margin, base_height - mark_height - self.margin
        elif self.position == 'bottom_right':
            x, y = base_width - mark_width - self.margin, base_height - mark_height - self.margin
        elif self.position == 'center':
            x, y = (base_width - mark_width) // 2, (base_height - mark_height) // 2
        else:
            # 默认右下角
            x, y = base_width - mark_width - self.margin, base_height - mark_height - self.margin

        return max(0, x), max(0, y)

    def process_chapter_images(self, image_paths: List[str], chapter_id: str = '') -> List[str]:
        """处理整个章节的图片，根据配置添加水印"""
        if not self.enabled or not image_paths:
            return image_paths

        # 过滤出有效的图片路径
        valid_paths = [path for path in image_paths if path and os.path.exists(path)]

        if not valid_paths:
            logger.warning("没有找到有效的图片文件")
            return image_paths

        total_images = len(valid_paths)
        logger.info(f"开始处理章节 {chapter_id} 的水印，共 {total_images} 张图片，模式: {self.mode}")

        # 为随机模式设置随机索引
        if self.mode == 'random':
            self.set_random_index(total_images)

        processed_count = 0

        # 处理每张图片
        for i, image_path in enumerate(image_paths):
            if not image_path or not os.path.exists(image_path):
                continue

            # 在 image_paths 中找到对应的索引
            try:
                valid_index = valid_paths.index(image_path)
            except ValueError:
                continue

            if self.should_add_watermark(valid_index, total_images):
                if self.add_watermark_to_image(image_path, chapter_id):
                    processed_count += 1
                    logger.info(f"已为第 {valid_index + 1} 张图片添加水印")

        if processed_count > 0:
            logger.info(f"章节 {chapter_id} 水印处理完成，共处理 {processed_count} 张图片")
        else:
            logger.info(f"章节 {chapter_id} 未添加水印")

        return image_paths


def create_watermark_processor(config: dict) -> Optional[WatermarkProcessor]:
    """创建水印处理器的工厂函数"""
    try:
        return WatermarkProcessor(config)
    except Exception as e:
        logger.error(f"创建水印处理器失败: {e}")
        return None