# GROK 6秒视频接入 API 文档（兼容版）

## 1. 目标协议（按当前兼容约定）

- 统一模型名称：`grok-video-3`（只用这一个）
- 创建任务接口：`POST /v1/videos`
- 查询任务接口：`GET /v1/videos/{id}`
- 内容兜底接口：`GET /v1/videos/{id}/content`
- 图生视频：`input_reference` 传 base64（支持 data URI / 原始 base64）
- 视频比例：仅使用 `16:9` 或 `9:16`
- 本文档场景：固定 6 秒（`seconds=6`）

## 2. 基础信息

- `BASE_URL`：`http://47.99.182.38:8000`
- `Header`：
  - `Authorization: Bearer <API_KEY>`
  - `Content-Type: application/json`

## 3. 创建任务（文生视频，6秒）

### 请求

`POST /v1/videos`

```json
{
  "model": "grok-video-3",
  "prompt": "A cinematic drone flyover above ocean cliffs at sunrise, realistic, smooth motion",
  "aspect_ratio": "16:9",
  "seconds": 6,
  "size": "720P"
}
```

### 成功响应（示例）

```json
{
  "id": "2eba9739-5aa9-4aba-a33e-c0a88dcff54b",
  "task_id": "2eba9739-5aa9-4aba-a33e-c0a88dcff54b",
  "object": "video",
  "model": "grok-video-3",
  "status": "queued",
  "progress": 0,
  "created_at": 1772771700,
  "size": "720P"
}
```

## 4. 创建任务（图生视频，base64，6秒）

### 请求

`POST /v1/videos`

```json
{
  "model": "grok-video-3",
  "prompt": "A cinematic dolly shot around the subject with realistic motion and lighting",
  "aspect_ratio": "16:9",
  "seconds": 6,
  "size": "720P",
  "input_reference": "data:image/jpeg;base64,<YOUR_BASE64>"
}
```

说明：
- `input_reference` 支持：
  - `data:image/...;base64,...`
  - 原始 base64 字符串
  - `http/https` 图片 URL
- 图生视频当前按单图处理（多图只取第一张）

## 5. 轮询查询

### 请求

`GET /v1/videos/{id}`

### 进行中响应（示例）

```json
{
  "id": "3569469b-7c55-43b0-aa27-20730c86a15c",
  "task_id": "3569469b-7c55-43b0-aa27-20730c86a15c",
  "object": "video",
  "model": "grok-video-3",
  "status": "processing",
  "progress": 10,
  "created_at": 1772771786,
  "size": "720P"
}
```

### 完成响应（示例）

```json
{
  "id": "3569469b-7c55-43b0-aa27-20730c86a15c",
  "task_id": "3569469b-7c55-43b0-aa27-20730c86a15c",
  "object": "video",
  "model": "grok-video-3",
  "status": "completed",
  "progress": 100,
  "created_at": 1772771786,
  "size": "720P",
  "url": "http://47.99.182.38:8000/v1/files/video/users/40a2515d-83d9-416b-b7a0-aab931292c74/generated/d6414074-4608-452f-87a0-36de4a78b7b9/generated_video.mp4",
  "video_url": "http://47.99.182.38:8000/v1/files/video/users/40a2515d-83d9-416b-b7a0-aab931292c74/generated/d6414074-4608-452f-87a0-36de4a78b7b9/generated_video.mp4",
  "output": {
    "url": "http://47.99.182.38:8000/v1/files/video/users/40a2515d-83d9-416b-b7a0-aab931292c74/generated/d6414074-4608-452f-87a0-36de4a78b7b9/generated_video.mp4"
  }
}
```

## 6. 内容兜底（可选）

### 请求

`GET /v1/videos/{id}/content`

### 返回

任务完成时返回同样的 `url/video_url/output.url`，可作为兜底取视频地址。

## 7. 状态与错误

- 进行中：`queued` / `processing`
- 成功：`completed`（必须带 `url`）
- 失败：`failed`（返回 `error.message`）

常见失败：
- `invalid_seconds`：`seconds` 非 `6`
- `invalid_aspect_ratio`：比例不是 `16:9`/`9:16`（按接入约束）
- `upstream_error`：上游网络/账号/上传失败

## 8. 本次实测结果

- 文生 6 秒：成功
  - 任务 ID：`2eba9739-5aa9-4aba-a33e-c0a88dcff54b`
  - 完成视频：`http://47.99.182.38:8000/v1/files/video/users/b6983be1-9212-45fc-a2a6-910553d03955/generated/bf7aabe1-858c-4f77-9592-a09a4226f5ae/generated_video_hd.mp4`
- 图生 6 秒（base64）：成功
  - 任务 ID：`3569469b-7c55-43b0-aa27-20730c86a15c`
  - 完成视频：`http://47.99.182.38:8000/v1/files/video/users/40a2515d-83d9-416b-b7a0-aab931292c74/generated/d6414074-4608-452f-87a0-36de4a78b7b9/generated_video.mp4`

