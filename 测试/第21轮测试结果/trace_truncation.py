"""Trace buffer truncation to see exactly which scenes are lost."""
import re, json, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), '..', '..', 'backend')))

from services.streaming_parser import ProgressiveAssetParser

t = open("chatgpt/_debug/stage1_raw.txt", encoding="utf-8").read()

# Monkey-patch to trace truncation
orig_feed = ProgressiveAssetParser.feed

truncation_events = []
scene_events = []

def traced_feed(self, chunk):
    old_buf_len = len(self.buffer)
    old_scan_pos = self._scan_pos
    old_obj_start = self._obj_start

    # Do the buffer append and clean
    self.buffer += chunk
    self.buffer = self._clean(self.buffer)
    result = {"characters": [], "scenes": []}

    if not self._chars_closed:
        new_chars = self._scan_array("characters")
        result["characters"] = new_chars
        self.found_chars.extend(new_chars)

    if self._chars_closed and not self._scenes_closed:
        # Check if truncation will happen
        if self._scan_pos > 1000:
            truncation_events.append({
                "buf_len_before": len(self.buffer),
                "scan_pos": self._scan_pos,
                "obj_start_before": self._obj_start,
                "depth": self._depth,
                "in_array": self._in_array,
                "scenes_found_so_far": len(self.found_scenes),
                "buffer_snippet_at_scanpos": self.buffer[self._scan_pos:self._scan_pos+80].replace('\n','\\n')[:80] if self._scan_pos < len(self.buffer) else "PAST_END",
            })
            # Do the truncation (same logic as original)
            self.buffer = self.buffer[self._scan_pos:]
            self._scan_pos = 0
            if self._obj_start >= 0:
                self._obj_start = 0
            truncation_events[-1]["obj_start_after"] = self._obj_start
            truncation_events[-1]["buf_len_after"] = len(self.buffer)
            truncation_events[-1]["buffer_head_after"] = self.buffer[:120].replace('\n','\\n')

        new_scenes = self._scan_array("scenes")
        result["scenes"] = new_scenes
        self.found_scenes.extend(new_scenes)
        for s in new_scenes:
            scene_events.append({
                "num": len(self.found_scenes),
                "location": s.get("location", "?")[:30],
            })

    return result

ProgressiveAssetParser.feed = traced_feed

# Run with chunk_size=2 (matching real streaming ~2 chars/chunk avg)
parser = ProgressiveAssetParser()
chunk_size = 2
pos = 0
while pos < len(t):
    chunk = t[pos:pos + chunk_size]
    parser.feed(chunk)
    pos += chunk_size

print(f"Total scenes found: {len(parser.found_scenes)}")
print(f"\nScenes discovered:")
for se in scene_events:
    print(f"  #{se['num']}: {se['location']}")

print(f"\nTruncation events: {len(truncation_events)}")
for i, te in enumerate(truncation_events[:5]):
    print(f"\n  Truncation #{i+1}:")
    print(f"    buf_len_before={te['buf_len_before']}, scan_pos={te['scan_pos']}")
    print(f"    obj_start_before={te['obj_start_before']} -> obj_start_after={te['obj_start_after']}")
    print(f"    depth={te['depth']}, in_array={te['in_array']}")
    print(f"    scenes_found_so_far={te['scenes_found_so_far']}")
    print(f"    buf_len_after={te['buf_len_after']}")
    print(f"    buffer_head_after: {te['buffer_head_after']}")
