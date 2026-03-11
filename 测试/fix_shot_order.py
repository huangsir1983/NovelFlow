"""Fix shot ID/order alignment in existing test results.

Problem: asyncio.gather processed scenes concurrently, so shot IDs were
assigned by API completion order instead of scene order.
e.g., scene_000 starts at shot_0025 instead of shot_0000.

Fix: Re-sort all shots by (scene_order, shot_number) and re-assign
sequential IDs from shot_0000.
"""

import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "第7次测试结果")
SHOTS_DIR = os.path.join(RESULT_DIR, "shots")


def main():
    # 1. Load all shots from all scene files
    all_shots = []
    shot_files = sorted(f for f in os.listdir(SHOTS_DIR)
                        if f.endswith("_shots.json") and f != "_index.json")

    print(f"Found {len(shot_files)} shot files")

    for fname in shot_files:
        path = os.path.join(SHOTS_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            shots = json.load(f)
        all_shots.extend(shots)

    print(f"Total shots: {len(all_shots)}")

    # 2. Show BEFORE state
    print("\n--- BEFORE (first shot per scene) ---")
    seen = set()
    for s in sorted(all_shots, key=lambda x: x.get("order", 0)):
        sid = s["scene_id"]
        if sid not in seen:
            seen.add(sid)
            print(f"  {sid}: first={s['id']}(order={s['order']})")

    # 3. Sort by scene numeric order, then shot_number within scene
    def scene_num(shot):
        m = re.search(r'scene_(\d+)', shot.get("scene_id", ""))
        return int(m.group(1)) if m else 9999

    all_shots.sort(key=lambda s: (scene_num(s), s.get("shot_number", 0)))

    # 4. Re-assign sequential IDs and orders
    for idx, shot in enumerate(all_shots):
        shot["id"] = f"shot_{idx:04d}"
        shot["order"] = idx

    # 5. Group by scene and save back
    from collections import defaultdict
    by_scene = defaultdict(list)
    for s in all_shots:
        by_scene[s["scene_id"]].append(s)

    for scene_id, scene_shots in by_scene.items():
        path = os.path.join(SHOTS_DIR, f"{scene_id}_shots.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(scene_shots, f, ensure_ascii=False, indent=2)

    # 6. Update index
    index = [{"id": s["id"], "scene_id": s["scene_id"],
              "framing": s["framing"], "goal": s["goal"][:50]}
             for s in all_shots]
    with open(os.path.join(SHOTS_DIR, "_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # 7. Show AFTER state
    print("\n--- AFTER (first shot per scene) ---")
    seen = set()
    for s in all_shots:
        sid = s["scene_id"]
        if sid not in seen:
            seen.add(sid)
            print(f"  {sid}: first={s['id']}(order={s['order']})")

    print(f"\nDone! Re-numbered {len(all_shots)} shots: shot_0000 ~ shot_{len(all_shots)-1:04d}")


if __name__ == "__main__":
    main()
