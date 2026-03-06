"""
涛割 - 视频帧提取工具
使用 opencv-python-headless 从视频中提取帧
"""

import os
from typing import Optional, Dict, Any


class FrameExtractor:
    """从视频中提取帧"""

    @staticmethod
    def extract_last_frame(video_path: str, output_path: str) -> Optional[str]:
        """
        提取视频最后一帧，保存为 PNG

        Args:
            video_path: 视频文件路径
            output_path: 输出图片路径

        Returns:
            成功返回输出路径，失败返回 None
        """
        try:
            import cv2
        except ImportError:
            print("opencv-python-headless 未安装，无法提取视频帧")
            return None

        if not os.path.exists(video_path):
            print(f"视频文件不存在: {video_path}")
            return None

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"无法打开视频: {video_path}")
            return None

        try:
            # 获取总帧数
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                print(f"视频帧数为 0: {video_path}")
                return None

            # 定位到最后一帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
            ret, frame = cap.read()
            if not ret:
                # 从末尾向前尝试读取
                for offset in range(2, min(10, total_frames)):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - offset)
                    ret, frame = cap.read()
                    if ret:
                        break

            if not ret:
                print(f"无法读取视频最后一帧: {video_path}")
                return None

            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # 保存为 PNG
            cv2.imwrite(output_path, frame)
            return output_path

        finally:
            cap.release()

    @staticmethod
    def extract_frame_at(video_path: str, timestamp: float, output_path: str) -> Optional[str]:
        """
        提取指定时间戳的帧

        Args:
            video_path: 视频文件路径
            timestamp: 时间戳（秒）
            output_path: 输出图片路径

        Returns:
            成功返回输出路径，失败返回 None
        """
        try:
            import cv2
        except ImportError:
            print("opencv-python-headless 未安装，无法提取视频帧")
            return None

        if not os.path.exists(video_path):
            print(f"视频文件不存在: {video_path}")
            return None

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"无法打开视频: {video_path}")
            return None

        try:
            # 转换为毫秒并定位
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ret, frame = cap.read()

            if not ret:
                print(f"无法读取时间戳 {timestamp}s 处的帧: {video_path}")
                return None

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cv2.imwrite(output_path, frame)
            return output_path

        finally:
            cap.release()

    @staticmethod
    def get_video_info(video_path: str) -> Dict[str, Any]:
        """
        获取视频信息

        Args:
            video_path: 视频文件路径

        Returns:
            包含 duration, width, height, fps, frame_count 的字典
        """
        try:
            import cv2
        except ImportError:
            return {'error': 'opencv-python-headless 未安装'}

        if not os.path.exists(video_path):
            return {'error': f'文件不存在: {video_path}'}

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {'error': f'无法打开视频: {video_path}'}

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0

            return {
                'duration': duration,
                'width': width,
                'height': height,
                'fps': fps,
                'frame_count': frame_count,
            }
        finally:
            cap.release()
