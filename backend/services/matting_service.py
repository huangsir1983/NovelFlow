"""
RunningHub 抠图服务 — 调用 RunningHub Matting App 去除图像背景，返回透明 PNG。

App ID: 2026922313706377217
Node ID: 1 (image input)
"""

import logging
import tempfile
from uuid import uuid4

from services.runninghub_client import RunningHubClient, RunningHubError

logger = logging.getLogger(__name__)

MATTING_APP_ID = "2026922313706377217"
MATTING_NODE_ID = "1"


def run_matting(
    client: RunningHubClient,
    image_path: str,
    *,
    instance_type: str = "default",
    poll_timeout: float = 300.0,
) -> bytes:
    """
    Upload an image, submit a matting task, poll until done, return result PNG bytes.

    Args:
        client: Configured RunningHubClient instance.
        image_path: Local path to the input image.
        instance_type: RunningHub instance type.
        poll_timeout: Max seconds to wait for result.

    Returns:
        Raw bytes of the matted (transparent-background) PNG image.

    Raises:
        RunningHubError: On upload, submission, polling, or download failure.
    """
    # 1. Upload source image
    logger.info("Matting: uploading image %s", image_path)
    download_url = client.upload_image(image_path)

    # 2. Submit matting task
    node_info_list = [
        {"nodeId": MATTING_NODE_ID, "fieldName": "image", "fieldValue": download_url},
    ]
    task_id = client.submit_task(
        app_id=MATTING_APP_ID,
        node_info_list=node_info_list,
        instance_type=instance_type,
    )
    logger.info("Matting: submitted task %s", task_id)

    # 3. Poll until done
    result = client.poll_until_done(task_id, poll_interval=3.0, timeout=poll_timeout)

    # 4. Download result
    results = result.get("results", [])
    if not results:
        raise RunningHubError("Matting: RunningHub returned no results")

    result_url = results[0] if isinstance(results[0], str) else results[0].get("url", "")
    if not result_url:
        raise RunningHubError("Matting: RunningHub returned empty result URL")

    logger.info("Matting: downloading result from %s", result_url[:80])
    return client._get_binary(result_url)
