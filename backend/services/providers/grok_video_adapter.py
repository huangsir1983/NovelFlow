"""Grok Video generation adapter — async task-based video API.

Protocol:
- Create task:  POST /v1/videos  → returns task_id + status
- Poll status:  GET  /v1/videos/{id}  → returns progress / video_url when completed
- Fallback:     GET  /v1/videos/{id}/content  → same as above
- Model:        grok-video-3
- Aspect ratio: 16:9 | 9:16
- Duration:     fixed 6 seconds
"""

import base64
import time
import logging
from dataclasses import dataclass

import httpx

from services.providers.base import ProviderAdapter, AIResponse

logger = logging.getLogger(__name__)

# Polling configuration
POLL_INTERVAL_S = 5       # seconds between polls
POLL_TIMEOUT_S = 300      # max wait time (5 minutes)


@dataclass
class VideoResponse:
    """Response from video generation."""
    video_url: str         # URL to download the generated video
    model: str
    task_id: str
    elapsed: float = 0.0
    provider_name: str = ""


class GrokVideoAdapter(ProviderAdapter):
    """Adapter for Grok Video generation API (POST /v1/videos).

    This is an async task-based API:
    1. Submit generation task → get task_id
    2. Poll task status until completed/failed
    3. Extract video URL from completed response
    """

    def __init__(self, *, base_url: str, api_key: str, provider_name: str = "Grok Video"):
        super().__init__(base_url=base_url, api_key=api_key, provider_name=provider_name)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_video(
        self,
        *,
        model: str,
        prompt: str,
        reference_image: bytes | None = None,
        reference_mime: str = "image/jpeg",
        aspect_ratio: str = "16:9",
        seconds: int = 6,
        size: str = "720P",
    ) -> VideoResponse:
        """Generate a video (text-to-video or image-to-video).

        Args:
            model: Model ID (e.g. "grok-video-3")
            prompt: Text prompt describing the video
            reference_image: Optional image bytes for image-to-video
            reference_mime: MIME type of reference image
            aspect_ratio: "16:9" or "9:16"
            seconds: Video duration (fixed at 6)
            size: Resolution ("720P")

        Returns:
            VideoResponse with video_url and metadata
        """
        # 1. Create task
        task_id = self._create_task(
            model=model,
            prompt=prompt,
            reference_image=reference_image,
            reference_mime=reference_mime,
            aspect_ratio=aspect_ratio,
            seconds=seconds,
            size=size,
        )

        # 2. Poll until completed or failed
        start = time.time()
        result = self._poll_task(task_id, start_time=start)

        elapsed = round(time.time() - start, 2)

        # 3. Extract video URL
        video_url = (
            result.get("video_url")
            or result.get("url")
            or (result.get("output", {}) or {}).get("url", "")
        )

        if not video_url:
            raise RuntimeError(f"Video task {task_id} completed but no video URL found in response")

        logger.info(
            "Video generated: task=%s, model=%s, elapsed=%.1fs, url=%s",
            task_id, model, elapsed, video_url[:80],
        )

        return VideoResponse(
            video_url=video_url,
            model=model,
            task_id=task_id,
            elapsed=elapsed,
            provider_name=self.provider_name,
        )

    def _create_task(
        self,
        *,
        model: str,
        prompt: str,
        reference_image: bytes | None,
        reference_mime: str,
        aspect_ratio: str,
        seconds: int,
        size: str,
    ) -> str:
        """Submit a video generation task. Returns task_id."""
        url = f"{self.base_url}/v1/videos"
        body: dict = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "seconds": seconds,
            "size": size,
        }

        # Image-to-video: attach reference image as base64
        if reference_image:
            b64 = base64.b64encode(reference_image).decode("utf-8")
            body["input_reference"] = f"data:{reference_mime};base64,{b64}"

        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=body, headers=self._headers())
            resp.raise_for_status()

        data = resp.json()

        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise RuntimeError(f"Video API did not return a task_id: {data}")

        status = data.get("status", "unknown")
        logger.info("Video task created: id=%s, status=%s", task_id, status)

        return task_id

    def _poll_task(self, task_id: str, *, start_time: float) -> dict:
        """Poll task status until completed or failed."""
        url = f"{self.base_url}/v1/videos/{task_id}"

        with httpx.Client(timeout=30) as client:
            while True:
                elapsed = time.time() - start_time
                if elapsed > POLL_TIMEOUT_S:
                    raise RuntimeError(
                        f"Video generation timed out after {POLL_TIMEOUT_S}s (task={task_id})"
                    )

                resp = client.get(url, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()

                status = data.get("status", "unknown")
                progress = data.get("progress", 0)

                if status == "completed":
                    return data

                if status == "failed":
                    error_msg = (data.get("error", {}) or {}).get("message", "Unknown error")
                    raise RuntimeError(f"Video generation failed: {error_msg} (task={task_id})")

                logger.debug(
                    "Video task %s: status=%s, progress=%s%%, elapsed=%.0fs",
                    task_id, status, progress, elapsed,
                )

                time.sleep(POLL_INTERVAL_S)

    # ── Required ProviderAdapter methods ──
    # These are text-oriented and not used for video generation,
    # but must be implemented to satisfy the abstract base class.

    def call(
        self,
        *,
        model: str,
        system: str = "",
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        raise NotImplementedError("GrokVideoAdapter does not support text calls. Use generate_video() instead.")

    def stream(self, **kwargs):
        raise NotImplementedError("GrokVideoAdapter does not support text streaming. Use generate_video() instead.")

    def health_check(self) -> bool:
        """Check if the video API is reachable."""
        try:
            # Try to hit the base URL or models endpoint
            url = f"{self.base_url}/v1/models"
            with httpx.Client(timeout=15) as client:
                resp = client.get(url, headers=self._headers())
                return resp.status_code == 200
        except Exception as e:
            logger.warning("Grok Video health check failed: %s", e)
            return False
