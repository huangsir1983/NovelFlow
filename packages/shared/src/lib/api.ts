export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Normalize a storage URI to an HTTP URL.
 *
 * LocalStorage returns absolute file paths (e.g. G:\...\backend\uploads\assets\images\xxx.jpeg).
 * This converts them to HTTP URLs served by the backend's /uploads static mount.
 * Also handles relative paths, HTTP URLs, and data URIs.
 */
export function normalizeStorageUrl(url: string | undefined | null): string {
  if (!url) return '';
  // Already an HTTP URL
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  // Base64 data URL — pass through
  if (url.startsWith('data:')) return url;
  // File system path (Windows or Unix) containing /uploads/ — extract from /uploads/ onwards
  const normalized = url.replace(/\\/g, '/');
  const uploadsIdx = normalized.indexOf('/uploads/');
  if (uploadsIdx !== -1) {
    return `${API_BASE_URL}${normalized.slice(uploadsIdx)}`;
  }
  // Relative path starting with /
  if (url.startsWith('/')) return `${API_BASE_URL}${url}`;
  return url;
}

/** Generic fetch wrapper for JSON API calls */
export async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/** Fetch wrapper for streaming responses (AI operations) */
export async function fetchAPIStream(
  endpoint: string,
  body: Record<string, unknown>,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value, { stream: true });
    onChunk(text);
  }
}
