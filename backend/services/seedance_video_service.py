"""
Seedance Video Service — 映话全能视频S API client.

Model: seedance-2.0-fast
Submit async task → poll for status → return video URL on success.
"""

import logging
import httpx

logger = logging.getLogger(__name__)

SUBMIT_TIMEOUT = 30.0
POLL_TIMEOUT = 15.0


async def submit_seedance_task(
    api_key: str,
    base_url: str,
    prompt: str,
    file_paths: list[str],
    ratio: str = "16:9",
    duration: int = 5,
) -> str:
    """Submit an async video generation task. Returns task_id."""
    url = f"{base_url}/async"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "seedance-2.0-fast",
        "prompt": prompt,
        "file_paths": file_paths,
        "ratio": ratio,
        "duration": duration,
    }
    logger.info("Seedance submit: prompt=%s chars, %d images, ratio=%s, dur=%ds",
                len(prompt), len(file_paths), ratio, duration)

    async with httpx.AsyncClient(timeout=SUBMIT_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    task_id = data.get("task_id") or data.get("id") or ""
    if not task_id:
        raise ValueError(f"Seedance submit returned no task_id: {data}")

    logger.info("Seedance task submitted: %s", task_id)
    return task_id


async def poll_seedance_task(
    api_key: str,
    base_url: str,
    task_id: str,
) -> dict:
    """
    Poll task status once.

    Returns dict with keys:
      - status: 'queued' | 'in_progress' | 'succeeded' | 'failed'
      - progress: int (0-100, estimated)
      - video_url: str | None (on success)
      - error: str | None (on failure)
    """
    url = f"{base_url}/async/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=POLL_TIMEOUT) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    status = data.get("status", "queued")
    result = {
        "status": status,
        "progress": 0,
        "video_url": None,
        "error": None,
    }

    if status == "in_progress":
        result["progress"] = data.get("progress", 50)
    elif status == "succeeded":
        result["progress"] = 100
        metadata = data.get("metadata", {})
        result["video_url"] = metadata.get("url")
    elif status == "failed":
        err = data.get("error", {})
        result["error"] = err.get("message", "Unknown error")

    return result
