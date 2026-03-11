"""Analyze raw stage1 response to understand scene object layout."""
import re, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

t = open("chatgpt/_debug/stage1_raw.txt", encoding="utf-8").read()
print(f"Total length: {len(t)} chars")

# Find scenes array start
scenes_key = t.find('"scenes"')
print(f'"scenes" key at pos: {scenes_key}')
scenes_bracket = t.find('[', scenes_key)
print(f'scenes [ at pos: {scenes_bracket}')

# Also find characters array to understand layout
chars_key = t.find('"characters"')
chars_bracket = t.find('[', chars_key)
print(f'"characters" key at pos: {chars_key}, [ at pos: {chars_bracket}')

# String-aware depth tracking
depth = 0
in_str = False
esc = False
obj_count = 0
obj_positions = []
obj_start = -1
pos = scenes_bracket + 1

while pos < len(t):
    ch = t[pos]
    if esc:
        esc = False
        pos += 1
        continue
    if in_str:
        if ch == "\\":
            esc = True
        elif ch == '"':
            in_str = False
        pos += 1
        continue
    # Not in string
    if ch == '"':
        in_str = True
    elif ch == '{':
        if depth == 0:
            obj_start = pos
        depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0 and obj_start >= 0:
            obj_count += 1
            obj_positions.append((obj_start, pos))
            obj_start = -1
    elif ch == ']' and depth == 0:
        print(f'scenes ] at pos: {pos}')
        break
    pos += 1

print(f"\nComplete scene objects in JSON: {obj_count}")
for i, (s, e) in enumerate(obj_positions):
    loc_m = re.search(r'"location"\s*:\s*"([^"]+)"', t[s:e+1])
    loc = loc_m.group(1)[:30] if loc_m else "?"
    print(f"  Scene {i+1:2d}: pos {s:6d}-{e:6d} (size={e-s:5d}) location={loc}")

# Now simulate what the streaming parser sees
# Key question: what happens at buffer truncation point (scan_pos > 1000)?
print(f"\n--- Simulating ProgressiveAssetParser behavior ---")
print(f"Characters array ends somewhere before scenes key at pos {scenes_key}")

# Check what characters look like between scene 8 and 9
if len(obj_positions) >= 9:
    s8_end = obj_positions[7][1]  # end of scene 8
    s9_start = obj_positions[8][0]  # start of scene 9
    between = t[s8_end:s9_start+1]
    print(f"\nBetween scene 8 (end={s8_end}) and scene 9 (start={s9_start}):")
    print(f"  Gap text ({len(between)} chars): {repr(between[:200])}")

# Check for problematic chars inside scene objects (] or } that could confuse naive parser)
print(f"\n--- Checking for ] and unescaped braces in scene string values ---")
for i, (s, e) in enumerate(obj_positions):
    obj_text = t[s:e+1]
    # Count ] inside string values (rough check: find ] not preceded by [)
    # More accurately: check if naive (non-string-aware) brace tracking would fail
    naive_depth = 0
    naive_closed = False
    for ci, cc in enumerate(obj_text):
        if cc == '{':
            naive_depth += 1
        elif cc == '}':
            naive_depth -= 1
            if naive_depth < 0:
                break
        elif cc == ']' and naive_depth == 0:
            naive_closed = True
            break
    if naive_closed:
        # Find which string field contains the problematic ]
        print(f"  Scene {i+1}: NAIVE PARSER WOULD SEE ] AT DEPTH 0 at char offset {ci}")
        context = obj_text[max(0,ci-40):ci+10]
        print(f"    Context: ...{repr(context)}...")
    if naive_depth < 0:
        print(f"  Scene {i+1}: NAIVE PARSER depth went negative at offset {ci}")
