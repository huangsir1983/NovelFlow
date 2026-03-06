"""
涛割 - SceneProcessor 单元测试
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from services.scene.processor import SceneProcessor, SubtitleSegment, SceneGroup


# ==================== 测试数据 ====================

SAMPLE_SRT = """1
00:00:00,000 --> 00:00:03,000
大家好，欢迎来到这个故事

2
00:00:03,500 --> 00:00:06,000
今天我要给大家讲一个传说

3
00:00:06,500 --> 00:00:09,000
很久很久以前，有一个王国

4
00:00:09,500 --> 00:00:12,000
meanwhile 另一边，敌人正在集结

5
00:00:12,500 --> 00:00:15,500
国王决定派勇士出征

6
00:00:16,000 --> 00:00:18,000
勇士踏上了旅途
"""


class TestSrtTimeConversion:
    """SRT时间格式转换测试"""

    def test_srt_time_to_microseconds(self):
        assert SceneProcessor.srt_time_to_microseconds("00:00:00,000") == 0
        assert SceneProcessor.srt_time_to_microseconds("00:00:01,000") == 1_000_000
        assert SceneProcessor.srt_time_to_microseconds("00:01:00,000") == 60_000_000
        assert SceneProcessor.srt_time_to_microseconds("01:00:00,000") == 3_600_000_000
        assert SceneProcessor.srt_time_to_microseconds("00:00:00,500") == 500_000

    def test_microseconds_to_srt_time(self):
        assert SceneProcessor.microseconds_to_srt_time(0) == "00:00:00,000"
        assert SceneProcessor.microseconds_to_srt_time(1_000_000) == "00:00:01,000"
        assert SceneProcessor.microseconds_to_srt_time(60_000_000) == "00:01:00,000"
        assert SceneProcessor.microseconds_to_srt_time(3_600_000_000) == "01:00:00,000"
        assert SceneProcessor.microseconds_to_srt_time(500_000) == "00:00:00,500"

    def test_roundtrip_conversion(self):
        """往返转换测试"""
        times = [
            "00:00:00,000", "00:01:23,456", "01:30:45,789", "00:00:05,500"
        ]
        for t in times:
            us = SceneProcessor.srt_time_to_microseconds(t)
            result = SceneProcessor.microseconds_to_srt_time(us)
            assert result == t, f"往返转换失败: {t} -> {us} -> {result}"


class TestSrtParsing:
    """SRT解析测试"""

    def test_parse_srt_basic(self):
        processor = SceneProcessor()
        segments = processor.parse_srt(SAMPLE_SRT)

        assert len(segments) == 6
        assert segments[0].index == 1
        assert segments[0].text == "大家好，欢迎来到这个故事"
        assert segments[0].start == "00:00:00,000"
        assert segments[0].end == "00:00:03,000"

    def test_parse_srt_timing(self):
        processor = SceneProcessor()
        segments = processor.parse_srt(SAMPLE_SRT)

        # 第一段时长应为3秒
        assert segments[0].duration == 3.0
        # 第二段时长应为2.5秒
        assert segments[1].duration == 2.5

    def test_parse_srt_empty(self):
        processor = SceneProcessor()
        segments = processor.parse_srt("")
        assert segments == []

    def test_parse_srt_file(self):
        processor = SceneProcessor()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt',
                                          delete=False, encoding='utf-8') as f:
            f.write(SAMPLE_SRT)
            f.flush()

            segments = processor.parse_srt_file(f.name)
            assert len(segments) == 6

        os.unlink(f.name)


class TestSceneGrouping:
    """场景分组测试"""

    def setup_method(self):
        self.processor = SceneProcessor(
            default_scene_duration=3.5,
            min_scene_duration=2.0,
            max_scene_duration=6.0
        )
        self.segments = self.processor.parse_srt(SAMPLE_SRT)

    def test_group_by_duration(self):
        groups = self.processor.group_segments(self.segments, strategy="duration")
        assert len(groups) > 0

        # 所有段落应被包含
        total_segs = sum(len(g.segments) for g in groups)
        assert total_segs == len(self.segments)

    def test_group_by_content(self):
        groups = self.processor.group_segments(self.segments, strategy="content")
        assert len(groups) > 0

        # "meanwhile" 应触发分组
        assert len(groups) >= 2

    def test_group_fixed(self):
        groups = self.processor.group_segments(self.segments, strategy="fixed")
        # 固定分组，每段一组
        assert len(groups) == len(self.segments)

    def test_group_default_strategy(self):
        groups = self.processor.group_segments(self.segments, strategy="unknown")
        # 默认：每段一组
        assert len(groups) == len(self.segments)

    def test_group_empty(self):
        groups = self.processor.group_segments([], strategy="duration")
        assert groups == []


class TestSceneGroup:
    """SceneGroup数据类测试"""

    def test_scene_group_properties(self):
        seg1 = SubtitleSegment(
            index=1, start="00:00:00,000", end="00:00:03,000",
            text="测试", start_microseconds=0, end_microseconds=3_000_000
        )
        seg2 = SubtitleSegment(
            index=2, start="00:00:03,000", end="00:00:05,000",
            text="文本", start_microseconds=3_000_000, end_microseconds=5_000_000
        )

        group = SceneGroup(segments=[seg1, seg2])

        assert group.start_time == "00:00:00,000"
        assert group.end_time == "00:00:05,000"
        assert group.duration == 5.0
        assert group.full_text == "测试 文本"

    def test_scene_group_to_dict(self):
        seg = SubtitleSegment(
            index=1, start="00:00:00,000", end="00:00:03,000",
            text="测试", start_microseconds=0, end_microseconds=3_000_000
        )
        group = SceneGroup(segments=[seg])

        d = group.to_dict()
        assert "segments" in d
        assert "start_time" in d
        assert "end_time" in d
        assert "duration" in d
        assert d["duration"] == 3.0


class TestMergeAndSplit:
    """分组合并与拆分测试"""

    def setup_method(self):
        self.processor = SceneProcessor()
        self.segments = self.processor.parse_srt(SAMPLE_SRT)
        self.groups = self.processor.group_segments(self.segments, strategy="fixed")

    def test_merge_groups(self):
        original_count = len(self.groups)
        merged = self.processor.merge_groups(self.groups, [0, 1])

        # 合并后应该少一组
        assert len(merged) < original_count

    def test_merge_single_index(self):
        # 单个索引不应合并
        result = self.processor.merge_groups(self.groups, [0])
        assert len(result) == len(self.groups)

    def test_merge_empty_indices(self):
        result = self.processor.merge_groups(self.groups, [])
        assert len(result) == len(self.groups)

    def test_split_group(self):
        group = self.groups[0] if self.groups else SceneGroup(segments=self.segments[:3])

        if len(group.segments) > 1:
            first, second = self.processor.split_group(group, 1)
            assert len(first.segments) == 1
            assert len(second.segments) == len(group.segments) - 1

    def test_split_at_boundary(self):
        group = SceneGroup(segments=self.segments[:3])
        first, second = self.processor.split_group(group, 0)
        assert first == group
        assert second.segments == []


class TestTotalDuration:
    """总时长计算测试"""

    def test_calculate_total_duration(self):
        processor = SceneProcessor()
        segments = processor.parse_srt(SAMPLE_SRT)
        groups = processor.group_segments(segments, strategy="fixed")

        duration = processor.calculate_total_duration(groups)
        assert duration > 0

    def test_calculate_empty_duration(self):
        processor = SceneProcessor()
        assert processor.calculate_total_duration([]) == 0.0
