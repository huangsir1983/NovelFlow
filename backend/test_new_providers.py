"""Test the two new providers: GCLI text + NanoBanana image.

Standalone test — imports only what's needed, no full registry dependency.
"""

import sys
import os
import json
import time
import base64
import re

import httpx

# ── 1. Test GCLI Text (OpenAI Compat) ──

def test_gcli_text():
    print("=" * 60)
    print("TEST 1: GCLI Text (gemini-3.1-pro-preview)")
    print("=" * 60)

    BASE_URL = "https://yhgcli.xuhuanai.cn"
    API_KEY = "ghitavjlksjkvnklghrvjog"
    MODEL = "gemini-3.1-pro-preview"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # 1a. Health check — GET /v1/models
    print("\n[1a] Health check (GET /v1/models)... ", end="", flush=True)
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(f"{BASE_URL}/v1/models", headers=headers)
            print(f"Status {resp.status_code} {'OK' if resp.status_code == 200 else 'WARN'}")
    except Exception as e:
        print(f"WARN: {e}")

    # 1b. Sync call (non-stream)
    print("\n[1b] Sync call (non-stream)... ", flush=True)
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Reply in Chinese, keep it short."},
            {"role": "user", "content": "用一句话介绍你自己"},
        ],
        "temperature": 0.7,
        "max_tokens": 256,
    }
    try:
        start = time.time()
        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{BASE_URL}/v1/chat/completions", json=body, headers=headers)
            resp.raise_for_status()
        elapsed = round(time.time() - start, 2)
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        print(f"  Model:   {data.get('model', MODEL)}")
        print(f"  Tokens:  {usage.get('prompt_tokens', '?')} in / {usage.get('completion_tokens', '?')} out")
        print(f"  Elapsed: {elapsed}s")
        print(f"  Content: {content[:300]}")
        print("  >> PASS")
    except Exception as e:
        print(f"  >> FAIL: {e}")

    # 1c. Stream call
    print("\n[1c] Stream call... ", flush=True)
    body_stream = {**body, "stream": True}
    body_stream["messages"] = [
        {"role": "user", "content": "用两句话描述春天"},
    ]
    try:
        chunks = []
        start = time.time()
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", f"{BASE_URL}/v1/chat/completions", json=body_stream, headers=headers) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            chunks.append(text)
                            print(text, end="", flush=True)
                    except json.JSONDecodeError:
                        continue
        elapsed = round(time.time() - start, 2)
        full_text = "".join(chunks)
        print(f"\n  Stream elapsed: {elapsed}s, chunks: {len(chunks)}, total chars: {len(full_text)}")
        print("  >> PASS" if full_text else "  >> FAIL: empty response")
    except Exception as e:
        print(f"\n  >> FAIL: {e}")

    print()


# ── 2. Test NanoBanana Image ──

RATIO_SUFFIX_MAP = {
    "16:9": "landscape",
    "9:16": "portrait",
    "1:1": "square",
    "4:3": "four-three",
    "3:4": "three-four",
}
SIZE_SUFFIX_MAP = {
    "1K": "",
    "2K": "-2k",
    "4K": "-4k",
}


def build_image_model_name(prefix, aspect_ratio="16:9", image_size="1K"):
    ratio_suffix = RATIO_SUFFIX_MAP.get(aspect_ratio, "landscape")
    size_suffix = SIZE_SUFFIX_MAP.get(image_size, "")
    return f"{prefix}-{ratio_suffix}{size_suffix}"


def extract_image_from_text(text):
    """Parse response text to extract image data."""
    text = text.strip()

    # data URL (base64)
    data_url_match = re.search(r'data:(image/[a-zA-Z+]+);base64,([A-Za-z0-9+/=\s]+)', text)
    if data_url_match:
        mime = data_url_match.group(1)
        b64_data = data_url_match.group(2).replace("\n", "").replace(" ", "")
        try:
            return base64.b64decode(b64_data), mime
        except Exception:
            pass

    # Markdown image with URL
    md_match = re.search(r'!\[.*?\]\((https?://[^\s)]+)\)', text)
    if md_match:
        url = md_match.group(1)
        return download_image(url)

    # JSON with url
    json_match = re.search(r'\{[^}]*"url"\s*:\s*"(https?://[^"]+)"[^}]*\}', text)
    if json_match:
        url = json_match.group(1)
        return download_image(url)

    # Plain URL
    url_match = re.search(r'(https?://\S+\.(?:png|jpg|jpeg|webp|gif)(?:\?\S*)?)', text, re.IGNORECASE)
    if url_match:
        url = url_match.group(1)
        return download_image(url)

    return None


def download_image(url):
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            mime = resp.headers.get("content-type", "image/png").split(";")[0].strip()
            return resp.content, mime
    except Exception as e:
        print(f"    Download failed: {e}")
        return None


def test_nanobanana_image():
    print("=" * 60)
    print("TEST 2: NanoBanana Image (gemini-3.1-flash-image)")
    print("=" * 60)

    BASE_URL = "https://yhflow.xuhuanai.cn"
    API_KEY = "gaiohtldtbnfakhtljkhg"
    PREFIX = "gemini-3.1-flash-image"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # 2a. Model name construction
    print("\n[2a] Model name construction:")
    tests = [
        ("16:9", "1K", "gemini-3.1-flash-image-landscape"),
        ("16:9", "2K", "gemini-3.1-flash-image-landscape-2k"),
        ("9:16", "4K", "gemini-3.1-flash-image-portrait-4k"),
        ("1:1", "1K", "gemini-3.1-flash-image-square"),
        ("4:3", "2K", "gemini-3.1-flash-image-four-three-2k"),
        ("3:4", "4K", "gemini-3.1-flash-image-three-four-4k"),
    ]
    all_pass = True
    for ratio, size, expected in tests:
        result = build_image_model_name(PREFIX, ratio, size)
        ok = result == expected
        all_pass = all_pass and ok
        status = "OK" if ok else f"FAIL (got {result})"
        print(f"  {ratio} + {size} -> {expected}  {status}")
    print(f"  >> {'ALL PASS' if all_pass else 'SOME FAILED'}")

    # 2b. Health check
    print(f"\n[2b] Health check (GET /v1/models)... ", end="", flush=True)
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(f"{BASE_URL}/v1/models", headers=headers)
            print(f"Status {resp.status_code} {'OK' if resp.status_code == 200 else '(may not support, not critical)'}")
    except Exception as e:
        print(f"WARN: {e}")

    # 2c. Text-to-image (stream)
    print("\n[2c] Text-to-image (16:9, 1K)... ", flush=True)
    full_model = build_image_model_name(PREFIX, "16:9", "1K")
    print(f"  Model name: {full_model}")

    body = {
        "model": full_model,
        "messages": [
            {"role": "user", "content": "一只橘猫坐在窗台上，午后阳光，写实风格"}
        ],
        "stream": True,
    }

    try:
        accumulated = []
        start = time.time()
        with httpx.Client(timeout=180) as client:
            with client.stream("POST", f"{BASE_URL}/v1/chat/completions", json=body, headers=headers) as resp:
                resp.raise_for_status()
                print(f"  HTTP status: {resp.status_code}")
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            text = delta.get("content", "") or delta.get("reasoning_content", "")
                            if text:
                                accumulated.append(text)
                    except json.JSONDecodeError:
                        continue

        elapsed = round(time.time() - start, 2)
        full_text = "".join(accumulated)
        print(f"  Elapsed: {elapsed}s")
        print(f"  Response length: {len(full_text)} chars")
        print(f"  Response preview: {full_text[:200]}{'...' if len(full_text) > 200 else ''}")

        # Extract image
        result = extract_image_from_text(full_text)
        if result:
            image_bytes, mime_type = result
            ext = mime_type.split("/")[-1].replace("jpeg", "jpg")
            filename = f"test_nanobanana_output.{ext}"
            with open(filename, "wb") as f:
                f.write(image_bytes)
            print(f"  Image MIME: {mime_type}")
            print(f"  Image size: {len(image_bytes)} bytes")
            print(f"  Saved to:   {filename}")
            print("  >> PASS")
        else:
            print(f"  >> FAIL: could not extract image from response")
            # Save raw response for debugging
            with open("test_nanobanana_raw.txt", "w", encoding="utf-8") as f:
                f.write(full_text)
            print(f"  Raw response saved to test_nanobanana_raw.txt")

    except Exception as e:
        print(f"  >> FAIL: {e}")

    print()


if __name__ == "__main__":
    print("Testing new providers...\n")

    test_gcli_text()
    test_nanobanana_image()

    print("=" * 60)
    print("All tests complete.")
