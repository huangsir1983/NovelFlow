"""Streaming JSON parser for Mode C progressive asset extraction.

Provides:
- ProgressiveAssetParser: incremental character/scene extraction from streaming JSON
- extract_json_robust(): multi-strategy JSON extraction with truncation recovery
- is_truncated(): detect incomplete AI responses
- estimate_max_tokens(): adaptive token budget based on input length

Ported from: 测试/第10轮测试结果/run_test_round10.py (lines 615-890)
"""

import json
import re
import logging

logger = logging.getLogger(__name__)


class ProgressiveAssetParser:
    """Multi-phase progressive parser — scans characters → scenes arrays in order.

    Expected format: {"characters": [{...}, {...}], "scenes": [{...}, {...}]}
    Yields individual character/scene objects as they complete during streaming.
    Handles <think> tags interleaved in streaming output.

    Key design: scenes are NARRATIVE SCENES (ordered story events), not locations.
    The same location may appear in multiple scenes with different events.
    """

    def __init__(self):
        self.buffer = ""
        self.found_chars = []       # Extracted character objects
        self.found_scenes = []      # Extracted narrative scene objects
        self._chars_closed = False  # characters array closed?
        self._scenes_closed = False  # scenes array closed?
        self._scan_pos = 0          # Incremental scan position

        # Current array scanning state
        self._in_array = False
        self._array_key = None      # "characters" or "scenes"
        self._obj_start = -1
        self._depth = 0

    def feed(self, chunk: str) -> dict:
        """Feed a streaming chunk, return newly discovered assets.

        Returns:
            {"characters": [...new_chars], "scenes": [...new_scenes]}
        """
        self.buffer += chunk
        self.buffer = self._clean(self.buffer)
        result = {"characters": [], "scenes": []}

        if not self._chars_closed:
            new_chars = self._scan_array("characters")
            result["characters"] = new_chars
            self.found_chars.extend(new_chars)

        if self._chars_closed and not self._scenes_closed:
            # B3.2: Once chars array is closed, truncate buffer to reduce memory.
            # Preserve any in-progress object to avoid cutting it in half.
            if self._scan_pos > 1000:
                if self._obj_start >= 0:
                    # An object is being parsed — truncate up to its start
                    offset = self._obj_start
                else:
                    # No object in progress — safe to discard up to scan_pos
                    offset = self._scan_pos
                self.buffer = self.buffer[offset:]
                self._scan_pos -= offset
                if self._obj_start >= 0:
                    self._obj_start -= offset

            new_scenes = self._scan_array("scenes")
            result["scenes"] = new_scenes
            self.found_scenes.extend(new_scenes)

        return result

    def _scan_array(self, key: str) -> list[dict]:
        """Generic array scanner — find complete JSON objects from _scan_pos."""
        found = []
        buf = self.buffer
        pos = self._scan_pos

        while pos < len(buf):
            ch = buf[pos]

            if not self._in_array:
                marker = f'"{key}"'
                idx = buf.find(marker, pos)
                if idx < 0:
                    break
                bracket_pos = buf.find('[', idx + len(marker))
                if bracket_pos < 0:
                    break
                self._in_array = True
                self._array_key = key
                pos = bracket_pos + 1
                continue

            # Inside array — track { } depth
            if ch == '{':
                if self._depth == 0:
                    self._obj_start = pos
                self._depth += 1
            elif ch == '}':
                self._depth -= 1
                if self._depth == 0 and self._obj_start >= 0:
                    obj_str = buf[self._obj_start:pos + 1]
                    obj_str = self._fix_json_str(obj_str)
                    try:
                        obj = json.loads(obj_str, strict=False)
                        found.append(obj)
                    except json.JSONDecodeError:
                        pass
                    self._obj_start = -1
            elif ch == ']' and self._depth == 0:
                # Array closed
                self._in_array = False
                self._array_key = None
                if key == "characters":
                    self._chars_closed = True
                elif key == "scenes":
                    self._scenes_closed = True
                pos += 1
                break
            pos += 1

        self._scan_pos = pos
        return found

    def get_checkpoint(self) -> dict:
        """Return current parser state as a checkpoint for stream recovery (加固1)."""
        return {
            "found_chars": [c.get("name", "") for c in self.found_chars],
            "found_scenes": [s.get("scene_id", s.get("location", "")) for s in self.found_scenes],
            "chars_closed": self._chars_closed,
            "scenes_closed": self._scenes_closed,
            "char_count": len(self.found_chars),
            "scene_count": len(self.found_scenes),
        }

    def is_chars_complete(self) -> bool:
        """Check if the characters array has been fully parsed (加固1)."""
        return self._chars_closed

    @staticmethod
    def _clean(text: str) -> str:
        """Strip think tags, handle unclosed tags, and remove markdown code fences."""
        text = re.sub(r'<think>[\s\S]*?</think>', '', text)
        text = re.sub(r'\[Agent\s*\d*\]\[AgentThink\][\s\S]*?\[/AgentThink\]', '', text)
        text = re.sub(r'\[Agent \d+\]\[AgentThink\][^\n]*\n?', '', text)
        # Handle unclosed <think> tag — truncate to before it (加固2)
        idx = text.rfind('<think>')
        if idx >= 0 and '</think>' not in text[idx:]:
            text = text[:idx]
        # Strip markdown code fences (ChatGPT frequently wraps JSON in ```json...```)
        text = re.sub(r'```json\s*\n?', '', text)
        text = re.sub(r'```\s*$', '', text)
        return text

    @staticmethod
    def _fix_json_str(s: str) -> str:
        """Fix bare newlines and broken numbers in JSON string."""
        fixed = s
        for _ in range(10):
            prev = fixed
            fixed = re.sub(
                r'("(?:[^"\\]|\\.)*?)\n((?:[^"\\]|\\.)*?")',
                r'\1 \2', fixed)
            if fixed == prev:
                break
        fixed = re.sub(r'(\d)\s+\.(\d)', r'\1.\2', fixed)
        return fixed


# ─── Robust JSON extraction ───────────────────────────────────────


def extract_json_robust(raw: str):
    """Extract JSON from model response with multi-strategy fallback.

    Handles: thinking tags, code blocks, bare newlines, truncation.
    Ported from run_test_round10.py extract_json() (lines 615-694).
    """
    # Strip <think> tags
    text = re.sub(r'<think>[\s\S]*?</think>', ' ', raw)
    text = re.sub(r'\[Agent\s*\d*\]\[AgentThink\][\s\S]*?\[/AgentThink\]', ' ', text)

    # Extract from code blocks (prefer the LAST one)
    blocks = list(re.finditer(r'```(?:json)?\s*([\s\S]*?)```', text))
    if blocks:
        text = blocks[-1].group(1).strip()
    else:
        text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fix 1: bare newlines inside JSON strings
    cleaned = text
    for _ in range(10):
        prev = cleaned
        cleaned = re.sub(r'("(?:[^"\\]|\\.)*?)\n((?:[^"\\]|\\.)*?")',
                         r'\1 \2', cleaned)
        if cleaned == prev:
            break
    # Fix 2: broken numbers (e.g. "0  .65" → "0.65")
    cleaned = re.sub(r'(\d)\s+\.(\d)', r'\1.\2', cleaned)
    # Fix 3: extra spaces around colons
    cleaned = re.sub(r':\s{2,}', ': ', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: find first [ or { in cleaned text
    for src in [cleaned, text]:
        for i, ch in enumerate(src):
            if ch in '[{':
                remainder = src[i:]
                try:
                    return json.loads(remainder)
                except json.JSONDecodeError:
                    end_ch = ']' if ch == '[' else '}'
                    last = remainder.rfind(end_ch)
                    if last > 0:
                        try:
                            return json.loads(remainder[:last + 1])
                        except json.JSONDecodeError:
                            pass
                break

    # Truncation repair: try to close incomplete JSON
    for src in [cleaned, text]:
        for i, ch in enumerate(src):
            if ch == '{':
                remainder = src[i:]
                for suffix in ['}]}', ']}', '}]}}', ']}}', '}}']:
                    try:
                        return json.loads(remainder + suffix)
                    except json.JSONDecodeError:
                        pass
                # Last resort: extract complete objects from partial array
                try:
                    partial = _extract_partial_json(remainder)
                    if partial:
                        return partial
                except Exception:
                    pass
                break

    raise ValueError(f"Cannot extract JSON (len={len(raw)}, preview={raw[:200]!r})")


def _extract_partial_json(text: str) -> dict | None:
    """Extract characters and scenes from truncated JSON."""
    result = {}
    m = re.search(r'"characters"\s*:\s*\[', text)
    if m:
        chars = _extract_complete_objects(text, m.end())
        if chars:
            result["characters"] = chars
    m = re.search(r'"scenes"\s*:\s*\[', text)
    if m:
        scenes = _extract_complete_objects(text, m.end())
        if scenes:
            result["scenes"] = scenes
    return result if result else None


def _extract_complete_objects(text: str, start: int) -> list:
    """Extract all complete JSON objects from an array starting at `start`."""
    pos = start
    found = []
    while pos < len(text):
        while pos < len(text) and text[pos] in ' \t\n\r,':
            pos += 1
        if pos >= len(text) or text[pos] == ']':
            break
        if text[pos] != '{':
            pos += 1
            continue
        depth = 0
        in_str = False
        esc = False
        obj_start = pos
        found_end = False
        for j in range(pos, len(text)):
            c = text[j]
            if esc:
                esc = False
                continue
            if c == '\\' and in_str:
                esc = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[obj_start:j + 1])
                        found.append(obj)
                    except json.JSONDecodeError:
                        pass
                    pos = j + 1
                    found_end = True
                    break
        if not found_end:
            break
    return found


# ─── Hardening utility functions ──────────────────────────────────


def is_truncated(raw: str) -> bool:
    """Detect if an AI response was truncated before completion (加固4)."""
    stripped = raw.rstrip()
    return not (stripped.endswith('}') or stripped.endswith(']') or stripped.endswith('```'))


def estimate_max_tokens(text_len: int, model_hint: str = "") -> int:
    """Adaptive max_tokens budget based on input text length (加固4).

    Args:
        text_len: Length of input text in characters.
        model_hint: Optional model name for adjustment.

    Returns:
        Recommended max_tokens value (16000–64000).
    """
    base = int(text_len * 2.5)

    model_lower = model_hint.lower()
    if "claude" in model_lower:
        # Claude has lower CJK token efficiency → need more tokens
        base = int(base * 1.5)
    elif "gpt" in model_lower or "o1" in model_lower or "o3" in model_lower or "o4" in model_lower:
        # GPT has slightly better CJK tokenization
        base = int(base * 1.2)
    else:
        # Unknown model — use conservative multiplier
        base = int(base * 1.3)

    return max(16000, min(64000, base))
