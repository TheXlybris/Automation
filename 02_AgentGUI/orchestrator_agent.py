#!/usr/bin/env python3
"""
Orchestrator Agent v2.3 — Mini-Agente Completo para AgentGUI.

Loop de agente: recebe mensagem -> chama LLM -> se decidir usar tool, executa ->
observa resultado -> repete até ter resposta final.

Comunicação: Socket.IO client com server.py (bidirecional).
Modelo: kimi-k2.6 via Ollama Cloud API.
Modos: Brainstorm (leitura apenas) / Orquestrador (tools completas).
"""

import json
import time
import os
import re
import subprocess
import textwrap
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import socketio
import requests

# ─── Config ───────────────────────────────────────────
DATA_DIR = Path("/media/sf_AI_Ecosystem/10_Projects/02_AgentGUI/data")
WIKI_DIR = Path("/media/sf_AI_Ecosystem/12_LLM_Wiki/AgentGUI/Wiki")
STATE_FILE = DATA_DIR / "orchestrator_state.json"
INBOX_FILE = DATA_DIR / "orchestrator_inbox.json"
HISTORY_FILE = DATA_DIR / "orchestrator_history.json"
SUMMARY_FILE = DATA_DIR / "orchestrator_summary.json"
MODE_FILE = DATA_DIR / "orchestrator_mode.json"
SERVER_URL = "http://192.168.0.188:5020"

# API config — loaded dynamically from profile config
# Local Ollama:  http://192.168.0.187:11434/v1
# Ollama Cloud:   https://ollama.com/v1
ORCH_CONFIG_FILE = Path.home() / ".hermes" / "profiles" / "orchestrator" / "agentgui_config.json"

CLOUD_MODELS = {"kimi-k2.6", "glm-5.2", "deepseek-v4-pro", "qwen3-coder:480b"}
LOCAL_OLLAMA_URL = "http://192.168.0.187:11434/v1"
CLOUD_OLLAMA_URL = "https://ollama.com/v1"

def _load_api_config():
    """Read model + base_url from profile config file, fall back to defaults."""
    model = "kimi-k2.6"
    base_url = CLOUD_OLLAMA_URL
    api_key = os.environ.get("OLLAMA_API_KEY", "")

    if ORCH_CONFIG_FILE.exists():
        try:
            cfg = json.loads(ORCH_CONFIG_FILE.read_text())
            cfg_model = cfg.get("model")
            if cfg_model:
                model = cfg_model
                # Auto-detect: cloud vs local based on model name
                if cfg_model not in CLOUD_MODELS and not cfg_model.endswith(":cloud"):
                    base_url = LOCAL_OLLAMA_URL
                    # Local Ollama doesn't need API key, but send empty string
                    api_key = api_key or "ollama"
                else:
                    base_url = CLOUD_OLLAMA_URL
        except Exception as e:
            print(f"[WARN] Could not read orchestrator config: {e}")

    return model, base_url, api_key

# Initial load
MODEL, BASE_URL, API_KEY = _load_api_config()

MAX_HISTORY = 30      # janela deslizante
SUMMARY_THRESHOLD = 20  # quando atinge 20 msgs, resumir primeiras 10
MAX_TURNS = 8         # máximo de iterações de tool-calling por mensagem

# ─── Tools definition ────────────────────────────────

BRAINSTORM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lê o conteúdo de um ficheiro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho absoluto do ficheiro"},
                    "limit": {"type": "integer", "description": "Número máximo de linhas (opcional, default 200)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Lista ficheiros num diretório.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho do diretório"},
                    "pattern": {"type": "string", "description": "Pattern glob opcional, ex: '*.md'"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_wiki",
            "description": "Lê uma página da wiki Obsidian do projeto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "string", "description": "Nome da página, ex: 'index' ou 'log'"}
                },
                "required": ["page"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_wiki",
            "description": "Procura texto na wiki Obsidian.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texto a procurar"}
                },
                "required": ["query"]
            }
        }
    }
]

ORCHESTRATOR_TOOLS = BRAINSTORM_TOOLS + [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Cria ou sobrescreve um ficheiro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho absoluto do ficheiro"},
                    "content": {"type": "string", "description": "Conteúdo completo do ficheiro"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminal",
            "description": "Executa um comando no terminal Linux.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando a executar"},
                    "timeout": {"type": "integer", "description": "Timeout em segundos (default 30)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Pesquisa na web via Tavily API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query de pesquisa"},
                    "limit": {"type": "integer", "description": "Número de resultados (default 5)"}
                },
                "required": ["query"]
            }
        }
    }
]

# ─── Tool Implementations ────────────────────────────

def tool_read_file(path: str, limit: int = 200) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"[ERRO] Ficheiro não encontrado: {path}"
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        if limit and len(lines) > limit:
            return "\n".join(lines[:limit]) + f"\n... ({len(lines) - limit} linhas omitidas)"
        return "\n".join(lines)
    except Exception as e:
        return f"[ERRO] {e}"

def tool_list_files(path: str, pattern: str = None) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"[ERRO] Diretório não encontrado: {path}"
        if pattern:
            files = sorted(p.glob(pattern))
        else:
            files = sorted(p.iterdir())
        out = []
        for f in files:
            marker = "D" if f.is_dir() else "F"
            size = f.stat().st_size if f.is_file() else "-"
            out.append(f"{marker} {f.name} ({size} bytes)")
        return "\n".join(out) if out else "(diretório vazio)"
    except Exception as e:
        return f"[ERRO] {e}"

def tool_read_wiki(page: str) -> str:
    """Lê uma página wiki Obsidian."""
    page = page.replace(".md", "")
    p = WIKI_DIR / f"{page}.md"
    if not p.exists():
        # Tenta procurar com hífens
        for f in WIKI_DIR.glob("*.md"):
            if f.stem.lower() == page.lower():
                p = f
                break
    if not p.exists():
        return f"[ERRO] Página wiki não encontrada: {page}.md"
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        return f"[ERRO] {e}"

def tool_search_wiki(query: str) -> str:
    """Procura texto na wiki."""
    results = []
    try:
        for f in WIKI_DIR.rglob("*.md"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                if query.lower() in text.lower():
                    # Mostrar contexto
                    idx = text.lower().find(query.lower())
                    start = max(0, idx - 100)
                    end = min(len(text), idx + 200)
                    snippet = text[start:end].replace("\n", " ")
                    results.append(f"📄 {f.name}: ...{snippet}...")
            except Exception:
                pass
        if not results:
            return f"Nenhum resultado para '{query}' na wiki."
        return "\n\n".join(results[:10])
    except Exception as e:
        return f"[ERRO] {e}"

def tool_write_file(path: str, content: str) -> str:
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"[OK] Ficheiro escrito: {path} ({len(content)} chars)"
    except Exception as e:
        return f"[ERRO] {e}"

def tool_terminal(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        stdout = result.stdout[:4000]  # limitar output
        stderr = result.stderr[:2000]
        out = f"EXIT CODE: {result.returncode}\n"
        if stdout:
            out += f"STDOUT:\n{stdout}\n"
        if stderr:
            out += f"STDERR:\n{stderr}\n"
        return out
    except subprocess.TimeoutExpired:
        return f"[ERRO] Timeout após {timeout}s"
    except Exception as e:
        return f"[ERRO] {e}"

def tool_web_search(query: str, limit: int = 5) -> str:
    """Pesquisa web via Tavily API."""
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if not tavily_key:
        return "[ERRO] TAVILY_API_KEY não configurada."
    try:
        url = "https://api.tavily.com/search"
        resp = requests.post(url, json={
            "api_key": tavily_key,
            "query": query,
            "search_depth": "basic",
            "max_results": limit,
        }, timeout=15)
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return f"Sem resultados para: {query}"
        out = []
        for r in results[:limit]:
            out.append(f"• {r.get('title', 'Sem título')}\n  {r.get('url', '')}\n  {r.get('content', '')[:300]}...")
        return "\n\n".join(out)
    except Exception as e:
        return f"[ERRO] Pesquisa falhou: {e}"

TOOL_MAP = {
    "read_file": tool_read_file,
    "list_files": tool_list_files,
    "read_wiki": tool_read_wiki,
    "search_wiki": tool_search_wiki,
    "write_file": tool_write_file,
    "terminal": tool_terminal,
    "web_search": tool_web_search,
}

# ─── State Management ──────────────────────────────

def load_history() -> List[Dict]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

def save_history(history: List[Dict]):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def load_summary() -> str:
    if SUMMARY_FILE.exists():
        try:
            return SUMMARY_FILE.read_text(encoding="utf-8")
        except Exception:
            pass
    return ""

def save_summary(summary: str):
    SUMMARY_FILE.write_text(summary, encoding="utf-8")

def load_mode() -> str:
    if MODE_FILE.exists():
        try:
            data = json.loads(MODE_FILE.read_text())
            return data.get("mode", "brainstorm")
        except Exception:
            pass
    return "brainstorm"

def save_mode(mode: str):
    MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODE_FILE.write_text(json.dumps({"mode": mode}), encoding="utf-8")

SYSTEM_PROMPT_BASE = textwrap.dedent("""\
    És o Orquestrador Hermes, um agente de IA que opera dentro do AgentGUI.

    As tuas capacidades:
    - Ler ficheiros e directorias
    - Consultar a wiki Obsidian do projecto
    - Pesquisar na web (modo Orquestrador)
    - Criar/modificar ficheiros (modo Orquestrador)
    - Executar comandos no terminal (modo Orquestrador)

    Regras:
    1. Responde sempre em português (PT-PT)
    2. Seja directo e técnico
    3. Quando usar tools, pensa passo a passo
    4. Se não souberes algo, admite-o
    5. O utilizador pode alternar entre modos Brainstorm e Orquestrador

    O projecto actual é o AgentGUI, um dashboard para orquestração de agentes LLM.
    A wiki está em /media/sf_AI_Ecosystem/12_LLM_Wiki/AgentGUI/Wiki/
    """)

def build_messages(history: List[Dict], summary: str, mode: str) -> List[Dict]:
    """Constrói a lista de mensagens para o LLM a partir do histórico."""
    sys_content = SYSTEM_PROMPT_BASE
    sys_content += f"\n\n## Modo Actual: {mode.upper()}"
    if mode == "brainstorm":
        sys_content += "\nPodes consultar ficheiros e wiki, mas NÃO podes criar/modificar ficheiros nem executar comandos."
    else:
        sys_content += "\nTens acesso completo a todas as tools. Podes criar ficheiros, executar comandos, e pesquisar na web."

    if summary:
        sys_content += f"\n\n## Resumo da Conversa Anterior\n{summary}"

    messages = [{"role": "system", "content": sys_content}]

    # Adicionar últimas mensagens do histórico (sliding window)
    for msg in history[-MAX_HISTORY:]:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("text", "")
        })

    return messages

# ─── LLM API Call ────────────────────────────────────

def call_llm(messages: List[Dict], tools: List[Dict], max_tokens: int = 4096) -> Dict:
    """Chama a API Ollama Cloud com tool calling."""
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"error": "Timeout na API Ollama (120s). O servidor pode estar sobrecarregado."}
    except Exception as e:
        return {"error": f"Erro na API: {e}"}

# ─── Agent Loop ──────────────────────────────────────

def process_user_message(text: str, mode: str) -> str:
    """Processa uma mensagem do utilizador e retorna a resposta final."""

    # Reload API config (in case user changed model via SettingsModal)
    global MODEL, BASE_URL, API_KEY
    MODEL, BASE_URL, API_KEY = _load_api_config()
    print(f"[CONFIG] Model={MODEL} | Base={BASE_URL} | Key={'set' if API_KEY else 'none'}")

    # Carregar estado
    history = load_history()
    summary = load_summary()
    tools = ORCHESTRATOR_TOOLS if mode == "orchestrator" else BRAINSTORM_TOOLS

    # Adicionar mensagem do utilizador ao histórico
    history.append({"role": "user", "text": text, "time": datetime.now().isoformat()})

    # Verificar se precisa de resumo automático
    if len(history) >= SUMMARY_THRESHOLD:
        # Resumir primeiras 10 mensagens
        to_summarize = history[:10]
        summary_text = summarize_history(to_summarize)
        existing = load_summary()
        new_summary = f"{existing}\n\n--- Novo Resumo ---\n{summary_text}".strip()
        save_summary(new_summary)
        # Remover do histórico activo
        history = history[10:]
        print(f"[INFO] Resumo automático gerado ({len(to_summarize)} mensagens)")

    save_history(history)

    # Construir mensagens para LLM
    messages = build_messages(history, load_summary(), mode)

    # Agent loop: até não haver tool calls ou atingir MAX_TURNS
    for turn in range(MAX_TURNS):
        print(f"[TURN {turn + 1}/{MAX_TURNS}] Chamando LLM...")
        response = call_llm(messages, tools)

        if "error" in response:
            error_msg = f"[Erro do sistema] {response['error']}"
            history.append({"role": "assistant", "text": error_msg, "time": datetime.now().isoformat()})
            save_history(history)
            return error_msg

        choice = response.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            # Resposta final — sem tool calls
            history.append({"role": "assistant", "text": content, "time": datetime.now().isoformat()})
            save_history(history)
            return content

        # Processar tool calls
        messages.append(msg)

        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            tool_args_raw = func.get("arguments", "{}")
            try:
                tool_args = json.loads(tool_args_raw)
            except json.JSONDecodeError:
                tool_args = {}
            tool_id = tc.get("id", "")

            print(f"[TOOL] {tool_name}({tool_args})")

            # Executar tool
            if tool_name in TOOL_MAP:
                result = TOOL_MAP[tool_name](**tool_args)
            else:
                result = f"[ERRO] Tool '{tool_name}' não existe."

            print(f"[TOOL RESULT] {result[:200]}...")

            # Adicionar resultado ao contexto
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": result
            })

            # Também guardar no histórico como system
            history.append({
                "role": "system",
                "text": f"[Tool: {tool_name}] {result[:500]}",
                "time": datetime.now().isoformat()
            })

    # Max turns atingido
    final_msg = "[Atingido limite de iterações. A resposta pode estar incompleta.]"
    history.append({"role": "assistant", "text": final_msg, "time": datetime.now().isoformat()})
    save_history(history)
    return final_msg

def summarize_history(messages: List[Dict]) -> str:
    """Gera um resumo das primeiras N mensagens usando o LLM."""
    summary_prompt = "Resume brevemente esta conversa, mantendo os pontos-chave e decisões:\n\n"
    for m in messages:
        r = m.get("role", "user")
        t = m.get("text", "")[:200]
        summary_prompt += f"{r}: {t}\n"

    url = f"{BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Resume a conversa seguinte em 2-3 frases, em português. Mantém tópicos, decisões e contexto importante."},
            {"role": "user", "content": summary_prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.3
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "[Resumo indisponível]")
    except Exception as e:
        return f"[Erro no resumo: {e}]"

# ─── Socket.IO Client ──────────────────────────────

def run_agent():
    """Loop principal do agente."""
    print("=" * 60)
    print("  ORCHESTRATOR AGENT v2.3")
    print(f"  Modo: {load_mode()}")
    print(f"  Server: {SERVER_URL}")
    print(f"  Model: {MODEL}")
    print(f"  API Key: {'configured' if API_KEY else 'MISSING'}")
    print("=" * 60)

    sio = socketio.Client()

    @sio.event
    def connect():
        print("[Socket.IO] Conectado ao server.py")
        # Notificar que o orquestrador está online
        sio.emit("orchestrator_ready", {"status": "online", "mode": load_mode()})

    @sio.event
    def disconnect():
        print("[Socket.IO] Desconectado do server.py")

    @sio.on("orchestrator_message")
    def on_orchestrator_message(data):
        """Recebe mensagem do dashboard via Socket.IO."""
        text = data.get("text", "")
        if not text:
            return
        print(f"[MSG] User: {text[:80]}...")

        mode = load_mode()

        # Notificar que está a processar
        sio.emit("orchestrator_typing", {})

        try:
            response = process_user_message(text, mode)
        except Exception as e:
            response = f"[Erro interno do agente] {e}"
            print(f"[ERROR] {e}")

        # Enviar resposta
        sio.emit("orchestrator_response", {"text": response, "mode": mode})
        print(f"[RESP] {response[:100]}...")

    @sio.on("orchestrator_mode_change")
    def on_mode_change(data):
        new_mode = data.get("mode", "brainstorm")
        save_mode(new_mode)
        print(f"[MODE] Alterado para: {new_mode}")
        sio.emit("orchestrator_response", {
            "text": f"Modo alterado para **{new_mode.upper()}**.",
            "mode": new_mode
        })

    @sio.on("orchestrator_summarize")
    def on_summarize(data):
        history = load_history()
        if len(history) < 3:
            sio.emit("orchestrator_response", {
                "text": "Histórico muito curto para resumir. Envia mais mensagens primeiro."
            })
            return
        summary = summarize_history(history)
        save_summary(summary)
        sio.emit("orchestrator_response", {
            "text": f"**Resumo gerado:**\n\n{summary}"
        })

    # Conectar
    try:
        sio.connect(SERVER_URL, wait_timeout=10)
    except Exception as e:
        print(f"[ERRO] Não foi possível conectar ao server: {e}")
        print("[INFO] A tentar modo fallback (polling de inbox.json)...")
        run_fallback()
        return

    # Loop principal (poll do inbox como fallback)
    last_inbox_len = 0
    try:
        while True:
            time.sleep(2)

            # Fallback: também verificar inbox.json (se server não reencaminhar via Socket.IO)
            if INBOX_FILE.exists():
                try:
                    inbox = json.loads(INBOX_FILE.read_text())
                    if len(inbox) > last_inbox_len:
                        # Novas mensagens
                        for msg in inbox[last_inbox_len:]:
                            text = msg.get("text", "")
                            if text:
                                print(f"[INBOX] User: {text[:80]}...")
                                mode = load_mode()
                                sio.emit("orchestrator_typing", {})
                                try:
                                    response = process_user_message(text, mode)
                                except Exception as e:
                                    response = f"[Erro] {e}"
                                sio.emit("orchestrator_response", {"text": response, "mode": mode})
                                print(f"[INBOX RESP] {response[:100]}...")
                        last_inbox_len = len(inbox)
                except Exception as e:
                    print(f"[WARN] Erro a ler inbox: {e}")
    except KeyboardInterrupt:
        print("\n[Agent] A terminar...")
    finally:
        sio.disconnect()

def run_fallback():
    """Modo fallback: só polling de inbox.json sem Socket.IO."""
    print("[FALLBACK] Modo polling de inbox.json")
    last_inbox_len = 0
    while True:
        time.sleep(3)
        if not INBOX_FILE.exists():
            continue
        try:
            inbox = json.loads(INBOX_FILE.read_text())
            if len(inbox) > last_inbox_len:
                for msg in inbox[last_inbox_len:]:
                    text = msg.get("text", "")
                    if text:
                        print(f"[FALLBACK MSG] User: {text[:80]}...")
                        mode = load_mode()
                        try:
                            response = process_user_message(text, mode)
                        except Exception as e:
                            response = f"[Erro] {e}"
                        print(f"[FALLBACK RESP] {response[:200]}...")
                        # Escrever resposta num outbox
                        outbox = DATA_DIR / "orchestrator_outbox.json"
                        entries = []
                        if outbox.exists():
                            try:
                                entries = json.loads(outbox.read_text())
                            except:
                                pass
                        entries.append({
                            "role": "assistant",
                            "text": response,
                            "time": datetime.now().isoformat()
                        })
                        outbox.write_text(json.dumps(entries, indent=2), encoding="utf-8")
                last_inbox_len = len(inbox)
        except Exception as e:
            print(f"[WARN] {e}")

if __name__ == "__main__":
    run_agent()