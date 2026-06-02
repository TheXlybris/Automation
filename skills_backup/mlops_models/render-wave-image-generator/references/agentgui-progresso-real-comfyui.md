# AgentGUI — Dashboard de Agentes Hermes com Progresso Real do ComfyUI

**Contexto:** THE RENDER WAVE project — dashboard Flask para lançar e monitorizar agentes Hermes (Researcher, Developer, Multimedia) em paralelo, com progresso real ligado ao WebSocket do ComfyUI.

**Sessão:** 2026-05-17 — teste end-to-end do AgentGUI com correções de bugs e implementação de progresso real.

---

## Arquitetura do AgentGUI

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (localhost:5020)                                   │
│  - Dashboard HTML com botões de lançar/matar/ver agentes  │
│  - Polling do estado via /api/agents                        │
└──────────────┬──────────────────────────────────────────────┘
               │ REST API
┌──────────────▼──────────────────────────────────────────────┐
│  Flask Server (server.py, port 5020)                        │
│  - SSE endpoint para streaming real-time                      │
│  - State persistente em data/agent_state.json               │
└──────────────┬──────────────────────────────────────────────┘
               │ tmux sessions
┌──────────────▼──────────────────────────────────────────────┐
│  Profile Runners (run_multimedia.py, run_developer.py)      │
│  - Cada agente corre numa sessão tmux isolada               │
│  - Runner chama generate_with_progress.py ou hermes chat     │
└──────────────┬──────────────────────────────────────────────┘
               │
┌──────────────▼──────────────┐  ┌───────────────────────────┐
│  generate_with_progress.py  │  │  hermes chat -q -Q ...  │
│  - WebSocket → progresso    │  │  (para análise, audio)   │
│  - HTTP polling → completo  │  │                           │
└──────────────┬──────────────┘  └───────────────────────────┘
               │ WebSocket + HTTP
┌──────────────▼──────────────────────────────────────────────┐
│  ComfyUI (Windows host, 192.168.144.1:8188 via proxy)      │
│  - Proxy TCP: WSL→Windows sem expor portas                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Componentes Criados

### 1. generate_with_progress.py
Script standalone que invoca ComfyUI directamente e reporta progresso em tempo real.

**Padrão de progresso:**
- 0-10%: Setup / carregar workflow / enviar para ComfyUI
- 10-90%: Sampler steps (WebSocket `progress` events do ComfyUI)
- 90-100%: Save + finalização
- 100%: "Concluído: N imagem(ns) gerada(s)"

**Mapeamento progresso:**
```python
sampler_pct = (step / max_steps) * 80
progress = int(10 + sampler_pct)  # 10-90% range
```

**Comunicação com runner:**
- Escreve progresso em `/tmp/progress_{agent_id}.json` a cada segundo
- Runner lê o file e chama `update_agent()` para actualizar estado no dashboard

### 2. run_multimedia.py (runner actualizado)
Decisão automática:
- Se a tarefa tem `prompt` longo (>20 chars) → chama `generate_with_progress.py` (progresso real)
- Senão → delega ao Hermes genérico (`hermes chat -q -Q --ignore-rules --source tool`)

### 3. server.py (Flask)
Endpoints:
- `POST /api/agents/launch` — cria task file + regista agente + lança tmux
- `GET /api/agents` — lista todos os agentes
- `GET /api/agents/<id>` — estado de um agente
- `GET /api/agents/<id>/output` — output do agente
- `POST /api/agents/<id>/kill` — matar agente
- `GET /api/stream` — SSE para updates real-time

---

## WebSocket ComfyUI — Formato de Eventos

**Descoberta crítica:** O ComfyUI NÃO envia `execution_success`, `execution_error`, ou `execution_interrupted` via WebSocket. O WebSocket apenas envia:

| Evento WebSocket | Dados | Significado |
|------------------|-------|-------------|
| `execution_start` | `prompt_id`, `timestamp` | Job iniciado |
| `executing` | `node` (node_id) | Node actual a correr |
| `progress` | `value`, `max`, `prompt_id`, `node` | Step do sampler |
| `executed` | `node`, `output` | Node completado (com imagens) |

**NÃO enviado via WebSocket:**
- `execution_success` — apenas disponível via HTTP `/history/{prompt_id}`
- `execution_error` — apenas via HTTP
- `execution_interrupted` — apenas via HTTP

**Consequência:** Para detetar conclusão, é obrigatório usar HTTP polling de `/history/{prompt_id}` a cada 5 segundos, NUNCA esperar evento WebSocket de término.

---

## HTTP /history/{prompt_id} — Estrutura de Resposta

```json
{
  "status": {
    "status_str": "success",
    "completed": true,
    "messages": [
      ["execution_start", {"prompt_id": "...", "timestamp": 1234567890}],
      ["execution_cached", {"nodes": ["5"], "prompt_id": "..."}],
      ["execution_success", {"prompt_id": "...", "timestamp": 1234567900}]
    ]
  },
  "outputs": {
    "9": {
      "images": [
        {"filename": "AGENTGUI_00001_.png", "subfolder": "", "type": "output"}
      ]
    }
  }
}
```

**Check de conclusão:**
```python
if history.get("status", {}).get("completed"):
    # Job terminou com sucesso
    images = extract_from_outputs(history.get("outputs", {}))
```

---

## Fixes Necessários no Hermes CLI

### 1. hermes chat -q fica em loop interativo
O comando `hermes chat -q` inicia uma sessão de chat normal que fica à espera de input do utilizador. Quando chamado via `subprocess.run(capture_output=True)`, o processo hermes nunca termina porque entra no REPL.

**Solução:** Adicionar flags para modo programático:
```bash
hermes chat -q "prompt aqui" -Q --ignore-rules --source tool
```
- `-Q` / `--quiet`: Suprime banner, spinner, tool previews — apenas output final
- `--ignore-rules`: Não injecta AGENTS.md, SOUL.md, .cursorrules (evita conflitos)
- `--source tool`: Marca a sessão como integração de ferramenta (não aparece na lista de sessões do utilizador)

### 2. stdin=subprocess.DEVNULL
Quando `hermes chat` corre via subprocess, pode ficar à espera de stdin. Adicionar:
```python
subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, ...)
```

---

## Configuração do ComfyUI para AgentGUI

### Checkpoint preferido
- **Modelo:** `DreamShaperXL_Turbo_v2_1.safetensors`
- **Resolução:** 2400×1350 (16:9 widescreen)
- **Steps:** 70
- **CFG:** 7.0-8.0
- **Sampler:** euler / normal

### Workflow base
- `D:/AI_Ecosystem/03_Workflows/API/Text2Image.json` — workflow genérico SDXL
- Node IDs: 3=KSampler, 4=CheckpointLoaderSimple, 5=EmptyLatentImage, 6/7=CLIPTextEncode, 9=SaveImage
- Para bypass de IP-Adapter: ligar KSampler ao CheckpointLoaderSimple em vez de IPAdapterAdvanced

### Proxy WSL→ComfyUI
```python
# Proxy TCP Python
# Escuta em 192.168.144.1:8188 (rede virtual Hyper-V, inacessível de fora)
# Redirecciona para 127.0.0.1:8188 (ComfyUI localhost)
# Ficheiro: D:/AI_Ecosystem/08_Config/wsl_comfyui_proxy.py
```
NUNCA usar `--listen 0.0.0.0` no ComfyUI — manter em localhost para segurança.

---

## Arranque do AgentGUI

### Manual
```bash
cd /mnt/d/AI_Ecosystem/10_Projects/02_AgentGUI
source venv/bin/activate
python3 server.py
```
Aceder em: http://127.0.0.1:5020

### Via script
```bash
cd /mnt/d/AI_Ecosystem/10_Projects/02_AgentGUI
./start_server.sh   # ativa venv + inicia server
```

---

## Bugs Encontrados e Corrigidos

### Bug 1: Prompt da imagem não passado ao agente
**Sintoma:** Agente multimedia perguntava "qual é o prompt?" em vez de usar o da tarefa.
**Causa:** `run_multimedia.py` só passava `task['goal']`, não `task['prompt']`.
**Fix:** Adicionar secção `## PROMPT DA IMAGEM` ao prompt do Hermes.

### Bug 2: Runner escreve log apenas no final
**Sintoma:** Dashboard mostrava progresso 30% o tempo todo, só actualizava no final.
**Causa:** `subprocess.run(capture_output=True)` só retorna quando o processo termina.
**Fix:** Para geração de imagem, usar `generate_with_progress.py` com polling do progress file. Para análise, manter `capture_output=True`.

### Bug 3: ComfyUI não reporta conclusão via WebSocket
**Sintoma:** Script ficava preso no final (step 70/70 = 90%) e nunca terminava.
**Causa:** WebSocket do ComfyUI não envia `execution_success`.
**Fix:** Adicionar HTTP polling de `/history/{prompt_id}` como detetor primário de conclusão.

---

## Ficheiros do AgentGUI

| Ficheiro | Localização |
|----------|-------------|
| Server Flask | `D:/AI_Ecosystem/10_Projects/02_AgentGUI/server.py` |
| Gerador com progresso | `D:/AI_Ecosystem/10_Projects/02_AgentGUI/generate_with_progress.py` |
| Runner multimedia | `D:/AI_Ecosystem/10_Projects/02_AgentGUI/profiles/run_multimedia.py` |
| Runner developer | `D:/AI_Ecosystem/10_Projects/02_AgentGUI/profiles/run_developer.py` |
| Runner researcher | `D:/AI_Ecosystem/10_Projects/02_AgentGUI/profiles/run_researcher.py` |
| Estado persistente | `D:/AI_Ecosystem/10_Projects/02_AgentGUI/data/agent_state.json` |
| Arranque rápido | `D:/AI_Ecosystem/10_Projects/02_AgentGUI/start_server.sh` |
| Dashboard HTML | `D:/AI_Ecosystem/10_Projects/02_AgentGUI/templates/index.html` |
| Core state | `D:/AI_Ecosystem/10_Projects/02_AgentGUI/core/state.py` |
| Core runner | `D:/AI_Ecosystem/10_Projects/02_AgentGUI/core/runner.py` |

---

## Estado do Arranque.txt

Secção **8.6 AgentGUI** adicionada ao `D:/AI_Ecosystem/Arranque.txt`:
- Porta 5020
- Comando de arranque (WSL2)
- Dependência: ComfyUI a correr + proxy WSL ativo
