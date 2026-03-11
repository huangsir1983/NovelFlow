"""
视频生成测试脚本 — 基于第5次测试结果场景+角色形象
提交5个任务到 Grok Video API, 轮询完成后下载视频
"""
import json
import time
import httpx
import os

API_BASE = "https://yhgrok.xuhuanai.cn"
API_KEY = "V378STSBi6jAC9Gk"
OUTPUT_DIR = r"G:\涛项目\claude版\测试\视频生成测试"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# ── 5 个视频提示词 (融合角色 visual_reference + 场景描述) ──
TASKS = [
    {
        "name": "01_柳下拾钗_初遇心动",
        "aspect_ratio": "16:9",
        "prompt": (
            "Soft warm sunlight filtering through hanging willow branches onto a stone path in ancient China. "
            "A tall aristocratic young nobleman with pale cold skin, sharp jawline, narrow dark eyes, "
            "straight black hair in a neat topknot, wearing dark ink-blue hanfu with jade ornament, "
            "bends down gracefully to pick up a golden hairpin from the ground. "
            "A dignified young noblewoman with sharp almond eyes, black coiled hair, in muted blue silk hanfu "
            "watches him with restrained emotion. Willow leaves swaying in breeze, dappled light and shadow, "
            "dreamy romantic atmosphere, cinematic slow motion, Song dynasty aesthetic, shallow depth of field"
        ),
    },
    {
        "name": "02_红烛婚房_噩梦独坐",
        "aspect_ratio": "9:16",
        "prompt": (
            "A dignified ancient Chinese noblewoman, slender and pale, oval face, sharp almond eyes, "
            "wearing an elaborate red wedding dress with golden embroidery, sitting alone in a dimly lit bridal chamber. "
            "Flickering red candlelight casting unstable shadows on red silk curtains. "
            "She reaches up and fiercely tears off her heavy hairpin ornaments, her expression shifting from frozen composure to cold despair. "
            "The candle flame wavers violently. Dark cinematic atmosphere, nightmare quality, warm red and cold shadow contrast, "
            "Song dynasty interior, realistic detail, film grain"
        ),
    },
    {
        "name": "03_马球角落_危险对峙",
        "aspect_ratio": "16:9",
        "prompt": (
            "A secluded corner behind curtains at an ancient Chinese polo ground. "
            "A tall nobleman in dark ink-blue brocade robe with pale cold skin and sharp jawline steps forward aggressively, "
            "blocking the path of a young noblewoman in ivory and blue-grey silk hanfu who leans against a wooden railing, "
            "her ankle slightly swollen. Their faces are dangerously close, tension crackling between them. "
            "Distant sounds of celebration, tree shadows and fabric curtains framing the scene, "
            "afternoon sunlight cutting through gaps, charged atmosphere, cinematic drama, shallow depth of field"
        ),
    },
    {
        "name": "04_书房辞官_父女博弈",
        "aspect_ratio": "16:9",
        "prompt": (
            "Interior of an ancient Chinese scholar's study, daylight from side window illuminating calligraphy desk. "
            "A middle-aged scholar-official father with salt-and-pepper hair in neat topknot, wearing dark teal robes, "
            "sits at the desk dipping brush in ink, writing on official paper with heavy deliberate strokes. "
            "His dignified daughter in muted blue hanfu stands beside him, arms at her sides, watching every stroke intently, "
            "her knuckles white from clenching. Ink, brush, paper, seal on desk. Tense solemn atmosphere, "
            "Song dynasty aesthetics, cinematic lighting, realistic, the weight of a life-changing decision"
        ),
    },
    {
        "name": "05_江南书房_冷笔封信",
        "aspect_ratio": "16:9",
        "prompt": (
            "A bright yet cold study room in a Jiangnan watertown house, white daylight streaming through lattice window. "
            "A slender pale young woman with sharp almond eyes and black hair in a neat low bun, wearing plain white silk hanfu, "
            "sits at a wooden desk writing a letter with steady brush strokes. She pauses at a word, brush pressed heavy, "
            "then continues. She finishes, blows on the wet ink, folds the letter with crisp decisive motions, "
            "her face completely expressionless, sealing away all emotion. Inkstone, paper weight, letter on desk. "
            "Clean minimal interior, quiet loneliness, cinematic, Song dynasty Jiangnan style, muted color palette"
        ),
    },
]

POLL_INTERVAL = 8   # seconds
POLL_TIMEOUT = 360  # 6 minutes max

def create_task(prompt: str, aspect_ratio: str) -> str:
    body = {
        "model": "grok-video-3",
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "seconds": 6,
        "size": "720P",
    }
    resp = httpx.post(f"{API_BASE}/v1/videos", json=body, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    task_id = data.get("task_id") or data.get("id")
    print(f"  -> task_id={task_id}, status={data.get('status')}")
    return task_id


def poll_task(task_id: str) -> dict | None:
    """Poll until completed/failed. Returns response dict or None on failure."""
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > POLL_TIMEOUT:
            print(f"  [TIMEOUT] {task_id} after {POLL_TIMEOUT}s")
            return None

        resp = httpx.get(f"{API_BASE}/v1/videos/{task_id}", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status", "unknown")
        progress = data.get("progress", 0)

        if status == "completed":
            return data
        elif status == "failed":
            err = (data.get("error") or {}).get("message", "unknown")
            print(f"  [FAILED] {task_id}: {err}")
            return None

        print(f"  [POLL] {task_id}: {status} {progress}% ({elapsed:.0f}s)")
        time.sleep(POLL_INTERVAL)


def download_video(url: str, filepath: str):
    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_bytes(8192):
                f.write(chunk)
    size_kb = os.path.getsize(filepath) / 1024
    print(f"  [SAVED] {filepath} ({size_kb:.0f} KB)")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Submit all tasks
    print("=" * 60)
    print("Step 1: Creating video generation tasks")
    print("=" * 60)
    task_ids = {}
    for t in TASKS:
        print(f"\n[CREATE] {t['name']}")
        tid = create_task(t["prompt"], t["aspect_ratio"])
        task_ids[t["name"]] = tid

    # 2. Poll all tasks
    print("\n" + "=" * 60)
    print("Step 2: Polling for completion")
    print("=" * 60)
    results = {}
    for name, tid in task_ids.items():
        print(f"\n[WAITING] {name} ({tid})")
        data = poll_task(tid)
        if data:
            video_url = data.get("video_url") or data.get("url") or (data.get("output") or {}).get("url", "")
            results[name] = video_url
            print(f"  [DONE] URL: {video_url[:80]}...")
        else:
            results[name] = None

    # 3. Download videos
    print("\n" + "=" * 60)
    print("Step 3: Downloading videos")
    print("=" * 60)
    for name, url in results.items():
        if url:
            filepath = os.path.join(OUTPUT_DIR, f"{name}.mp4")
            print(f"\n[DOWNLOAD] {name}")
            try:
                download_video(url, filepath)
            except Exception as e:
                print(f"  [ERROR] Download failed: {e}")
        else:
            print(f"\n[SKIP] {name} - no URL (failed or timed out)")

    # 4. Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for name, url in results.items():
        filepath = os.path.join(OUTPUT_DIR, f"{name}.mp4")
        if url and os.path.exists(filepath):
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            print(f"  OK  {name}.mp4  ({size_mb:.1f} MB)")
        else:
            print(f"  FAIL  {name}")


if __name__ == "__main__":
    main()
