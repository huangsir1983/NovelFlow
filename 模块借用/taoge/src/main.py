"""
涛割 - AI视频生成平台
主程序入口
"""

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def main():
    """主函数"""
    from ui import run_app
    run_app()


if __name__ == "__main__":
    main()
