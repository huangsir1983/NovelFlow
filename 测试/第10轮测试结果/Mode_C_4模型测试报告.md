# Mode C 后端管线 — 4模型验证测试报告

> 测试时间: 2026-03-10
> 测试小说: 《我和沈词的长子》(13,173字符, GB18030)
> 管线: streaming -> locations -> props -> variants (3阶段资产管线)

---

## 一、最佳配置汇总

| 模型 | 第三方渠道 | 模型ID | 协议 | 流式 |
|------|-----------|--------|------|------|
| ChatGPT | openclaudecode.cn | gpt-5.4 | Responses API | Yes |
| Claude | ai.comfly.chat | claude-opus-4-6 | OpenAI Chat | Yes |
| Gemini | yhgcli.xuhuanai.cn | gemini-3.1-pro-preview | OpenAI Chat | Yes |
| Grok | yhgrok.xuhuanai.cn | grok-4.20-beta | OpenAI Chat | Yes |

---

## 二、各模型详细结果

### ChatGPT (gpt-5.4) — 综合最强

| 指标 | 数值 |
|------|------|
| 第三方 | https://www.openclaudecode.cn/v1/responses |
| API Key | sk-S2HdTV...ct50e (OCC) |
| 总耗时 | **677s** (Stage1: 295s, Stage2+3: 382s) |
| 首卡时间 | **32.9s** |
| 流式chunks | 12,804 |
| 角色 | **13** (高令宁/沈词/陆姝仪/高父/蒋晟/沈母/沈睿/沈昭昭/媒人/沈府小厮/陆姝仪婢女/稳婆/太医) |
| 叙事场景 | **17** |
| 位置卡 | **17** |
| 道具 | **142** (major: 3) |
| 角色变体 | **23** (4个eligible角色, 平均5.75变体/角色) |
| 整体质量 | **A+** 提取最全面, 角色覆盖所有主次配角, 道具数远超其他模型, 变体最丰富 |
| 缺点 | 耗时最长(677s), 首卡较慢(33s), 位置卡生成单次调用206s |

### Claude (claude-opus-4-6) — 速度最快

| 指标 | 数值 |
|------|------|
| 第三方 | https://ai.comfly.chat/v1 |
| API Key | sk-4f5dNl...fzD6R (Comfly) |
| 总耗时 | **249s** (Stage1: 108s, Stage2+3: 141s) |
| 首卡时间 | **17.7s** (最快) |
| 流式chunks | 1,131 |
| 角色 | **10** (高令宁/沈词/陆姝仪/沈睿/昭昭/高父/蒋晟/沈母/媒人/江南赘婿们) |
| 叙事场景 | **14** (含2个流式后补充解析) |
| 位置卡 | **11** (含高府廊下/高府厢房等细分) |
| 道具 | **49** (major: 2) |
| 角色变体 | **16** (4个eligible角色, 平均4变体/角色) |
| 整体质量 | **A** 速度最快, 首卡17.7s体验最好, 角色抽象合理("江南赘婿们"作为群体角色) |
| 缺点 | chunk数少(1131 vs GPT 12804), 道具数中等, 角色少3个次要配角 |

### Gemini (gemini-3.1-pro-preview) — 场景最多

| 指标 | 数值 |
|------|------|
| 第三方 | https://yhgcli.xuhuanai.cn/v1 |
| API Key | ghitav...rvjog (GCLI) |
| 总耗时 | **379s** (Stage1: 154s, Stage2+3: 225s) |
| 首卡时间 | **59.5s** |
| 流式chunks | 126 |
| 角色 | **7** (高令宁/沈词/陆姝仪/高父/蒋晟/沈睿/昭昭) |
| 叙事场景 | **18** (最多) |
| 位置卡 | **16** |
| 道具 | **57** (major: 0) |
| 角色变体 | **11** (3个eligible角色) |
| 整体质量 | **B+** 场景拆分最细(18个), 位置卡丰富(16个), 但角色偏少, 无major道具 |
| 缺点 | 首卡慢(59.5s), 角色只有7个(缺沈母/媒人等), chunk数极少(126) |

**Gemini 渠道测试历史:**

| 渠道 | 模型 | 流式 | 结果 |
|------|------|------|------|
| comfly.chat | gemini-2.5-pro | No | Stage1 OK(8角色+19场景), Stage2断连 |
| yhgcli | gemini-3.1-pro-preview | Stream | 空响应(第一次), 后来成功 |
| comfly.chat | gemini-3.1-pro-preview | Stream | 5角色但断连 |
| yhgcli | gemini-3.1-pro-preview | No | 第一次403, 后来OK(6角色+16场景) |
| comfly.chat | gemini-3.1-flash-lite-preview | No | OK但太弱(3角色+5场景) |
| comfly.chat | gemini-3-pro-preview | No | OK(5角色+13场景) |
| **yhgcli** | **gemini-3.1-pro-preview** | **Stream** | **最佳: 7角色+18场景+16位置卡** |

### Grok (grok-4.20-beta) — 稳定均衡

| 指标 | 数值 |
|------|------|
| 第三方 | https://yhgrok.xuhuanai.cn/v1 |
| API Key | V378ST...C9Gk (GROK) |
| 总耗时 | **621s** (Stage1: 199s, Stage2+3: 422s) |
| 首卡时间 | **75.8s** |
| 流式chunks | 5,672 |
| 角色 | **8** (高令宁/沈词/陆姝仪/高父/蒋晟/沈母/沈睿/昭昭) |
| 叙事场景 | **14** |
| 位置卡 | **13** |
| 道具 | **52** (major: 0) |
| 角色变体 | **15** (3个eligible角色, 平均5变体/角色) |
| 整体质量 | **B+** 各项指标均衡, 全流程无异常, 稳定性好 |
| 缺点 | 耗时长(621s), 首卡最慢(75.8s), 无major道具, 位置卡生成173s |

---

## 三、对比排名

### 综合排名
1. **ChatGPT (gpt-5.4)** — 质量最优, 各项指标全面领先
2. **Claude (opus-4-6)** — 速度最快, 性价比最高, 推荐生产环境
3. **Gemini (3.1-pro)** — 场景拆分最细, 但角色偏少
4. **Grok (4.20-beta)** — 均衡稳定, 无明显短板也无明显优势

### 单项最佳
| 维度 | 最佳模型 | 数值 |
|------|---------|------|
| 首卡速度 | Claude | 17.7s |
| 总耗时 | Claude | 249s |
| 角色数量 | ChatGPT | 13 |
| 场景数量 | Gemini | 18 |
| 位置卡 | ChatGPT | 17 |
| 道具总数 | ChatGPT | 142 |
| 角色变体 | ChatGPT | 23 |
| 流式chunk密度 | ChatGPT | 12,804 |

### 生产环境推荐
- **首选**: Claude opus-4-6 (速度快+质量好, 249s完成全流程)
- **质量优先**: ChatGPT gpt-5.4 (最全面但慢, 677s)
- **备选**: Gemini 3.1-pro (yhgcli渠道, 场景细致)
- **兜底**: Grok 4.20-beta (最稳定, 从不断连)

---

## 四、管线加固验证

| 加固措施 | 触发情况 |
|---------|---------|
| 加固1: 断连重试 | Gemini comfly渠道Stage2触发3次重试 |
| 加固2: think标签清洗 | 未触发(4模型均未返回think标签) |
| 加固3: 增量扫描 | 全部模型正常工作, 无重复解析 |
| 加固4: 截断检测 | Gemini comfly流式触发(角色完整+场景为0) |
| 加固5: 场景兜底 | Gemini comfly流式触发独立场景提取 |
| 加固6: 非流式降级 | Gemini yhgcli首次流式0 chunks触发降级 |

---

## 五、API Key 备忘

| 渠道 | Key变量 | 用途 |
|------|--------|------|
| openclaudecode.cn | _OCC_KEY = sk-S2HdTVBy...ct50e | ChatGPT |
| ai.comfly.chat | _COMFLY_KEY = sk-4f5dNlvb...fzD6R | Claude / Gemini(备选) |
| yhgcli.xuhuanai.cn | _GCLI_KEY = ghitav...rvjog | Gemini(推荐) |
| yhgrok.xuhuanai.cn | _GROK_KEY = V378ST...C9Gk | Grok |
