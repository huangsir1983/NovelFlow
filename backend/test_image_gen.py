"""Test Gemini image generation via Comfly API."""

import base64
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, init_db
from models.ai_provider import AIProvider
from uuid import uuid4

init_db()
db = SessionLocal()

# Setup provider with image model
db.query(AIProvider).filter(AIProvider.name == "_img_test").delete()
db.commit()

provider = AIProvider(
    id=str(uuid4()),
    name="_img_test",
    provider_type="gemini",
    base_url="https://ai.comfly.chat",
    api_key="sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R",
    models=[
        {
            "model_id": "gemini-3.1-flash-lite-preview",
            "display_name": "Gemini Flash Lite",
            "model_type": "text",
            "capability_tier": "fast",
            "max_tokens": 8192,
            "supports_streaming": True,
        },
        {
            "model_id": "gemini-3.1-flash-image-preview",
            "display_name": "Gemini Flash Image (2K)",
            "model_type": "image",
            "capability_tier": "standard",
            "max_tokens": 8192,
            "supports_streaming": False,
        },
        {
            "model_id": "gemini-3.1-flash-image-preview-4k",
            "display_name": "Gemini Flash Image (4K)",
            "model_type": "image",
            "capability_tier": "advanced",
            "max_tokens": 8192,
            "supports_streaming": False,
        },
    ],
    is_default=True,
    enabled=True,
    priority=0,
)
db.add(provider)
db.commit()

from services.ai_engine import ai_engine
ai_engine.invalidate_cache()

output = []

try:
    output.append("=== Test: Gemini Image Generation ===")
    output.append("")

    result = ai_engine.generate_image(
        prompt="A cute cartoon cat sitting on a red cushion, simple illustration style, white background",
        aspect_ratio="1:1",
        image_size="1K",
        db=db,
    )

    output.append(f"Model: {result['model']}")
    output.append(f"Provider: {result['provider']}")
    output.append(f"Elapsed: {result['elapsed']}s")
    output.append(f"MIME type: {result['mime_type']}")
    output.append(f"Image size: {len(result['image_data'])} bytes ({len(result['image_data'])/1024:.1f} KB)")

    # Save image to file for inspection
    ext = "png" if "png" in result["mime_type"] else "jpg"
    img_path = f"test_generated_image.{ext}"
    with open(img_path, "wb") as f:
        f.write(result["image_data"])
    output.append(f"Image saved to: {img_path}")
    output.append("")
    output.append("[PASS] Image generation successful!")

except Exception as e:
    output.append(f"[FAIL] Error: {e}")
    import traceback
    output.append(traceback.format_exc())

finally:
    db.query(AIProvider).filter(AIProvider.name == "_img_test").delete()
    db.commit()
    db.close()
    ai_engine.invalidate_cache()

with open("test_image_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

for line in output:
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode())
