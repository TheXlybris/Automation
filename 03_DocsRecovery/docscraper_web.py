#!/usr/bin/env python3
"""docscraper_web — GUI web para a ferramenta docscraper.

Servidor Flask que serve um GUI HTML. Abre no browser.
Funciona em qualquer ambiente (headless incluído).

Uso:
  python3 docscraper_web.py
  # Abre em http://localhost:8501
"""

import os
import sys
import json
import threading
import subprocess
import time
import queue
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ── Config ──────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8501
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def find_venv_python():
    """Procura o python do venv em vários locais."""
    candidates = [
        os.path.join(SCRIPT_DIR, ".venv", "bin", "python"),
        os.path.join(os.path.expanduser("~"), "docscraper-venv", "bin", "python"),
        os.path.join(os.path.expanduser("~"), ".hermes", "scripts", "docscraper", ".venv", "bin", "python"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return sys.executable


# ── Estado global ────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.is_running = False
        self.process = None
        self.logs = []
        self.logs_lock = threading.Lock()
        self.result = None

    def add_log(self, msg, tag="dim"):
        with self.logs_lock:
            self.logs.append({"msg": msg, "tag": tag, "ts": time.time()})
            # Manter só últimos 500 logs
            if len(self.logs) > 500:
                self.logs = self.logs[-500:]

    def get_logs_since(self, since_ts=0):
        with self.logs_lock:
            return [l for l in self.logs if l["ts"] > since_ts]

    def clear_logs(self):
        with self.logs_lock:
            self.logs = []

    def reset(self):
        self.clear_logs()
        self.result = None


state = AppState()


def run_extraction(url, out_dir, layer=None, max_depth=3, keep_html=False, verbose=True):
    """Corre docscraper.py como subprocesso."""
    venv_python = find_venv_python()
    script_path = os.path.join(SCRIPT_DIR, "docscraper.py")

    cmd = [venv_python, script_path, url, "-o", out_dir]
    if verbose:
        cmd.append("-v")
    if layer and layer != "auto":
        cmd.extend(["--layer", layer])
    cmd.extend(["--max-depth", str(max_depth)])
    if keep_html:
        cmd.append("--keep-html")

    state.add_log(f"Comando: {' '.join(cmd)}", "dim")
    state.add_log("", "dim")

    try:
        state.process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, universal_newlines=True,
            cwd=SCRIPT_DIR,
        )

        for line in state.process.stdout:
            line = line.rstrip()
            if not line:
                continue
            tag = "dim"
            if "✓" in line or "SUCCESS" in line:
                tag = "success"
            elif "✗" in line or "ERROR" in line or "Failed" in line:
                tag = "error"
            elif "WARNING" in line or "SPA" in line:
                tag = "warning"
            elif line.startswith("[") or "Camada" in line:
                tag = "info"
            state.add_log(line, tag)

        state.process.wait()
        rc = state.process.returncode

        if rc == 0:
            state.add_log("", "dim")
            state.add_log("✓ Extração concluída com sucesso!", "success")
            state.result = {"success": True, "output_dir": out_dir}
        else:
            state.add_log("", "dim")
            state.add_log(f"✗ Processo terminou com código {rc}", "error")
            state.result = {"success": False, "error": f"exit code {rc}"}

    except Exception as e:
        state.add_log(f"✗ Erro: {e}", "error")
        state.result = {"success": False, "error": str(e)}
    finally:
        state.is_running = False
        state.process = None


# ── HTML ────────────────────────────────────────────────────
HTML_PAGE = """<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>docscraper</title>
<style>
:root {
  --bg: #1e1e2e;
  --bg-panel: #181825;
  --bg-entry: #313244;
  --fg: #cdd6f4;
  --fg-dim: #a6adc8;
  --accent: #89b4fa;
  --accent-hover: #74c7ec;
  --success: #a6e3a1;
  --error: #f38ba8;
  --warning: #f9e2af;
  --border: #45475a;
  --radius: 8px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--bg); color: var(--fg);
  font-family: 'Segoe UI', system-ui, sans-serif;
  min-height: 100vh; padding: 16px;
}
.container { max-width: 820px; margin: 0 auto; }
.header {
  background: var(--bg-panel); border-radius: var(--radius);
  padding: 20px 24px; margin-bottom: 12px;
  display: flex; align-items: center; gap: 12px;
}
.header h1 { font-size: 22px; color: var(--accent); }
.header .version { color: var(--fg-dim); font-size: 12px; }
.header .desc {
  color: var(--fg-dim); font-size: 12px; margin-left: auto;
  max-width: 380px; text-align: right; line-height: 1.5;
}
.panel {
  background: var(--bg-panel); border-radius: var(--radius);
  padding: 20px 24px; margin-bottom: 12px;
}
.panel label {
  display: block; font-size: 13px; font-weight: 600;
  margin-bottom: 6px; color: var(--fg);
}
.input-row { display: flex; gap: 8px; margin-bottom: 16px; }
input[type="text"], select {
  flex: 1; background: var(--bg-entry); color: var(--fg);
  border: 1px solid var(--border); border-radius: 6px;
  padding: 10px 12px; font-size: 14px; outline: none;
  transition: border-color 0.2s;
}
input[type="text"]:focus, select:focus { border-color: var(--accent); }
.btn {
  background: var(--bg-entry); color: var(--fg);
  border: 1px solid var(--border); border-radius: 6px;
  padding: 10px 16px; font-size: 14px; cursor: pointer;
  transition: all 0.2s; white-space: nowrap;
}
.btn:hover { background: var(--accent-hover); color: var(--bg); }
.btn-primary {
  background: var(--accent); color: var(--bg);
  border-color: var(--accent); font-weight: 600;
}
.btn-primary:hover { background: var(--accent-hover); }
.btn-danger {
  background: var(--error); color: var(--bg);
  border-color: var(--error); font-weight: 600;
}
.btn-danger:hover { opacity: 0.85; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.options-row {
  display: flex; align-items: center; gap: 20px;
  flex-wrap: wrap; margin-bottom: 16px;
}
.checkbox-row {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--fg-dim); cursor: pointer;
}
.checkbox-row input { width: 16px; height: 16px; accent-color: var(--accent); }
.depth-row {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--fg-dim);
}
.depth-row input {
  width: 50px; text-align: center; background: var(--bg-entry);
  color: var(--fg); border: 1px solid var(--border);
  border-radius: 4px; padding: 4px 8px; font-size: 13px;
}
.actions {
  display: flex; gap: 8px; margin-bottom: 16px;
}
.actions .spacer { flex: 1; }
.log-panel {
  background: var(--bg); border-radius: 6px;
  border: 1px solid var(--border); padding: 12px;
  height: 320px; overflow-y: auto; font-family: 'Consolas', monospace;
  font-size: 12px; line-height: 1.6;
}
.log-line { white-space: pre-wrap; word-break: break-word; }
.log-success { color: var(--success); }
.log-error { color: var(--error); }
.log-warning { color: var(--warning); }
.log-info { color: var(--accent); }
.log-dim { color: var(--fg-dim); }
.status-bar {
  display: flex; align-items: center; gap: 12px;
  margin-top: 8px; font-size: 12px; color: var(--fg-dim);
}
.spinner {
  width: 14px; height: 14px; border: 2px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.8s linear infinite; display: none;
}
.spinner.active { display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
.hint { font-size: 11px; color: var(--fg-dim); margin-top: 4px; }
.layer-desc { font-size: 11px; color: var(--fg-dim); margin-top: 4px; margin-bottom: 12px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>docscraper</h1>
    <span class="version">v1.0.0</span>
    <div class="desc">
      Extrai TODA a documentação de qualquer site.<br>
      5 camadas em cascata: llms.txt → sitemap → link discovery → GitHub → wget → Playwright.<br>
      Local, gratuito, sem limites de API.
    </div>
  </div>

  <div class="panel">
    <label for="url">URL do site de documentação</label>
    <div class="input-row">
      <input type="text" id="url" placeholder="https://exemplo.com/docs/" autofocus>
    </div>
    <div class="hint">Ex: https://hermes-agent.nousresearch.com/docs/</div>

    <label for="outdir">Pasta de output</label>
    <div class="input-row">
      <input type="text" id="outdir" placeholder="/home/user/output">
      <button class="btn" onclick="browseDir()">Procurar…</button>
    </div>
    <div class="hint">Default: ~/docscraper_output</div>
  </div>

  <div class="panel">
    <label for="layer">Camada de extração</label>
    <select id="layer">
      <option value="auto">Automático (recomendado)</option>
      <option value="llms_txt">0 — llms.txt / llms-full</option>
      <option value="sitemap">0 — sitemap.xml</option>
      <option value="link_discovery">1 — Link discovery</option>
      <option value="github">2 — GitHub source</option>
      <option value="wget">3 — wget mirror</option>
      <option value="playwright">4 — Playwright (SPAs)</option>
    </select>
    <div class="layer-desc">Automático tenta cada camada por ordem até uma funcionar.</div>

    <div class="options-row">
      <label class="checkbox-row">
        <input type="checkbox" id="verbose" checked> Verbose (log detalhado)
      </label>
      <label class="checkbox-row">
        <input type="checkbox" id="keephtml"> Manter HTML original
      </label>
      <div class="depth-row">
        <label>Profundidade:</label>
        <input type="number" id="depth" value="3" min="1" max="10">
      </div>
    </div>

    <div class="actions">
      <button class="btn btn-primary" id="runBtn" onclick="startExtraction()">▶ Extrair</button>
      <button class="btn btn-danger" id="stopBtn" onclick="stopExtraction()" disabled>■ Parar</button>
      <div class="spacer"></div>
      <button class="btn" onclick="clearLog()">Limpar log</button>
    </div>

    <label>Log de execução</label>
    <div class="log-panel" id="log"></div>

    <div class="status-bar">
      <span class="spinner" id="spinner"></span>
      <span id="status">Pronto.</span>
    </div>
  </div>
</div>

<script>
let pollTimer = null;
let lastTs = 0;

function setRunning(running) {
  document.getElementById('runBtn').disabled = running;
  document.getElementById('stopBtn').disabled = !running;
  document.getElementById('spinner').classList.toggle('active', running);
  document.getElementById('status').textContent = running ? 'A extrair…' : 'Pronto.';
}

function addLogLine(msg, tag) {
  const log = document.getElementById('log');
  const div = document.createElement('div');
  div.className = 'log-line log-' + tag;
  div.textContent = msg;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function startExtraction() {
  const url = document.getElementById('url').value.trim();
  const outdir = document.getElementById('outdir').value.trim();
  const layer = document.getElementById('layer').value;
  const verbose = document.getElementById('verbose').checked;
  const keephtml = document.getElementById('keephtml').checked;
  const depth = document.getElementById('depth').value;

  if (!url) { alert('Indica o URL do site de documentação.'); return; }
  if (!outdir) { alert('Indica a pasta de output.'); return; }

  // Limpar log
  document.getElementById('log').innerHTML = '';
  lastTs = 0;

  addLogLine('Iniciando extração de: ' + url, 'info');
  addLogLine('Output: ' + outdir, 'dim');
  addLogLine('Data: ' + new Date().toISOString(), 'dim');
  addLogLine('', 'dim');

  setRunning(true);

  fetch('/api/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      url, outdir, layer, verbose, keep_html: keephtml, max_depth: parseInt(depth)
    })
  }).then(r => r.json()).then(data => {
    if (data.error) {
      addLogLine('✗ ' + data.error, 'error');
      setRunning(false);
    } else {
      // Iniciar polling
      pollLogs();
    }
  }).catch(e => {
    addLogLine('✗ Erro: ' + e, 'error');
    setRunning(false);
  });
}

function pollLogs() {
  fetch('/api/logs?since=' + lastTs)
    .then(r => r.json())
    .then(data => {
      if (data.logs && data.logs.length > 0) {
        data.logs.forEach(l => {
          addLogLine(l.msg, l.tag);
          lastTs = l.ts;
        });
      }
      if (data.running) {
        pollTimer = setTimeout(pollLogs, 200);
      } else {
        setRunning(false);
        if (data.result) {
          if (data.result.success) {
            addLogLine('', 'dim');
            addLogLine('✓ Extração concluída! Output: ' + data.result.output_dir, 'success');
          } else {
            addLogLine('', 'dim');
            addLogLine('✗ Falhou: ' + (data.result.error || 'unknown'), 'error');
          }
        }
        document.getElementById('status').textContent = 'Concluído.';
      }
    })
    .catch(e => {
      pollTimer = setTimeout(pollLogs, 500);
    });
}

function stopExtraction() {
  fetch('/api/stop', {method: 'POST'})
    .then(r => r.json())
    .then(data => {
      addLogLine('A parar…', 'warning');
      setRunning(false);
    });
}

function clearLog() {
  document.getElementById('log').innerHTML = '';
  fetch('/api/clear', {method: 'POST'});
}

function browseDir() {
  // Prompt simples para browser — não há file dialog nativo em web
  const dir = prompt('Indica o caminho da pasta de output:', '/home/' + 'xlybris' + '/docscraper_output');
  if (dir) document.getElementById('outdir').value = dir;
}

// Init
document.getElementById('outdir').value = '/home/xlybris/docscraper_output';
</script>
</body>
</html>"""


# ── HTTP Server ─────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silenciar logs do HTTP

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_html(self, html, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            self._send_html(HTML_PAGE)

        elif parsed.path == "/api/logs":
            since = 0
            try:
                since = float(parsed.query.split("since=")[1])
            except Exception:
                pass
            logs = state.get_logs_since(since)
            self._send_json({
                "logs": logs,
                "running": state.is_running,
                "result": state.result,
            })

        elif parsed.path == "/api/status":
            self._send_json({
                "running": state.is_running,
                "result": state.result,
                "log_count": len(state.logs),
            })

        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/start":
            if state.is_running:
                self._send_json({"error": "Já está a correr"}, 400)
                return

            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                url = body.get("url", "").strip()
                outdir = body.get("outdir", "").strip()
                layer = body.get("layer", "auto")
                verbose = body.get("verbose", True)
                keep_html = body.get("keep_html", False)
                max_depth = body.get("max_depth", 3)

                if not url or not outdir:
                    self._send_json({"error": "URL e output são obrigatórios"}, 400)
                    return

                os.makedirs(outdir, exist_ok=True)
                state.reset()
                state.is_running = True

                t = threading.Thread(
                    target=run_extraction,
                    args=(url, outdir, layer, max_depth, keep_html, verbose),
                    daemon=True
                )
                t.start()

                self._send_json({"ok": True})

            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif parsed.path == "/api/stop":
            if state.process:
                state.process.terminate()
                state.add_log("A parar…", "warning")
            state.is_running = False
            self._send_json({"ok": True})

        elif parsed.path == "/api/clear":
            state.clear_logs()
            self._send_json({"ok": True})

        else:
            self._send_json({"error": "not found"}, 404)


def main():
    server = HTTPServer((HOST, PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"docscraper GUI rodando em: {url}")
    print(f"Abre o browser em: {url}")
    print(f"Para parar: Ctrl+C")

    # Tentar abrir browser automaticamente
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nA parar…")
        server.shutdown()


if __name__ == "__main__":
    main()