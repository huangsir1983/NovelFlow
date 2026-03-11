"""Full trace: which scenes are found, which are lost, and why."""
import re, json, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), '..', '..', 'backend')))

from services.streaming_parser import ProgressiveAssetParser

t = open("chatgpt/_debug/stage1_raw.txt", encoding="utf-8").read()

# Get ground truth scene locations
all_21 = []
for m in re.finditer(r'"location"\s*:\s*"([^"]+)"', t[15600:]):
    all_21.append(m.group(1))
print("Ground truth 21 scenes:")
for i, loc in enumerate(all_21[:21]):
    print(f"  {i+1:2d}. {loc}")

truncation_log = []

# Monkey-patch to log truncation details
orig_feed = ProgressiveAssetParser.feed
def traced_feed(self, chunk):
    self.buffer += chunk
    self.buffer = self._clean(self.buffer)
    result = {"characters": [], "scenes": []}

    if not self._chars_closed:
        new_chars = self._scan_array("characters")
        result["characters"] = new_chars
        self.found_chars.extend(new_chars)

    if self._chars_closed and not self._scenes_closed:
        if self._scan_pos > 1000:
            # Log what's being cut
            cut_content = self.buffer[:self._scan_pos]
            # Check if there are incomplete scene objects in the cut portion
            if self._obj_start >= 0 and self._obj_start < self._scan_pos:
                lost_fragment = self.buffer[self._obj_start:self._scan_pos]
                loc_m = re.search(r'"location"\s*:\s*"([^"]+)"', lost_fragment)
                loc = loc_m.group(1) if loc_m else "not yet in fragment"
                truncation_log.append({
                    "scenes_so_far": len(self.found_scenes),
                    "obj_start": self._obj_start,
                    "scan_pos": self._scan_pos,
                    "depth": self._depth,
                    "fragment_size": self._scan_pos - self._obj_start,
                    "location_in_fragment": loc,
                    "issue": "OBJECT CUT IN HALF - front part discarded",
                })

            self.buffer = self.buffer[self._scan_pos:]
            self._scan_pos = 0
            if self._obj_start >= 0:
                self._obj_start = 0

        new_scenes = self._scan_array("scenes")
        result["scenes"] = new_scenes
        self.found_scenes.extend(new_scenes)

    return result

ProgressiveAssetParser.feed = traced_feed

parser = ProgressiveAssetParser()
chunk_size = 2
pos = 0
while pos < len(t):
    parser.feed(t[pos:pos+chunk_size])
    pos += chunk_size

found_locs = [s.get("location","?") for s in parser.found_scenes]
print(f"\nStreaming parser found {len(found_locs)} scenes:")
for i, loc in enumerate(found_locs):
    print(f"  {i+1:2d}. {loc}")

print(f"\nMISSED scenes:")
for i, loc in enumerate(all_21[:21]):
    if loc not in found_locs:
        print(f"  {i+1:2d}. {loc}")

print(f"\nTruncation events that CUT scene objects: {len(truncation_log)}")
for i, tl in enumerate(truncation_log):
    print(f"\n  Cut #{i+1}:")
    print(f"    scenes_found_so_far={tl['scenes_so_far']}")
    print(f"    obj_start={tl['obj_start']}, scan_pos={tl['scan_pos']}")
    print(f"    fragment_size={tl['fragment_size']}, depth={tl['depth']}")
    print(f"    location_in_fragment: {tl['location_in_fragment']}")
    print(f"    >> {tl['issue']}")
