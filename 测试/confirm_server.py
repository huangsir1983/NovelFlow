"""Web 确认服务 — 阶段式流水线的浏览器确认页面.

职责:
  - 启动临时 HTTP 服务（默认 localhost:5678）
  - 展示当前阶段的结果卡片
  - 提供「继续」「重跑」「停止」三个操作按钮
  - Phase B: 勾选框选择可选阶段 + 目标模型配置
  - 使用 threading.Event 阻塞主线程等待用户确认
  - 零外部依赖（Python 内置 http.server + 内嵌 HTML）
"""

import json
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler


# ── 内嵌 HTML 页面（标准确认） ────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>流水线确认 — {stage_name}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f172a; color: #e2e8f0;
    min-height: 100vh; padding: 2rem;
  }
  .container { max-width: 900px; margin: 0 auto; }
  .header {
    text-align: center; padding: 2rem 0; border-bottom: 1px solid #334155;
    margin-bottom: 2rem;
  }
  .header h1 { font-size: 1.8rem; color: #38bdf8; margin-bottom: 0.5rem; }
  .header .stage-badge {
    display: inline-block; background: #1e3a5f; color: #7dd3fc;
    padding: 0.25rem 1rem; border-radius: 9999px; font-size: 0.85rem;
  }
  .cards { display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 2rem; }
  .card {
    background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem;
    padding: 1rem 1.25rem; transition: border-color 0.2s;
  }
  .card:hover { border-color: #475569; }
  .card .label { color: #94a3b8; font-size: 0.8rem; margin-bottom: 0.25rem; }
  .card .value { color: #f1f5f9; font-size: 0.95rem; line-height: 1.5; }
  .card .value.highlight { color: #38bdf8; font-weight: 600; }
  .stats {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 0.75rem; margin-bottom: 2rem;
  }
  .stat {
    background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem;
    padding: 1rem; text-align: center;
  }
  .stat .num { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .stat .lbl { font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem; }
  .items { margin-bottom: 2rem; }
  .items h3 { color: #94a3b8; font-size: 0.85rem; margin-bottom: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .item-row {
    display: flex; align-items: baseline; gap: 0.75rem;
    padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e293b;
    font-size: 0.9rem;
  }
  .item-row:hover { background: #1e293b; border-radius: 0.5rem; }
  .item-idx { color: #475569; min-width: 2rem; text-align: right; font-variant-numeric: tabular-nums; }
  .item-name { color: #f1f5f9; font-weight: 500; min-width: 6rem; }
  .item-tag {
    display: inline-block; background: #1e3a5f; color: #7dd3fc;
    padding: 0.1rem 0.5rem; border-radius: 0.25rem; font-size: 0.75rem;
  }
  .item-desc { color: #94a3b8; flex: 1; }
  .cost-bar {
    background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem;
    padding: 0.75rem 1.25rem; margin-bottom: 2rem; text-align: center;
    font-size: 0.85rem; color: #94a3b8;
  }
  .cost-bar .cost-value { color: #38bdf8; font-weight: 600; }
  .actions {
    display: flex; gap: 1rem; justify-content: center;
    padding: 2rem 0; border-top: 1px solid #334155;
  }
  .btn {
    padding: 0.75rem 2rem; border: none; border-radius: 0.5rem;
    font-size: 1rem; font-weight: 600; cursor: pointer; transition: all 0.2s;
  }
  .btn-continue { background: #22c55e; color: #052e16; }
  .btn-continue:hover { background: #16a34a; transform: translateY(-1px); }
  .btn-retry { background: #eab308; color: #422006; }
  .btn-retry:hover { background: #ca8a04; transform: translateY(-1px); }
  .btn-stop { background: #ef4444; color: #fff; }
  .btn-stop:hover { background: #dc2626; transform: translateY(-1px); }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
  .status {
    text-align: center; padding: 1rem; color: #94a3b8; font-size: 0.9rem;
    display: none;
  }
  .status.show { display: block; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{stage_name}</h1>
    <span class="stage-badge">Stage {stage_number} / {total_stages}</span>
  </div>
  <div id="content">Loading...</div>
  <div id="status" class="status"></div>
  <div class="actions" id="actions">
    <button class="btn btn-continue" onclick="confirm('continue')">继续下一阶段</button>
    <button class="btn btn-retry" onclick="confirm('retry')">重跑本阶段</button>
    <button class="btn btn-stop" onclick="confirm('stop')">停止流水线</button>
  </div>
</div>
<script>
async function loadData() {
  try {
    const resp = await fetch('/api/stage-data');
    const data = await resp.json();
    renderData(data);
  } catch(e) {
    document.getElementById('content').innerHTML = '<p style="color:#ef4444">加载失败: ' + e.message + '</p>';
  }
}

function renderData(data) {
  const el = document.getElementById('content');
  let html = '';

  if (data.cost) {
    html += '<div class="cost-bar">';
    html += '成本: <span class="cost-value">' + (data.cost.api_calls || '?') + '</span> 次调用';
    html += ' | <span class="cost-value">' + (data.cost.tokens || '?') + '</span> tokens';
    html += ' | <span class="cost-value">' + (data.cost.elapsed || '?') + '</span>s';
    html += '</div>';
  }

  if (data.stats) {
    html += '<div class="stats">';
    for (const [k, v] of Object.entries(data.stats)) {
      html += `<div class="stat"><div class="num">${v}</div><div class="lbl">${k}</div></div>`;
    }
    html += '</div>';
  }

  if (data.items && data.items.length > 0) {
    html += '<div class="items"><h3>' + (data.items_title || '详细列表') + '</h3>';
    for (const item of data.items) {
      html += '<div class="item-row">';
      html += `<span class="item-idx">${item.idx ?? ''}</span>`;
      html += `<span class="item-name">${item.name ?? ''}</span>`;
      if (item.tag) html += `<span class="item-tag">${item.tag}</span>`;
      if (item.desc) html += `<span class="item-desc">${item.desc}</span>`;
      html += '</div>';
    }
    html += '</div>';
  }

  if (data.cards) {
    html += '<div class="cards">';
    for (const card of data.cards) {
      html += '<div class="card">';
      if (card.label) html += `<div class="label">${card.label}</div>`;
      const cls = card.highlight ? 'value highlight' : 'value';
      html += `<div class="${cls}">${card.value ?? ''}</div>`;
      html += '</div>';
    }
    html += '</div>';
  }

  el.innerHTML = html || '<p>暂无数据</p>';
}

async function confirm(action) {
  const btns = document.querySelectorAll('.btn');
  btns.forEach(b => b.disabled = true);
  const status = document.getElementById('status');
  const labels = { continue: '继续中...', retry: '正在重跑...', stop: '已停止' };
  status.textContent = labels[action] || action;
  status.classList.add('show');

  try {
    await fetch('/api/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    if (action === 'continue') {
      status.textContent = '已确认，等待下一阶段...';
    } else if (action === 'stop') {
      status.textContent = '流水线已停止，可关闭此页面。';
    }
  } catch(e) {
    status.textContent = '通信失败: ' + e.message;
    btns.forEach(b => b.disabled = false);
  }
}

loadData();
</script>
</body>
</html>"""


# ── Phase B HTML 页面（可选阶段勾选） ──────────────────────────────

HTML_PHASE_B_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Phase B — 可选阶段选择</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f172a; color: #e2e8f0;
    min-height: 100vh; padding: 2rem;
  }
  .container { max-width: 900px; margin: 0 auto; }
  .header {
    text-align: center; padding: 2rem 0; border-bottom: 1px solid #334155;
    margin-bottom: 2rem;
  }
  .header h1 { font-size: 1.8rem; color: #22c55e; margin-bottom: 0.5rem; }
  .header .badge {
    display: inline-block; background: #14532d; color: #86efac;
    padding: 0.25rem 1rem; border-radius: 9999px; font-size: 0.85rem;
  }
  .stats {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 0.75rem; margin-bottom: 2rem;
  }
  .stat {
    background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem;
    padding: 1rem; text-align: center;
  }
  .stat .num { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .stat .lbl { font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem; }
  .cost-bar {
    background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem;
    padding: 0.75rem 1.25rem; margin-bottom: 2rem; text-align: center;
    font-size: 0.85rem; color: #94a3b8;
  }
  .cost-bar .cost-value { color: #38bdf8; font-weight: 600; }
  .section {
    background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem;
    padding: 1.5rem; margin-bottom: 1.5rem;
  }
  .section h3 {
    color: #94a3b8; font-size: 0.85rem; margin-bottom: 1rem;
    text-transform: uppercase; letter-spacing: 0.05em;
  }
  .checkbox-group { display: flex; flex-direction: column; gap: 0.75rem; }
  .checkbox-item {
    display: flex; align-items: center; gap: 0.75rem;
    padding: 0.5rem 0.75rem; border-radius: 0.5rem;
    cursor: pointer; transition: background 0.2s;
  }
  .checkbox-item:hover { background: #334155; }
  .checkbox-item input[type="checkbox"] {
    width: 1.25rem; height: 1.25rem; accent-color: #38bdf8;
    cursor: pointer;
  }
  .checkbox-item label { cursor: pointer; flex: 1; }
  .checkbox-item .est {
    color: #94a3b8; font-size: 0.8rem; white-space: nowrap;
  }
  .radio-group { display: flex; gap: 1.5rem; flex-wrap: wrap; }
  .radio-item {
    display: flex; align-items: center; gap: 0.5rem;
    padding: 0.5rem 1rem; border: 1px solid #334155; border-radius: 0.5rem;
    cursor: pointer; transition: all 0.2s;
  }
  .radio-item:hover { border-color: #38bdf8; }
  .radio-item input[type="radio"] {
    accent-color: #38bdf8; cursor: pointer;
  }
  .radio-item label { cursor: pointer; }
  .model-checkboxes { display: flex; gap: 1rem; flex-wrap: wrap; }
  .actions {
    display: flex; gap: 1rem; justify-content: center;
    padding: 2rem 0; border-top: 1px solid #334155;
  }
  .btn {
    padding: 0.75rem 2rem; border: none; border-radius: 0.5rem;
    font-size: 1rem; font-weight: 600; cursor: pointer; transition: all 0.2s;
  }
  .btn-primary { background: #22c55e; color: #052e16; }
  .btn-primary:hover { background: #16a34a; transform: translateY(-1px); }
  .btn-skip { background: #64748b; color: #fff; }
  .btn-skip:hover { background: #475569; transform: translateY(-1px); }
  .btn-stop { background: #ef4444; color: #fff; }
  .btn-stop:hover { background: #dc2626; transform: translateY(-1px); }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
  .status {
    text-align: center; padding: 1rem; color: #94a3b8; font-size: 0.9rem;
    display: none;
  }
  .status.show { display: block; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Phase A 完成 — 结果概览</h1>
    <span class="badge">Phase B: 选择可选阶段</span>
  </div>

  <div id="stats-area"></div>
  <div id="cost-area"></div>

  <div class="section">
    <h3>选择可选阶段</h3>
    <div class="checkbox-group">
      <div class="checkbox-item">
        <input type="checkbox" id="stage8" value="8">
        <label for="stage8">Stage 8: 角色状态追踪</label>
        <span class="est">预估 ~22min</span>
      </div>
      <div class="checkbox-item">
        <input type="checkbox" id="stage9" value="9">
        <label for="stage9">Stage 9: 对白提取</label>
        <span class="est">预估 ~1.5min</span>
      </div>
      <div class="checkbox-item">
        <input type="checkbox" id="stage10" value="10">
        <label for="stage10">Stage 10: 视觉评估</label>
        <span class="est">预估 ~3min</span>
      </div>
    </div>
  </div>

  <div class="section">
    <h3>目标模型</h3>
    <div class="radio-group">
      <div class="radio-item">
        <input type="radio" name="target_model" id="model_grok" value="grok" checked>
        <label for="model_grok">Grok (6s)</label>
      </div>
      <div class="radio-item">
        <input type="radio" name="target_model" id="model_jimeng" value="jimeng">
        <label for="model_jimeng">即梦 (12s)</label>
      </div>
    </div>
  </div>

  <div class="section">
    <h3>生成用模型（多选）</h3>
    <div class="model-checkboxes">
      <div class="checkbox-item">
        <input type="checkbox" id="gen_gpt" value="gpt-5.4" checked>
        <label for="gen_gpt">GPT-5.4</label>
      </div>
      <div class="checkbox-item">
        <input type="checkbox" id="gen_gemini" value="gemini">
        <label for="gen_gemini">Gemini</label>
      </div>
      <div class="checkbox-item">
        <input type="checkbox" id="gen_claude" value="claude-opus-4-6">
        <label for="gen_claude">Claude</label>
      </div>
      <div class="checkbox-item">
        <input type="checkbox" id="gen_grok" value="grok">
        <label for="gen_grok">Grok</label>
      </div>
    </div>
  </div>

  <div id="status" class="status"></div>

  <div class="actions">
    <button class="btn btn-primary" onclick="runSelected()">执行选中项</button>
    <button class="btn btn-skip" onclick="skipToReport()">跳过，直接生成报告</button>
    <button class="btn btn-stop" onclick="stopPipeline()">停止流水线</button>
  </div>
</div>

<script>
async function loadData() {
  try {
    const resp = await fetch('/api/stage-data');
    const data = await resp.json();
    renderPhaseB(data);
  } catch(e) {
    console.error('加载失败:', e);
  }
}

function renderPhaseB(data) {
  if (data.stats) {
    let html = '<div class="stats">';
    for (const [k, v] of Object.entries(data.stats)) {
      html += `<div class="stat"><div class="num">${v}</div><div class="lbl">${k}</div></div>`;
    }
    html += '</div>';
    document.getElementById('stats-area').innerHTML = html;
  }

  if (data.cost) {
    let html = '<div class="cost-bar">';
    html += 'Phase A 成本: <span class="cost-value">' + (data.cost.api_calls || '?') + '</span> 次调用';
    html += ' | <span class="cost-value">' + (data.cost.tokens || '?') + '</span> tokens';
    html += ' | <span class="cost-value">' + (data.cost.elapsed || '?') + '</span>s';
    html += '</div>';
    document.getElementById('cost-area').innerHTML = html;
  }
}

function getSelectedConfig() {
  const stages = [];
  document.querySelectorAll('.checkbox-group input[type="checkbox"]:checked').forEach(cb => {
    if (['8', '9', '10'].includes(cb.value)) stages.push(parseInt(cb.value));
  });

  const targetModel = document.querySelector('input[name="target_model"]:checked')?.value || 'grok';
  const targetDuration = targetModel === 'jimeng' ? '12s' : '6s';

  const testModels = [];
  document.querySelectorAll('.model-checkboxes input[type="checkbox"]:checked').forEach(cb => {
    testModels.push(cb.value);
  });

  return {
    selected_stages: stages,
    config: {
      target_duration: targetDuration,
      target_model: targetModel,
      test_models: testModels
    }
  };
}

async function sendAction(payload) {
  const btns = document.querySelectorAll('.btn');
  btns.forEach(b => b.disabled = true);
  const status = document.getElementById('status');
  status.textContent = '正在提交...';
  status.classList.add('show');

  try {
    await fetch('/api/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    status.textContent = '已提交，正在执行...';
  } catch(e) {
    status.textContent = '通信失败: ' + e.message;
    btns.forEach(b => b.disabled = false);
  }
}

function runSelected() {
  const cfg = getSelectedConfig();
  sendAction({ action: 'run_selected', ...cfg });
}

function skipToReport() {
  sendAction({ action: 'skip_to_report' });
}

function stopPipeline() {
  sendAction({ action: 'stop' });
}

loadData();
</script>
</body>
</html>"""


class ConfirmServer:
    """阶段确认 Web 服务。

    用法:
        server = ConfirmServer(port=5678)
        action = server.wait_for_confirm("Stage 3: 角色提取", 3, stage_data)
        # action: "continue" | "retry" | "stop"

        # Phase B 模式:
        result = server.wait_for_phase_b(stage_data)
        # result: {"action": "run_selected", "selected_stages": [8,9], "config": {...}}
    """

    def __init__(self, port: int = 5678, total_stages: int = 11):
        self.port = port
        self.total_stages = total_stages
        self._event = threading.Event()
        self._action = "stop"
        self._result_data = {}  # Phase B 的完整返回数据
        self._stage_name = ""
        self._stage_number = 0
        self._stage_data = {}
        self._phase_b_mode = False
        self._httpd = None
        self._thread = None

    def wait_for_confirm(self, stage_name: str, stage_number: int,
                         stage_data: dict) -> str:
        """启动 Web 服务，等待用户确认后返回操作。"""
        self._phase_b_mode = False
        self._event.clear()
        self._action = "stop"
        self._stage_name = stage_name
        self._stage_number = stage_number
        self._stage_data = stage_data

        return self._run_server()

    def wait_for_phase_b(self, stage_data: dict) -> dict:
        """Phase B: 展示勾选框页面，返回选择结果。

        Returns:
            {
                "action": "run_selected" | "skip_to_report" | "stop",
                "selected_stages": [8, 9, 10],
                "config": {
                    "target_duration": "6s",
                    "target_model": "grok",
                    "test_models": ["gpt-5.4", "gemini"]
                }
            }
        """
        self._phase_b_mode = True
        self._event.clear()
        self._action = "stop"
        self._result_data = {}
        self._stage_data = stage_data

        self._run_server()
        return self._result_data

    def _run_server(self) -> str:
        """内部：启动 HTTP 服务并等待用户操作。"""
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # suppress default logging

            def do_GET(self):
                if self.path == "/":
                    if server_ref._phase_b_mode:
                        html = HTML_PHASE_B_TEMPLATE
                    else:
                        html = HTML_TEMPLATE.format(
                            stage_name=server_ref._stage_name,
                            stage_number=server_ref._stage_number,
                            total_stages=server_ref.total_stages,
                        )
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                elif self.path == "/api/stage-data":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(
                        server_ref._stage_data, ensure_ascii=False
                    ).encode("utf-8"))
                else:
                    self.send_error(404)

            def do_POST(self):
                if self.path == "/api/confirm":
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length)) if length else {}

                    server_ref._action = body.get("action", "stop")
                    # Phase B: 保存完整返回数据
                    server_ref._result_data = body

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                    server_ref._event.set()
                else:
                    self.send_error(404)

        self._httpd = HTTPServer(("127.0.0.1", self.port), Handler)

        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

        url = f"http://localhost:{self.port}"
        mode_label = "Phase B 选择" if self._phase_b_mode else "确认"
        print(f"  [WEB] {mode_label}页面已启动: {url}")
        try:
            webbrowser.open(url)
        except Exception:
            pass

        self._event.wait()

        self._httpd.shutdown()
        self._httpd = None
        self._thread = None

        return self._action

    def shutdown(self):
        """手动关闭服务。"""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
