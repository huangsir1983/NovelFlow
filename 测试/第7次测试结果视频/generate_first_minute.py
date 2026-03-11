"""
第7次测试结果 — 视频生成：整部剧第1分钟（前10段 x 6秒）
基于 VFF 提示词，将角色描述内联替换 @char_ 引用
API: Grok Video (yhgrok.xuhuanai.cn)
"""
import json
import time
import httpx
import os
from datetime import datetime

API_BASE = "https://yhgrok.xuhuanai.cn"
API_KEY = "V378STSBi6jAC9Gk"
OUTPUT_DIR = r"G:\涛项目\claude版\测试\第7次测试结果视频"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# ── 角色外观描述（内联替换 @char_ 引用） ──
CHAR_GAO_LINGNING = (
    "a slender young noblewoman with pale skin, oval face, sharp calm almond eyes, "
    "straight dark brows with a hint of sharpness, black hair in a neat low bun, "
    "wearing muted moon-white silk hanfu robes, elegant yet emotionally guarded"
)

CHAR_GAO_FATHER = (
    "a dignified middle-aged scholar-official father with lean build, graying temples, "
    "stern furrowed brows, deep nasolabial folds, restrained but protective expression, "
    "wearing dark teal-blue hanfu robe, scholarly bearing"
)

CHAR_SHEN_RUI = (
    "a tall aristocratic young nobleman with pale cold skin, sharp jawline, narrow dark eyes, "
    "straight black hair in a neat topknot, wearing dark ink-blue brocade hanfu with jade ornament, "
    "restrained and cold expression, handsome yet emotionally guarded"
)

CHAR_LU_SHUYI = (
    "a frail young noblewoman with pale skin, teary downcast eyes, delicate oval face, "
    "slim body, black long hair in a low bun, wearing moon-white and pale pink hanfu "
    "with light gauze shawl, vulnerable tragic beauty"
)

# ── 前10段视频提示词（第1分钟） ──
# Scene 000: 高家屋内 — 高令宁 vs 高父 对峙（6段）
# Scene 001: 高家正堂 — 订亲退木雁（前4段）

TASKS = [
    {
        "name": "01_S000_父女对峙_开场",
        "scene": "scene_000 seg1",
        "aspect_ratio": "16:9",
        "prompt": (
            f"Interior of an ancient Chinese noble family house, daytime. Soft side light from doorway cuts across the room. "
            f"{CHAR_GAO_LINGNING} stands motionless at the right side of frame, spine perfectly straight. "
            f"{CHAR_GAO_FATHER} paces around her in the left-center, circling between her front and side, "
            f"his movement creating an oppressive interrogation rhythm. A wooden table in blurred foreground, "
            f"doorframe forming a cage-like second layer trapping both figures. "
            f"Fixed camera, medium wide shot. Oppressive, confined atmosphere. Song dynasty interior. "
            f"Cinematic lighting, shallow depth of field, film grain."
        ),
    },
    {
        "name": "02_S000_父女对峙_逼问",
        "scene": "scene_000 seg2",
        "aspect_ratio": "16:9",
        "prompt": (
            f"Interior of an ancient Chinese house, daytime. Medium close-up shot. "
            f"{CHAR_GAO_FATHER} occupies the left half of frame, facing right, brow deeply furrowed, "
            f"raising his hand to point accusingly, his fingers jabbing into foreground. "
            f"Window lattice light spots on the empty wall behind him create psychological pressure. "
            f"Then reverse shot: {CHAR_GAO_LINGNING} at right-center, side-backlight splitting her face "
            f"into cold white and shadow halves. She does not argue or retreat, meeting his accusations "
            f"with an unnervingly calm flat gaze. Father's sleeve occasionally sweeps across foreground. "
            f"Fixed camera, anxious and cold undercurrent. Song dynasty aesthetic, cinematic."
        ),
    },
    {
        "name": "03_S000_父女对峙_冷笑",
        "scene": "scene_000 seg3",
        "aspect_ratio": "16:9",
        "prompt": (
            f"Interior ancient Chinese house, daytime. Medium wide shot. "
            f"{CHAR_GAO_LINGNING} remains pinned at the right side of frame, absolutely still. "
            f"{CHAR_GAO_FATHER} paces from left foreground to background and back, furniture cutting the space. "
            f"The bright doorway behind them is an exit no one approaches. "
            f"Close-up: when he mentions the Shen family's insult, her lip corner twitches into "
            f"a faint cold smirk, her eyes suddenly hardening. Diagonal window light crosses her jaw, "
            f"revealing menace for the first time. "
            f"Then his gestures drop, body leans forward then pulls back, fear creeping into his reproach. "
            f"Tracking shot, tense and icy. Song dynasty interior, cinematic drama."
        ),
    },
    {
        "name": "04_S000_父女对峙_退让",
        "scene": "scene_000 seg4",
        "aspect_ratio": "16:9",
        "prompt": (
            f"Interior ancient Chinese house, daytime. Close-up on {CHAR_GAO_LINGNING} in three-quarter profile "
            f"at right side, large negative space to her left. She quietly says 'I know' — her expression "
            f"barely changes but her eyes grow colder, the words cutting like a blade. "
            f"Medium shot: {CHAR_GAO_FATHER} finally stops pacing. He stands still, drops his hands, "
            f"presses his chest and slowly exhales. Window lattice shadows cross his chest. "
            f"His aggression transforms into weary surrender. He lowers his voice, offering her a way out — "
            f"if she doesn't want to marry, he'll find an excuse to refuse. "
            f"Dolly camera movement. Cold-hard mood shifting to false calm. Song dynasty interior, cinematic."
        ),
    },
    {
        "name": "05_S000_父女对峙_反问",
        "scene": "scene_000 seg5",
        "aspect_ratio": "16:9",
        "prompt": (
            f"Interior ancient Chinese house, daytime. Medium close-up: {CHAR_GAO_LINGNING} first looks down, "
            f"then slowly raises her eyes toward the left where her father stands. Background darkens, "
            f"only a thin line of light from the doorway remains. Her chin lifts slightly, "
            f"showing sharp determination in her stillness. "
            f"Close-up: camera presses tight on her face. She asks quietly but firmly: "
            f"'Who said I don't want to marry?' Background simplified to cold grey wall and blurred window shadows. "
            f"All information and control falls on her. "
            f"Close-up: {CHAR_GAO_FATHER} — his gaze freezes, mouth slightly open but speechless. "
            f"Doorway light behind him feels more oppressive. He is pushed outside his frame of understanding. "
            f"Dolly movement, sharp and stunning reversal. Cinematic, Song dynasty."
        ),
    },
    {
        "name": "06_S000_父女对峙_宣言",
        "scene": "scene_000 seg6",
        "aspect_ratio": "16:9",
        "prompt": (
            f"Interior ancient Chinese house, daytime. Low angle close-up pressing toward {CHAR_GAO_LINGNING}. "
            f"She stands centered, window lattice shadows behind her like prison bars cutting the cold grey background. "
            f"She states without blinking: 'I must marry' — her voice steady, carrying absolute will, "
            f"as if seizing control of this arranged marriage with her own hands. "
            f"Then medium wide shot returning to the opening composition: {CHAR_GAO_FATHER} stopped at left, "
            f"no longer pacing. {CHAR_GAO_LINGNING} still at right, unmoved. Empty space between them "
            f"with diagonal light on the floor like an invisible boundary. Table corner presses foreground down. "
            f"Doorway still bright, but neither walks toward it. "
            f"Dolly, then fixed. Resolute, icy fracture. Cinematic, Song dynasty interior."
        ),
    },
    {
        "name": "07_S001_订亲正堂_木雁登场",
        "scene": "scene_001 seg1",
        "aspect_ratio": "16:9",
        "prompt": (
            f"Interior of a grand ancient Chinese family hall during a betrothal ceremony, daytime. "
            f"Doorframe composition. Gold and silver silks laid out in perfect rows as betrothal gifts. "
            f"{CHAR_GAO_FATHER} sits at the head position, smiling. A matchmaker stands beside the gifts. "
            f"{CHAR_SHEN_RUI} stands further back, half-hidden behind ceremonial objects, reserved and cold. "
            f"At the brightest center spot sits a conspicuously crude wooden goose — out of place among the wealth. "
            f"Subjective shot: {CHAR_GAO_LINGNING} enters through moon-white sleeves crossing frame. "
            f"Her gaze bypasses all faces, cutting through the gifts to lock onto the wooden goose. "
            f"Close-up of the wooden goose surrounded by gold and silk, rough wood grain lit by side-backlight, "
            f"its cheapness painfully obvious amid the luxury. "
            f"Fixed camera, formal yet oppressive. Song dynasty betrothal hall, cinematic."
        ),
    },
    {
        "name": "08_S001_订亲正堂_伸手取雁",
        "scene": "scene_001 seg2",
        "aspect_ratio": "16:9",
        "prompt": (
            f"Ancient Chinese family hall, betrothal ceremony, daytime. "
            f"Medium close-up: {CHAR_GAO_LINGNING} stops at the right side of the hall. "
            f"Half her face is cut by window lattice light and shadow. Her gaze locks toward the wooden goose "
            f"at the left. Her expression shifts from scrutiny to swift determination. "
            f"Medium shot: {CHAR_GAO_FATHER} sits at the head, leaning forward toward the matchmaker "
            f"and {CHAR_SHEN_RUI} with an eager smile. {CHAR_SHEN_RUI} stands in half-shadow behind, "
            f"eyes downcast, restrained to the point of cold rigidity. "
            f"Medium shot: without waiting for ceremony to proceed, {CHAR_GAO_LINGNING} reaches "
            f"from the right side across the betrothal gifts toward the central wooden goose, "
            f"her body's diagonal line breaking the hall's symmetrical order. "
            f"Push-in tracking, restrained then suddenly transgressive. Song dynasty interior, cinematic."
        ),
    },
    {
        "name": "09_S001_订亲正堂_退还木雁",
        "scene": "scene_001 seg3",
        "aspect_ratio": "16:9",
        "prompt": (
            f"Ancient Chinese betrothal hall, daytime. Close-up: {CHAR_GAO_LINGNING}'s hand extends "
            f"from the right, pushing the crude wooden goose directly toward the matchmaker. "
            f"The matchmaker's hands hover between accepting and refusing. The wooden goose sits centered "
            f"in frame — like a publicly returned insult. "
            f"Medium close-up: the matchmaker hastily cradles the goose but holds it unsteadily. "
            f"{CHAR_GAO_LINGNING}'s shoulder presses foreground. {CHAR_GAO_FATHER}'s silhouette freezes above. "
            f"The hall's veneer of propriety cracks open. "
            f"{CHAR_GAO_FATHER}'s smile hasn't fully faded before his face suddenly darkens. "
            f"Then {CHAR_GAO_LINGNING} lifts her chin toward matchmaker and father, her voice steady: "
            f"'The betrothal gifts are too thin. I am not satisfied.' "
            f"Deep in background, {CHAR_SHEN_RUI} has not yet raised his eyes. "
            f"Fixed camera, sharp, brazen public reversal. Song dynasty, cinematic."
        ),
    },
    {
        "name": "10_S001_订亲正堂_对视识破",
        "scene": "scene_001 seg4",
        "aspect_ratio": "16:9",
        "prompt": (
            f"Ancient Chinese betrothal hall, daytime. Extreme close-up: "
            f"{CHAR_SHEN_RUI} suddenly lifts his eyelids from behind the matchmaker's shoulder, "
            f"window light cutting into his dark pupils — silently catching the blade {CHAR_GAO_LINGNING} has thrown. "
            f"Medium close-up: restricted dual perspective — {CHAR_GAO_LINGNING} in right foreground, "
            f"{CHAR_SHEN_RUI} in left background, betrothal gifts and matchmaker between them. "
            f"The two lock eyes across the distance, the wooden goose pushed to a corner. "
            f"Their mutual recognition becomes the new focal point. "
            f"Medium shot: {CHAR_GAO_FATHER} slams the table, standing up abruptly. Tea cups tremble. "
            f"Handheld shake tears the suppressed space wide open. He leans forward scolding fiercely. "
            f"The matchmaker clutches the goose, squeezed between father and daughter trying to mediate. "
            f"{CHAR_SHEN_RUI} still stands deep in the frame, watching coldly. "
            f"Handheld camera, recognition, counter-strike, authority erupting. Song dynasty hall, cinematic."
        ),
    },
]

POLL_INTERVAL = 8   # seconds between polls
POLL_TIMEOUT = 360  # 6 minutes max per task


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
    log_file = os.path.join(OUTPUT_DIR, "generation_log.json")
    start_time = datetime.now()

    print("=" * 70)
    print(f"第7次测试结果 — 视频生成：第1分钟（10段 x 6秒）")
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1. Submit all tasks
    print("\n" + "=" * 70)
    print("Step 1: 创建视频生成任务 (10 tasks)")
    print("=" * 70)
    task_ids = {}
    for i, t in enumerate(TASKS, 1):
        print(f"\n[CREATE {i}/10] {t['name']}")
        print(f"  Scene: {t['scene']}")
        print(f"  Aspect: {t['aspect_ratio']}")
        try:
            tid = create_task(t["prompt"], t["aspect_ratio"])
            task_ids[t["name"]] = tid
        except Exception as e:
            print(f"  [ERROR] 创建失败: {e}")
            task_ids[t["name"]] = None

    # 2. Poll all tasks
    print("\n" + "=" * 70)
    print("Step 2: 等待视频生成完成")
    print("=" * 70)
    results = {}
    for name, tid in task_ids.items():
        if tid is None:
            results[name] = {"status": "create_failed", "url": None}
            continue
        print(f"\n[WAITING] {name} ({tid})")
        data = poll_task(tid)
        if data:
            video_url = (
                data.get("video_url")
                or data.get("url")
                or (data.get("output") or {}).get("url", "")
            )
            results[name] = {"status": "completed", "url": video_url, "task_id": tid}
            print(f"  [DONE] URL: {video_url[:80]}...")
        else:
            results[name] = {"status": "failed", "url": None, "task_id": tid}

    # 3. Download videos
    print("\n" + "=" * 70)
    print("Step 3: 下载视频文件")
    print("=" * 70)
    for name, info in results.items():
        url = info.get("url")
        if url:
            filepath = os.path.join(OUTPUT_DIR, f"{name}.mp4")
            print(f"\n[DOWNLOAD] {name}")
            try:
                download_video(url, filepath)
                info["file"] = filepath
                info["file_size_mb"] = os.path.getsize(filepath) / (1024 * 1024)
            except Exception as e:
                print(f"  [ERROR] 下载失败: {e}")
                info["download_error"] = str(e)
        else:
            print(f"\n[SKIP] {name} - 无URL (生成失败或超时)")

    # 4. Summary
    end_time = datetime.now()
    elapsed_total = (end_time - start_time).total_seconds()
    print("\n" + "=" * 70)
    print("Summary — 第1分钟视频生成结果")
    print("=" * 70)
    success = 0
    fail = 0
    for name, info in results.items():
        if info.get("file_size_mb"):
            success += 1
            print(f"  OK    {name}.mp4  ({info['file_size_mb']:.1f} MB)")
        else:
            fail += 1
            print(f"  FAIL  {name}  ({info['status']})")
    print(f"\n成功: {success}/10, 失败: {fail}/10")
    print(f"总耗时: {elapsed_total:.0f}s ({elapsed_total/60:.1f} min)")

    # 5. Save log
    log = {
        "test": "第7次测试结果_视频生成_第1分钟",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "elapsed_seconds": elapsed_total,
        "tasks": [
            {
                "name": t["name"],
                "scene": t["scene"],
                "aspect_ratio": t["aspect_ratio"],
                "prompt": t["prompt"],
                "result": results.get(t["name"], {}),
            }
            for t in TASKS
        ],
        "summary": {"success": success, "fail": fail, "total": 10},
    }
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"\n日志已保存: {log_file}")


if __name__ == "__main__":
    main()
