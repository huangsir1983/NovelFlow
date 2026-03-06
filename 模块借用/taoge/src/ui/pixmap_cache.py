"""
涛割 - 图片缓存工具
LRU缓存机制，避免重复加载和缩放QPixmap
后台线程加载器，避免阻塞UI线程
"""

import os
from collections import OrderedDict
from typing import Optional, Tuple, List

from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QObject


class PixmapCache:
    """
    QPixmap LRU缓存
    - 根据 (文件路径, 目标尺寸) 作为缓存键
    - 自动淘汰最久未使用的条目
    """

    _instance: Optional['PixmapCache'] = None

    def __init__(self, max_entries: int = 200):
        self._cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._max_entries = max_entries

    @classmethod
    def instance(cls) -> 'PixmapCache':
        if cls._instance is None:
            cls._instance = PixmapCache()
        return cls._instance

    @staticmethod
    def _make_key(path: str, width: int, height: int) -> str:
        return f"{path}|{width}x{height}"

    def get_scaled(self, path: str, width: int, height: int,
                   aspect_mode=Qt.AspectRatioMode.KeepAspectRatio,
                   transform_mode=Qt.TransformationMode.SmoothTransformation
                   ) -> Optional[QPixmap]:
        """
        获取缩放后的缓存图片

        Args:
            path: 图片文件路径
            width: 目标宽度
            height: 目标高度
            aspect_mode: 宽高比模式
            transform_mode: 缩放算法

        Returns:
            缩放后的 QPixmap，文件不存在或加载失败返回 None
        """
        if not path or not os.path.exists(path):
            return None

        key = self._make_key(path, width, height)

        # 缓存命中：移到末尾（最近使用）
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        # 缓存未命中：加载并缩放
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return None

        scaled = pixmap.scaled(
            width, height, aspect_mode, transform_mode
        )

        # 存入缓存
        self._cache[key] = scaled
        self._evict()

        return scaled

    def get_original(self, path: str) -> Optional[QPixmap]:
        """
        获取原始尺寸的缓存图片

        Args:
            path: 图片文件路径

        Returns:
            原始 QPixmap，失败返回 None
        """
        if not path or not os.path.exists(path):
            return None

        key = self._make_key(path, 0, 0)

        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        pixmap = QPixmap(path)
        if pixmap.isNull():
            return None

        self._cache[key] = pixmap
        self._evict()

        return pixmap

    def invalidate(self, path: str):
        """使指定路径的所有缓存失效"""
        keys_to_remove = [k for k in self._cache if k.startswith(f"{path}|")]
        for k in keys_to_remove:
            del self._cache[k]

    def clear(self):
        """清空全部缓存"""
        self._cache.clear()

    def _evict(self):
        """淘汰超出容量的最旧条目"""
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)

    def get_layer_thumbnail(self, path: str, size: int = 40) -> Optional[QPixmap]:
        """
        获取图层缩略图（正方形裁剪 + 缩放）

        与 get_scaled 不同，此方法先居中裁剪为正方形再缩放，
        适合图层面板中的缩略图显示。

        Args:
            path: 图片文件路径
            size: 缩略图边长（像素）

        Returns:
            正方形缩略图 QPixmap，失败返回 None
        """
        if not path or not os.path.exists(path):
            return None

        key = f"layer_thumb|{path}|{size}"

        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        pixmap = QPixmap(path)
        if pixmap.isNull():
            return None

        # 居中裁剪为正方形
        w, h = pixmap.width(), pixmap.height()
        side = min(w, h)
        x = (w - side) // 2
        y = (h - side) // 2
        cropped = pixmap.copy(x, y, side, side)

        # 缩放到目标尺寸
        thumb = cropped.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self._cache[key] = thumb
        self._evict()
        return thumb

    @property
    def size(self) -> int:
        return len(self._cache)


class ThumbnailLoader(QThread):
    """
    后台缩略图加载线程
    在子线程中加载 QImage，通过信号传递给主线程转为 QPixmap

    用法：
        loader = ThumbnailLoader()
        loader.thumbnail_ready.connect(on_thumb_ready)
        loader.add_request("id1", "/path/to/img.png", 160, 140)
        loader.start()
    """

    # 信号: request_id, QImage
    thumbnail_ready = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._requests: List[Tuple[str, str, int, int]] = []
        self._abort = False

    def add_request(self, request_id: str, path: str, width: int, height: int):
        """添加加载请求"""
        self._requests.append((request_id, path, width, height))

    def run(self):
        """在子线程中加载图片"""
        for req_id, path, w, h in self._requests:
            if self._abort:
                break
            if not path or not os.path.exists(path):
                continue

            image = QImage(path)
            if image.isNull():
                continue

            scaled = image.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.thumbnail_ready.emit(req_id, scaled)

        self._requests.clear()

    def abort(self):
        """中止加载"""
        self._abort = True
