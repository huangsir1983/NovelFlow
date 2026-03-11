"""
第7次测试结果 — 视频生成：整部剧第1分钟（前10段 x 6秒）
全中文提示词版本，角色描述内联替换 @char_ 引用
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

# ── 角色外观描述（中文，内联替换 @char_ 引用） ──
高令宁 = (
    "一位身形纤薄修长的年轻贵族女子，冷白肌肤，鹅蛋脸偏清瘦，眉形平直略带锋意，"
    "眼型细长微挑、瞳色乌深，乌黑长发梳成低髻，身穿月白色丝绸汉服长裙，"
    "气质端丽克制，神情冷静而内敛"
)

高父 = (
    "一位清瘦端正的中年文官父亲，两鬓斑白，眉心常年微蹙呈川字纹，"
    "面相儒雅威严，法令纹深刻，身穿深青色圆领长衫，"
    "举止有士大夫的规整感，神情隐忍而护犊"
)

沈睿 = (
    "一位身量修长的年轻贵族男子，冷白肌肤，面容清俊，下颌线锋利，"
    "眼型偏长而黑白分明，乌黑浓密的头发束以发冠，"
    "身穿墨青色暗纹锦缎汉服，佩玉，气质疏淡克制而带压迫感"
)

# ── 前10段视频提示词（第1分钟，全中文） ──

TASKS = [
    {
        "name": "01_S000_父女对峙_开场",
        "scene": "scene_000 seg1",
        "aspect_ratio": "16:9",
        "prompt": (
            f"中国古代宋朝风格的贵族宅邸室内，白天，门口斜射入柔和侧光。"
            f"中全景镜头，{高令宁}立于画面右侧偏中，肩背笔直、纹丝不动。"
            f"{高父}在左中景沿她身前与侧后方来回绕步踱步，形成围猎般的压迫节奏。"
            f"前景桌沿虚焦，门框像第二层牢笼将父女二人困在室内。"
            f"女儿的静止与父亲的绕步形成强烈对比。"
            f"压抑、围困的气氛，古典中国室内，电影级光影，浅景深。"
        ),
    },
    {
        "name": "02_S000_父女对峙_逼问",
        "scene": "scene_000 seg2",
        "aspect_ratio": "16:9",
        "prompt": (
            f"中国古代宅邸室内，白天。中近景镜头。"
            f"{高父}占画面左半，朝右质问，眉心深锁，抬手指向时手指短促逼入前景。"
            f"窗棂光斑投在身后空墙上，留出心理压力区。"
            f"切至{高令宁}，仍在画面右侧偏中，侧逆光将她面部切成冷白与阴影两半。"
            f"她不辩、不退，只以平直冰冷的视线接住父亲的责问，异常平静的沉默反应。"
            f"左前景偶有父亲袖摆掠过。焦灼与暗流涌动的气氛，古典中国美学，电影质感。"
        ),
    },
    {
        "name": "03_S000_父女对峙_冷笑",
        "scene": "scene_000 seg3",
        "aspect_ratio": "16:9",
        "prompt": (
            f"中国古代宅邸室内，白天。"
            f"中全景：{高令宁}仍钉在画面右侧原地一动不动，"
            f"{高父}从左前景绕至背景又折回中前景，桌椅切割空间，门口亮部像退路却无人靠近。"
            f"当父亲提到沈家与今日失礼，切近{高令宁}唇角——"
            f"她嘴角极轻牵起一丝冷笑，眼神骤然发硬，斜向窗光掠过下颌，寒意第一次外露。"
            f"然后回到{高父}，手势已放下，身体前倾后收住，责备里开始掺入惶惧。"
            f"绷紧、寒意弥漫，电影级镜头，古典宋朝室内。"
        ),
    },
    {
        "name": "04_S000_父女对峙_退让",
        "scene": "scene_000 seg4",
        "aspect_ratio": "16:9",
        "prompt": (
            f"中国古代宅邸室内，白天。"
            f"近景：{高令宁}在右侧四分之三侧面，左侧留出大片负空间。"
            f"她只低声一句'我知道'，神情几乎未动，唯有眼神更冷，这句话像刀锋轻轻递出。"
            f"中景：{高父}终于停住脚步，不再绕步，垂手、轻按胸口后缓缓叹气。"
            f"窗棂阴影横过他胸前，攻势转为疲惫退让。"
            f"他双手收回身前，语气放低，提出'若你不想嫁,便由爹爹找由头回绝'。"
            f"姿态从进攻变成试探与护短。冷硬而虚假缓和的气氛，电影级画面。"
        ),
    },
    {
        "name": "05_S000_父女对峙_反问",
        "scene": "scene_000 seg5",
        "aspect_ratio": "16:9",
        "prompt": (
            f"中国古代宅邸室内，白天。"
            f"中近景：{高令宁}先略垂目，随即缓慢抬眼看向左侧出画的父亲。"
            f"背景压暗，只余门边一线亮光，她下颌微抬，静止里显出将要翻案的锋利。"
            f"近景：不切父亲，直接压紧在{高令宁}脸上，"
            f"她轻却硬地反问'谁说我不想嫁?'背景简化成冷灰墙与模糊窗影，"
            f"信息与控制权完全落在她身上。"
            f"近景：{高父}目光凝住，嘴微张却失语，"
            f"门口亮部在身后更显逼仄，他被女儿推出原有解释框架之外。"
            f"蓄势、锋利、错愕，电影级反转镜头，古典宋朝美学。"
        ),
    },
    {
        "name": "06_S000_父女对峙_宣言",
        "scene": "scene_000 seg6",
        "aspect_ratio": "16:9",
        "prompt": (
            f"中国古代宅邸室内，白天。"
            f"略低机位近景压向{高令宁}，她居中站定，"
            f"身后窗棂阴影如栅栏般切开冷灰背景。"
            f"她不眨眼、稳稳吐出'我一定要嫁'，语速平稳却带绝对意志，"
            f"像亲手把这门婚事从被安排改成被掌控。"
            f"中全景：回到开场同轴空间——{高父}停在左侧不再绕步，"
            f"{高令宁}仍立在右侧原地。二人之间留出一段空地，"
            f"地上斜光像无形界线，前景桌角压低画幅。"
            f"门口仍亮，却谁也不走向那里。决绝、冷冽、裂痕，电影级画面。"
        ),
    },
    {
        "name": "07_S001_订亲正堂_木雁登场",
        "scene": "scene_001 seg1",
        "aspect_ratio": "16:9",
        "prompt": (
            f"中国古代宋朝风格的高家正堂内，白天，订亲仪式。"
            f"门框式构图，金银绸缎成列铺开作为聘礼。"
            f"{高父}居上首含笑，媒人立于聘礼旁。"
            f"{沈睿}站在后方半隐于礼器切割的空间里，沉默克制。"
            f"正中央最亮处偏偏放着一只格格不入的木雁——粗糙寒酸。"
            f"以{高令宁}入堂的主观视线掠过月白衣袖，"
            f"视线不落人脸，只穿过满堂聘礼直钉中央木雁。"
            f"木雁被金银绸缎包围，粗糙木纹被侧逆光刮亮，寒酸感在富贵堆里异常刺眼。"
            f"规整、体面、压抑、隐隐失礼，电影级古典中国画面。"
        ),
    },
    {
        "name": "08_S001_订亲正堂_伸手取雁",
        "scene": "scene_001 seg2",
        "aspect_ratio": "16:9",
        "prompt": (
            f"中国古代正堂内，订亲仪式，白天。"
            f"中近景：{高令宁}停在堂前右侧，半侧脸被窗棂光影切开，"
            f"目光锁向画外左前方木雁，脚步已收，神情由审视迅速沉成决断。"
            f"中景：{高父}坐于上首，对媒人与{沈睿}方向微微前倾，笑意殷勤。"
            f"而{沈睿}立在后侧半明半暗中垂眼不语，克制得近乎冷硬。"
            f"中景：不等礼数推进，{高令宁}自画面右侧直接伸手越过聘礼取向中央木雁，"
            f"身体斜线切破堂内原本的对称秩序，远处众人视线同时被她牵住。"
            f"克制、审视、暗流涌动、骤然越界，电影质感。"
        ),
    },
    {
        "name": "09_S001_订亲正堂_退还木雁",
        "scene": "scene_001 seg3",
        "aspect_ratio": "16:9",
        "prompt": (
            f"中国古代正堂内，订亲仪式，白天。"
            f"近景：{高令宁}的手从右侧将木雁径直递向媒人，"
            f"媒人的双手悬在接与不接之间，木雁居中,像一纸当众退回的羞辱。"
            f"媒人仓促把木雁接进怀里却抱得不稳，满堂体面开始裂缝外露。"
            f"{高父}正面笑意未净便骤然沉脸，案几和匾额将他压成将要发怒的家法象征。"
            f"{高令宁}抬起下巴，面向媒人与上首，语气平稳地说出:'聘礼太薄,我不满意。'"
            f"前景虚焦里仍是那只刚被退回的木雁，背景深处的{沈睿}尚未抬眼。"
            f"失礼、锋利、当众翻面、权力反转，电影级古典中国镜头。"
        ),
    },
    {
        "name": "10_S001_订亲正堂_对视识破",
        "scene": "scene_001 seg4",
        "aspect_ratio": "16:9",
        "prompt": (
            f"中国古代正堂内，订亲仪式，白天。"
            f"特写：{沈睿}在媒人肩线遮挡后猛地掀起眼皮，"
            f"窗光切入眸中，像无声接住{高令宁}抛来的刀。"
            f"中近景：限制性双视角——{高令宁}在右前，{沈睿}在左后，"
            f"中间隔着聘礼和媒人，两人隔空对视，彼此识破成为新的焦点。"
            f"中景：{高父}猛地拍案起身，茶盏轻震，手持般的轻晃把压抑空间一下撕开。"
            f"他前压斥责，门第与体面从口中砸向画外的女儿。"
            f"媒人抱着木雁被夹在父女之间左右劝解，谁都收不住局面。"
            f"{沈睿}仍站在纵深里冷眼旁观。"
            f"识破、反刺、威压、失控边缘，电影级古典中国画面。"
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
    log_file = os.path.join(OUTPUT_DIR, "generation_log_v2_cn.json")
    start_time = datetime.now()

    print("=" * 70)
    print(f"第7次测试结果 — 视频生成V2（中文提示词）：第1分钟（10段 x 6秒）")
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
            # 加 _v2 后缀区分中文版本
            filepath = os.path.join(OUTPUT_DIR, f"{name}_v2.mp4")
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
    print("Summary — 第1分钟视频生成结果（中文提示词V2）")
    print("=" * 70)
    success = 0
    fail = 0
    for name, info in results.items():
        if info.get("file_size_mb"):
            success += 1
            print(f"  OK    {name}_v2.mp4  ({info['file_size_mb']:.1f} MB)")
        else:
            fail += 1
            print(f"  FAIL  {name}  ({info['status']})")
    print(f"\n成功: {success}/10, 失败: {fail}/10")
    print(f"总耗时: {elapsed_total:.0f}s ({elapsed_total/60:.1f} min)")

    # 5. Save log
    log = {
        "test": "第7次测试结果_视频生成_第1分钟_V2_中文",
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
