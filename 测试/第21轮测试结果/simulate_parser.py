"""Simulate ProgressiveAssetParser step-by-step to find exactly where scenes are lost."""
import re, json, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add backend to path
sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), '..', '..', 'backend')))

from services.streaming_parser import ProgressiveAssetParser

t = open("chatgpt/_debug/stage1_raw.txt", encoding="utf-8").read()
print(f"Total response: {len(t)} chars")

# Simulate streaming with different chunk sizes
for chunk_size in [2, 10, 50, 200]:
    parser = ProgressiveAssetParser()
    total_chars = 0
    total_scenes = 0
    scene_discoveries = []

    pos = 0
    feed_count = 0
    while pos < len(t):
        chunk = t[pos:pos + chunk_size]
        result = parser.feed(chunk)
        feed_count += 1

        for c in result["characters"]:
            total_chars += 1
        for s in result["scenes"]:
            total_scenes += 1
            scene_discoveries.append({
                "scene_num": total_scenes,
                "feed": feed_count,
                "input_pos": pos,
                "location": s.get("location", "?")[:25],
                "buffer_len": len(parser.buffer),
                "scan_pos": parser._scan_pos,
                "obj_start": parser._obj_start,
                "depth": parser._depth,
                "in_array": parser._in_array,
                "scenes_closed": parser._scenes_closed,
            })

        pos += chunk_size

    print(f"\n=== Chunk size={chunk_size}: chars={total_chars}, scenes={total_scenes}, feeds={feed_count} ===")
    if total_scenes < 21:
        print(f"  MISSING {21 - total_scenes} scenes!")
        # Show last discovered scene
        if scene_discoveries:
            last = scene_discoveries[-1]
            print(f"  Last scene: #{last['scene_num']} at feed {last['feed']} (input_pos={last['input_pos']})")
            print(f"    location={last['location']}")
            print(f"    buffer_len={last['buffer_len']}, scan_pos={last['scan_pos']}")
            print(f"    obj_start={last['obj_start']}, depth={last['depth']}")
            print(f"    in_array={last['in_array']}, scenes_closed={last['scenes_closed']}")

        # Check parser state after all feeds
        print(f"  Final parser state:")
        print(f"    buffer_len={len(parser.buffer)}, scan_pos={parser._scan_pos}")
        print(f"    chars_closed={parser._chars_closed}, scenes_closed={parser._scenes_closed}")
        print(f"    in_array={parser._in_array}, depth={parser._depth}")
        print(f"    obj_start={parser._obj_start}")

        # Show buffer content around scan_pos
        sp = parser._scan_pos
        buf = parser.buffer
        if sp < len(buf):
            snippet = buf[max(0,sp-50):sp+50].replace('\n', '\\n')
            print(f"    buffer around scan_pos: ...{snippet}...")
        else:
            print(f"    scan_pos ({sp}) >= buffer_len ({len(buf)})")
            tail = buf[-100:].replace('\n', '\\n')
            print(f"    buffer tail: ...{tail}")
    else:
        print(f"  OK - all 21 scenes found")
        for sd in scene_discoveries[:3]:
            print(f"    Scene {sd['scene_num']}: {sd['location']}")
        print(f"    ...")
        for sd in scene_discoveries[-3:]:
            print(f"    Scene {sd['scene_num']}: {sd['location']}")
