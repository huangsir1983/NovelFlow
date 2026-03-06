"""
涛割 - 帧提取工具测试
"""

import os
import tempfile
import pytest


class TestFrameExtractor:
    """测试 FrameExtractor"""

    def test_import(self):
        """测试模块可正常导入"""
        from services.utils.frame_extractor import FrameExtractor
        assert FrameExtractor is not None

    def test_get_video_info_nonexistent(self):
        """测试不存在的视频文件"""
        from services.utils.frame_extractor import FrameExtractor
        info = FrameExtractor.get_video_info("/nonexistent/video.mp4")
        assert 'error' in info

    def test_extract_last_frame_nonexistent(self):
        """测试从不存在的视频提取帧"""
        from services.utils.frame_extractor import FrameExtractor
        result = FrameExtractor.extract_last_frame(
            "/nonexistent/video.mp4",
            "/tmp/output.png"
        )
        assert result is None

    def test_extract_frame_at_nonexistent(self):
        """测试从不存在的视频提取指定时间戳帧"""
        from services.utils.frame_extractor import FrameExtractor
        result = FrameExtractor.extract_frame_at(
            "/nonexistent/video.mp4",
            1.0,
            "/tmp/output.png"
        )
        assert result is None

    @pytest.mark.skipif(
        not _cv2_available(),
        reason="opencv-python-headless 未安装"
    )
    def test_extract_from_real_video(self, tmp_path):
        """测试从真实视频提取帧（需要 opencv）"""
        import cv2
        import numpy as np

        # 创建一个简短的测试视频
        video_path = str(tmp_path / "test.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_path, fourcc, 10, (320, 240))

        # 写 10 帧（蓝、绿、红交替）
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        for i in range(10):
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            frame[:] = colors[i % 3]
            out.write(frame)
        out.release()

        from services.utils.frame_extractor import FrameExtractor

        # 测试视频信息
        info = FrameExtractor.get_video_info(video_path)
        assert info['frame_count'] == 10
        assert info['width'] == 320
        assert info['height'] == 240
        assert info['fps'] == 10

        # 测试提取最后一帧
        output_path = str(tmp_path / "last_frame.png")
        result = FrameExtractor.extract_last_frame(video_path, output_path)
        assert result is not None
        assert os.path.exists(result)

        # 测试提取指定时间戳帧
        output_path2 = str(tmp_path / "frame_at.png")
        result2 = FrameExtractor.extract_frame_at(video_path, 0.5, output_path2)
        assert result2 is not None
        assert os.path.exists(result2)


def _cv2_available():
    """检查 opencv 是否可用"""
    try:
        import cv2
        return True
    except ImportError:
        return False
