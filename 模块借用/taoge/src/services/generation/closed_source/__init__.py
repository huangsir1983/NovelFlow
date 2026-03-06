"""
涛割 - 闭源Provider模块
"""

from .vidu_provider import ViduProvider
from .kling_provider import KlingProvider
from .jimeng_provider import JimengProvider
from .yunwu_provider import YunwuProvider
from .geek_provider import GeekProvider

# 预留其他Provider
# from .grok_provider import GrokProvider

__all__ = [
    'ViduProvider',
    'KlingProvider',
    'JimengProvider',
    'YunwuProvider',
    'GeekProvider',
]
