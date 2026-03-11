"""Verify the fix: run ProgressiveAssetParser against saved raw response."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), '..', '..', 'backend')))

from services.streaming_parser import ProgressiveAssetParser

t = open("chatgpt/_debug/stage1_raw.txt", encoding="utf-8").read()
print(f"Response: {len(t)} chars")

for chunk_size in [2, 10, 50, 200]:
    parser = ProgressiveAssetParser()
    pos = 0
    while pos < len(t):
        parser.feed(t[pos:pos + chunk_size])
        pos += chunk_size

    locs = [s.get("location", "?") for s in parser.found_scenes]
    print(f"\nchunk_size={chunk_size:3d}: chars={len(parser.found_chars)}, scenes={len(parser.found_scenes)}")
    for i, loc in enumerate(locs):
        print(f"  {i+1:2d}. {loc}")
