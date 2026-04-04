"""
RunningHub HD Upscale service -- upscale images via RunningHub ComfyUI workflow.

App ID: 2026926386652385282
Node 16: image input
Node 21: target size (single-side pixel count)
"""

import logging

from services.runninghub_client import RunningHubClient, RunningHubError

logger = logging.getLogger(__name__)

HD_UPSCALE_APP_ID = "2026926386652385282"
IMAGE_NODE_ID = "16"
SIZE_NODE_ID = "21"

SIZE_MAP = {"1K": "1024", "2K": "2048", "4K": "4096"}


def run_hd_upscale(
    client: RunningHubClient,
    image_path: str,
    *,
    image_size: str = "2K",
    instance_type: str = "default",
    poll_timeout: float = 600.0,
) -> bytes:
    """
    Upload an image, submit an HD upscale task, poll until done, return result bytes.

    Args:
        client: Configured RunningHubClient instance.
        image_path: Local path to the input image.
        image_size: Target size key ("1K", "2K", "4K").
        instance_type: RunningHub instance type.
        poll_timeout: Max seconds to wait for result.

    Returns:
        Raw bytes of the upscaled image.

    Raises:
        RunningHubError: On upload, submission, polling, or download failure.
    """
    # 1. Upload source image
    logger.info("HD Upscale: uploading image %s", image_path)
    download_url = client.upload_image(image_path)

    # 2. Submit upscale task
    size_value = SIZE_MAP.get(image_size, "2048")
    node_info_list = [
        {"nodeId": IMAGE_NODE_ID, "fieldName": "image", "fieldValue": download_url},
        {"nodeId": SIZE_NODE_ID, "fieldName": "value", "fieldValue": size_value},
    ]
    task_id = client.submit_task(
        app_id=HD_UPSCALE_APP_ID,
        node_info_list=node_info_list,
        instance_type=instance_type,
    )
    logger.info("HD Upscale: submitted task %s (size=%s)", task_id, size_value)

    # 3. Poll until done
    result = client.poll_until_done(task_id, poll_interval=3.0, timeout=poll_timeout)

    # 4. Download result
    results = result.get("results", [])
    if not results:
        raise RunningHubError("HD Upscale: RunningHub returned no results")

    result_url = results[0] if isinstance(results[0], str) else results[0].get("url", "")
    if not result_url:
        raise RunningHubError("HD Upscale: RunningHub returned empty result URL")

    logger.info("HD Upscale: downloading result from %s", result_url[:80])
    return client._get_binary(result_url)
