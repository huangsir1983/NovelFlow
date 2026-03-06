"""
涛割 - 场景处理器
负责剧本/SRT解析和场景拆分
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class SubtitleSegment:
    """字幕段落"""
    index: int
    start: str  # SRT格式时间 "00:00:00,000"
    end: str
    text: str
    start_microseconds: int = 0
    end_microseconds: int = 0
    image_paths: List[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """获取时长（秒）"""
        return (self.end_microseconds - self.start_microseconds) / 1_000_000


@dataclass
class SceneGroup:
    """场景分组"""
    segments: List[SubtitleSegment]
    image_paths: List[str] = field(default_factory=list)
    ai_tags: Dict[str, List[str]] = field(default_factory=lambda: {
        "场景": [],
        "角色": [],
        "道具": [],
        "特效": []
    })

    @property
    def start_time(self) -> str:
        """获取起始时间"""
        return self.segments[0].start if self.segments else "00:00:00,000"

    @property
    def end_time(self) -> str:
        """获取结束时间"""
        return self.segments[-1].end if self.segments else "00:00:00,000"

    @property
    def start_microseconds(self) -> int:
        return self.segments[0].start_microseconds if self.segments else 0

    @property
    def end_microseconds(self) -> int:
        return self.segments[-1].end_microseconds if self.segments else 0

    @property
    def duration(self) -> float:
        """获取总时长（秒）"""
        return (self.end_microseconds - self.start_microseconds) / 1_000_000

    @property
    def full_text(self) -> str:
        """获取完整文本"""
        return " ".join(seg.text for seg in self.segments)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segments": [
                {
                    "index": s.index,
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "image_paths": s.image_paths
                }
                for s in self.segments
            ],
            "image_paths": self.image_paths,
            "ai_tags": self.ai_tags,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
        }


class SceneProcessor:
    """
    场景处理器
    负责解析SRT/剧本并拆分为场景
    """

    def __init__(
        self,
        default_scene_duration: float = 3.5,
        min_scene_duration: float = 2.0,
        max_scene_duration: float = 6.0
    ):
        self.default_scene_duration = default_scene_duration
        self.min_scene_duration = min_scene_duration
        self.max_scene_duration = max_scene_duration

    def parse_srt(self, srt_content: str) -> List[SubtitleSegment]:
        """
        解析SRT字幕文件内容

        Args:
            srt_content: SRT文件内容

        Returns:
            List[SubtitleSegment]: 解析后的字幕段落列表
        """
        segments = []

        # SRT正则匹配
        pattern = re.compile(
            r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\n*$)',
            re.DOTALL
        )

        matches = pattern.findall(srt_content)

        for match in matches:
            index, start, end, text = match
            text = text.strip().replace('\n', ' ')

            segment = SubtitleSegment(
                index=int(index),
                start=start,
                end=end,
                text=text,
                start_microseconds=self.srt_time_to_microseconds(start),
                end_microseconds=self.srt_time_to_microseconds(end),
                image_paths=[]
            )
            segments.append(segment)

        return segments

    def parse_srt_file(self, file_path: str) -> List[SubtitleSegment]:
        """
        从文件解析SRT

        Args:
            file_path: SRT文件路径

        Returns:
            List[SubtitleSegment]: 解析后的字幕段落列表
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return self.parse_srt(content)

    def group_segments(
        self,
        segments: List[SubtitleSegment],
        strategy: str = "duration"
    ) -> List[SceneGroup]:
        """
        将字幕段落分组为场景

        Args:
            segments: 字幕段落列表
            strategy: 分组策略 ("duration", "content", "fixed")

        Returns:
            List[SceneGroup]: 场景分组列表
        """
        if not segments:
            return []

        if strategy == "duration":
            return self._group_by_duration(segments)
        elif strategy == "content":
            return self._group_by_content(segments)
        elif strategy == "fixed":
            return self._group_fixed(segments)
        else:
            # 默认：每个字幕一个场景
            return [SceneGroup(segments=[seg]) for seg in segments]

    def _group_by_duration(self, segments: List[SubtitleSegment]) -> List[SceneGroup]:
        """按时长分组，确保每组时长在合理范围内"""
        groups = []
        current_segments = []
        current_duration = 0.0

        for segment in segments:
            seg_duration = segment.duration

            # 如果添加这个段落会超过最大时长
            if current_duration + seg_duration > self.max_scene_duration and current_segments:
                groups.append(SceneGroup(segments=current_segments.copy()))
                current_segments = []
                current_duration = 0.0

            current_segments.append(segment)
            current_duration += seg_duration

            # 如果达到理想时长，考虑分组
            if current_duration >= self.default_scene_duration:
                groups.append(SceneGroup(segments=current_segments.copy()))
                current_segments = []
                current_duration = 0.0

        # 处理剩余段落
        if current_segments:
            # 如果剩余太短，合并到上一组
            if current_duration < self.min_scene_duration and groups:
                groups[-1].segments.extend(current_segments)
            else:
                groups.append(SceneGroup(segments=current_segments))

        return groups

    def _group_by_content(self, segments: List[SubtitleSegment]) -> List[SceneGroup]:
        """
        按内容分组（简单实现：检测对话变化）
        实际应用中可以用AI分析内容切换点
        """
        groups = []
        current_segments = []

        # 用于检测内容变化的标记词
        scene_change_markers = ['meanwhile', '同时', '另一边', '与此同时', '切换', '转场']

        for segment in segments:
            text_lower = segment.text.lower()

            # 检测是否应该开始新场景
            should_split = False
            for marker in scene_change_markers:
                if marker in text_lower:
                    should_split = True
                    break

            if should_split and current_segments:
                groups.append(SceneGroup(segments=current_segments.copy()))
                current_segments = []

            current_segments.append(segment)

        # 处理剩余
        if current_segments:
            groups.append(SceneGroup(segments=current_segments))

        return groups

    def _group_fixed(self, segments: List[SubtitleSegment], group_size: int = 1) -> List[SceneGroup]:
        """固定数量分组"""
        groups = []
        for i in range(0, len(segments), group_size):
            group_segments = segments[i:i + group_size]
            groups.append(SceneGroup(segments=group_segments))
        return groups

    def merge_groups(self, groups: List[SceneGroup], indices: List[int]) -> List[SceneGroup]:
        """
        合并指定索引的分组

        Args:
            groups: 原始分组列表
            indices: 要合并的分组索引列表（按顺序）

        Returns:
            List[SceneGroup]: 合并后的分组列表
        """
        if not indices or len(indices) < 2:
            return groups

        indices = sorted(set(indices))
        result = []
        merged_segments = []
        merged_images = []
        merged_tags = {"场景": [], "角色": [], "道具": [], "特效": []}

        for i, group in enumerate(groups):
            if i in indices:
                merged_segments.extend(group.segments)
                merged_images.extend(group.image_paths)
                # 合并标签
                for key in merged_tags:
                    merged_tags[key].extend(group.ai_tags.get(key, []))
            else:
                if i > max(indices) and merged_segments:
                    # 先添加合并的组
                    merged_group = SceneGroup(
                        segments=merged_segments,
                        image_paths=list(set(merged_images)),
                        ai_tags={k: list(set(v)) for k, v in merged_tags.items()}
                    )
                    result.append(merged_group)
                    merged_segments = []
                    merged_images = []
                    merged_tags = {"场景": [], "角色": [], "道具": [], "特效": []}
                result.append(group)

        # 处理末尾的合并组
        if merged_segments:
            merged_group = SceneGroup(
                segments=merged_segments,
                image_paths=list(set(merged_images)),
                ai_tags={k: list(set(v)) for k, v in merged_tags.items()}
            )
            result.append(merged_group)

        return result

    def split_group(self, group: SceneGroup, split_index: int) -> Tuple[SceneGroup, SceneGroup]:
        """
        拆分一个分组

        Args:
            group: 要拆分的分组
            split_index: 拆分位置（第一组包含0到split_index-1）

        Returns:
            Tuple[SceneGroup, SceneGroup]: 拆分后的两个分组
        """
        if split_index <= 0 or split_index >= len(group.segments):
            return (group, SceneGroup(segments=[]))

        first_segments = group.segments[:split_index]
        second_segments = group.segments[split_index:]

        first_group = SceneGroup(
            segments=first_segments,
            image_paths=group.image_paths.copy(),
            ai_tags={k: v.copy() for k, v in group.ai_tags.items()}
        )

        second_group = SceneGroup(
            segments=second_segments,
            image_paths=[],
            ai_tags={"场景": [], "角色": [], "道具": [], "特效": []}
        )

        return (first_group, second_group)

    @staticmethod
    def srt_time_to_microseconds(srt_time: str) -> int:
        """
        将SRT时间格式转换为微秒

        Args:
            srt_time: SRT时间格式 "HH:MM:SS,mmm"

        Returns:
            int: 微秒数
        """
        h, m, s_ms = srt_time.split(':')
        s, ms = s_ms.split(',')
        total_microseconds = (int(h) * 3600 + int(m) * 60 + int(s)) * 1_000_000 + int(ms) * 1000
        return total_microseconds

    @staticmethod
    def microseconds_to_srt_time(microseconds: int) -> str:
        """
        将微秒转换为SRT时间格式

        Args:
            microseconds: 微秒数

        Returns:
            str: SRT时间格式 "HH:MM:SS,mmm"
        """
        seconds = microseconds // 1_000_000
        ms = (microseconds % 1_000_000) // 1000
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def calculate_total_duration(self, groups: List[SceneGroup]) -> float:
        """计算总时长（秒）"""
        if not groups:
            return 0.0
        return (groups[-1].end_microseconds - groups[0].start_microseconds) / 1_000_000

    # ==================== 文件导入 ====================

    @staticmethod
    def parse_txt_file(path: str, encoding: str = None) -> str:
        """读取 TXT 文件，自动检测编码"""
        encodings = [encoding] if encoding else ['utf-8', 'gbk', 'utf-16', 'gb2312', 'big5']
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ValueError(f"无法识别文件编码: {path}")

    @staticmethod
    def parse_docx_file(path: str) -> str:
        """读取 Word (.docx) 文件"""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")

        doc = Document(path)
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)
        return '\n'.join(paragraphs)

    @staticmethod
    def parse_pdf_file(path: str) -> str:
        """读取 PDF 文件"""
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            raise ImportError("请安装 PyPDF2: pip install PyPDF2")

        reader = PdfReader(path)
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())
        return '\n'.join(pages_text)

    @staticmethod
    def parse_file(path: str) -> str:
        """根据文件扩展名自动选择解析器"""
        ext = path.lower().rsplit('.', 1)[-1] if '.' in path else ''
        if ext == 'txt':
            return SceneProcessor.parse_txt_file(path)
        elif ext == 'docx':
            return SceneProcessor.parse_docx_file(path)
        elif ext == 'pdf':
            return SceneProcessor.parse_pdf_file(path)
        else:
            # 尝试作为纯文本读取
            return SceneProcessor.parse_txt_file(path)

    @staticmethod
    def parse_plain_text_to_acts(text: str) -> List[Dict[str, Any]]:
        """
        按场景（物理空间变化）拆分文本为 Act。
        优先识别章节/场景标记，其次检测地点转换关键词，
        最后按段落分组兜底。对话过程不拆分。

        Returns:
            [{title, text, start_char, end_char}]
        """
        import re

        # 1) 章节/场景标记正则
        chapter_pattern = re.compile(
            r'^(?:第[一二三四五六七八九十百千\d]+[章节幕场回]|'
            r'Chapter\s*\d+|Scene\s*\d+|'
            r'[=]{3,}|[-]{3,}|'
            r'[【\[]\s*(?:第.+?[章节幕场回]|场景|场次).+?[】\]])'
            r'[\s：:]*(.*)$',
            re.MULTILINE | re.IGNORECASE
        )

        matches = list(chapter_pattern.finditer(text))

        acts = []
        if matches:
            for i, match in enumerate(matches):
                start = match.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                title_line = match.group(0).strip()
                body = text[start:end].strip()
                acts.append({
                    'title': title_line[:50],
                    'text': body,
                    'start_char': start,
                    'end_char': end,
                })
            return acts

        # 2) 无章节标记：按地点转换关键词检测场景切换
        # 常见的场景转换信号词
        scene_change_pattern = re.compile(
            r'(?:^|\n)\s*(?:'
            r'(?:来到|走进|走出|走到|回到|跑到|赶到|到了|进入|离开|'
            r'推开|踏入|走入|抵达|转身走向|出了|去了|奔向|冲进|冲出|'
            r'坐在|站在|躺在)[\w]{0,10}(?:门|里|中|外|旁|上|下|前|后|处|边)|'
            r'(?:第二天|次日|翌日|隔天|那天|当天|几天后|一周后|'
            r'三年后|多年后|不久后|那晚|那天晚上|清晨|傍晚|夜里|午后|黄昏)|'
            r'(?:另一边|与此同时|此时此刻|在另一个|画面切到|镜头转到)'
            r')',
            re.MULTILINE
        )

        # 按段落处理
        paragraphs = re.split(r'\n\s*\n', text)
        if not paragraphs:
            return [{'title': '场景 1', 'text': text, 'start_char': 0, 'end_char': len(text)}]

        current_group = []
        current_start = 0
        offset = 0

        for para in paragraphs:
            para_stripped = para.strip()
            if not para_stripped:
                offset += len(para) + 1
                continue

            start = text.find(para_stripped, offset)
            if start == -1:
                start = offset

            # 检测是否此段落包含场景转换信号
            has_scene_change = bool(scene_change_pattern.search(para_stripped))

            # 如果检测到场景转换且已有积累的段落，先保存之前的场景
            if has_scene_change and current_group:
                group_text = '\n'.join(current_group)
                acts.append({
                    'title': f'场景 {len(acts) + 1}',
                    'text': group_text,
                    'start_char': current_start,
                    'end_char': start,
                })
                current_group = []
                current_start = start

            if not current_group:
                current_start = start

            current_group.append(para_stripped)
            offset = start + len(para_stripped)

        # 处理最后一组
        if current_group:
            group_text = '\n'.join(current_group)
            acts.append({
                'title': f'场景 {len(acts) + 1}',
                'text': group_text,
                'start_char': current_start,
                'end_char': len(text),
            })

        # 兜底：如果没有检测到任何切换点，整个文本作为一个场景
        if not acts:
            acts = [{'title': '场景 1', 'text': text, 'start_char': 0, 'end_char': len(text)}]

        return acts

    @staticmethod
    def split_act_text_to_shots(
        act_text: str,
        target_duration: float = 10.0
    ) -> List[Dict[str, Any]]:
        """
        将场次文本按镜头切换点拆分为分镜单元。
        核心策略：按说话人/动作主体切换来拆分，而非单纯按字数累积。
        - 对话引号对内不拆开（同一人说的话保持在一个分镜）
        - 不同人说话切换时拆分（镜头需要切到另一个人）
        - 叙述段与对话段之间拆分
        - 过长的单一叙述段按句号断句累积到目标字数后切分

        Args:
            act_text: 场次文本
            target_duration: 目标时长（秒）

        Returns:
            [{"subtitle_text": "...", "duration": 10.0}]
        """
        import re

        if not act_text or not act_text.strip():
            return [{'subtitle_text': act_text, 'duration': target_duration}]

        chars_per_second = 4  # 中文朗读约 4 字/秒
        target_chars = int(target_duration * chars_per_second)
        min_chars = max(15, target_chars // 3)  # 最小分镜字数，防止碎片分镜

        # 第一步：将文本拆分为"段元素"（对话块 / 叙述句）
        # 对话块：引号对包裹的内容（含引号前的说话人标记）
        # 叙述句：非对话的普通叙述，按句号断句
        elements = []

        # 匹配对话块：可能有 "XXX说/道/喊" 等前导 + 引号对内容
        # 支持：「」『』""''""''
        dialogue_pattern = re.compile(
            r'([^「『""\u201c\u2018。！？.!?\n]*?'  # 前导（说话人标记，非贪婪）
            r'[：:]?\s*)'                            # 可选冒号
            r'([「『""\u201c\u2018]'                 # 开引号
            r'[^」』""\u201d\u2019]*'                # 引号内容
            r'[」』""\u201d\u2019])'                  # 闭引号
            r'([^「『""\u201c\u2018]*?'              # 后续（如"他叹了口气"）
            r'(?=[「『""\u201c\u2018]|\Z|(?<=[。！？.!?\n])))'
        )

        last_end = 0
        for m in dialogue_pattern.finditer(act_text):
            # m.start() 之前的非对话文本
            before = act_text[last_end:m.start()].strip()
            if before:
                elements.append(('narration', before))

            # 对话块（前导 + 引号内容 + 后续）
            dialogue_full = m.group(0).strip()
            if dialogue_full:
                elements.append(('dialogue', dialogue_full))

            last_end = m.end()

        # 剩余的尾部文本
        tail = act_text[last_end:].strip()
        if tail:
            elements.append(('narration', tail))

        # 如果没有对话块，退回到按句子断句
        if not elements:
            sentences = re.split(r'(?<=[。！？.!?\n])\s*', act_text)
            sentences = [s.strip() for s in sentences if s.strip()]
            if not sentences:
                return [{'subtitle_text': act_text, 'duration': target_duration}]
            for s in sentences:
                elements.append(('narration', s))

        # 第二步：按镜头切换逻辑合并段元素为分镜
        # 核心原则：把整个场次文本当作整体来拆分，不产出碎片分镜
        shots = []
        current_text_parts = []
        current_chars = 0
        current_type = None  # 'dialogue' or 'narration'

        def _flush_shot():
            nonlocal current_text_parts, current_chars, current_type
            if current_text_parts:
                shot_text = ''.join(current_text_parts)
                shot_duration = max(3.0, min(15.0, len(shot_text) / chars_per_second))
                shots.append({
                    'subtitle_text': shot_text,
                    'duration': round(shot_duration, 1),
                })
                current_text_parts = []
                current_chars = 0
                current_type = None

        for elem_type, elem_text in elements:
            # 镜头切换条件：
            # 1. 类型切换（叙述 → 对话，或 对话 → 叙述）
            # 2. 对话 → 对话（不同说话人，即两段不同的对话块）
            # 3. 叙述段累积超过目标字数
            # 但：如果当前累积字数太少（低于 min_chars），不切，继续合并
            should_cut = False

            if current_type is None:
                # 第一个元素，不切
                pass
            elif current_chars < min_chars:
                # 当前累积太短，不切镜头，继续合并（防止碎片分镜）
                pass
            elif elem_type == 'dialogue' and current_type == 'dialogue':
                # 对话 → 对话：不同说话人，切镜头（但前提是已有足够内容）
                should_cut = True
            elif elem_type != current_type:
                # 类型切换：叙述↔对话
                should_cut = True
            elif elem_type == 'narration' and current_chars + len(elem_text) > target_chars * 1.5:
                # 叙述段过长，切分
                should_cut = True

            if should_cut:
                _flush_shot()

            current_text_parts.append(elem_text)
            current_chars += len(elem_text)
            current_type = elem_type

            # 累积超过目标字数时切分
            if current_chars >= target_chars:
                _flush_shot()

        _flush_shot()

        # 安全兜底：如果拆分结果为空
        if not shots:
            shots = [{'subtitle_text': act_text, 'duration': target_duration}]

        return shots
