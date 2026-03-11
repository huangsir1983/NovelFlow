"""Test Grok text API — grok-4.20-beta."""

import json
import sys
import time
import io

# Fix Windows GBK encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import httpx

BASE_URL = "https://yhgrok.xuhuanai.cn"
API_KEY = "V378STSBi6jAC9Gk"
MODEL = "grok-4.20-beta"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

print("=" * 60)
print(f"TEST: Grok Text ({MODEL})")
print("=" * 60)

# 1. Health check
print("\n[1] Health check... ", end="", flush=True)
try:
    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{BASE_URL}/v1/models", headers=headers)
        print(f"Status {resp.status_code} OK")
except Exception as e:
    print(f"WARN: {e}")

# 2. Sync call
print("\n[2] Sync call (non-stream)... ", flush=True)
body = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": "You are a helpful assistant. Reply in Chinese, keep it short."},
        {"role": "user", "content": "用一句话介绍你自己"},
    ],
    "stream": False,
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

# 3. Stream call
print("\n[3] Stream call... ", flush=True)
body_stream = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "用两句话描述夏天"}],
    "stream": True,
}
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

# 4. Multi-turn
print("\n[4] Multi-turn... ", flush=True)
body_multi = {
    "model": MODEL,
    "messages": [
        {"role": "user", "content": "我叫小王"},
        {"role": "assistant", "content": "你好，小王。"},
        {"role": "user", "content": "记住我的名字，然后再说一遍"},
    ],
    "stream": False,
}
try:
    start = time.time()
    with httpx.Client(timeout=120) as client:
        resp = client.post(f"{BASE_URL}/v1/chat/completions", json=body_multi, headers=headers)
        resp.raise_for_status()
    elapsed = round(time.time() - start, 2)
    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    has_name = "小王" in content
    print(f"  Elapsed: {elapsed}s")
    print(f"  Content: {content[:300]}")
    print(f"  Remembers name: {'YES' if has_name else 'NO'}")
    print("  >> PASS" if has_name else "  >> WARN")
except Exception as e:
    print(f"  >> FAIL: {e}")

print("\n" + "=" * 60)
print("All tests complete.")
