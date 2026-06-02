# Clawd3D Office Feature — Hermes Desktop App

Session: 2026-05-19 — User: Fil_B

## O que é o Clawd3D

O separador "Office" na app Hermes Desktop (fathah/hermes-desktop) não é uma feature do Hermes CLI. É um **componente separado chamado Clawd3D** — um ambiente 3D visual onde agentes AI colaboram.

**Clawd3D ≠ Hermes CLI multi-agent.** São stacks independentes.

## Requisitos para ativar o Office (Clawd3D)

O wizard de setup do Clawd3D pede:

1. **OpenClaw installed** — `npm install -g @openclaw/cli` (ou pnpm/source)
2. **Gateway running** — `openclaw gateway start`
3. **Gateway URL e token** — encontrado em `./openclaw/openclaw.json`
4. **Node.js 20+**

O Hermes Desktop app conecta-se ao gateway OpenClaw via WebSocket para mostrar os agentes no ambiente 3D.

## Como funciona

| Componente | Stack | Função |
|------------|-------|--------|
| Hermes Desktop app (fathah/hermes-desktop) | Electron + React | UI principal, chat, profiles |
| Clawd3D | Three.js/WebGL | Renderização 3D do escritório |
| OpenClaw gateway | Node.js | Backend de runtime dos agentes no 3D |

O Hermes Desktop app espera um **OpenClaw gateway** em `ws://localhost:18780` (ou outra porta), não o Hermes CLI.

## O que NÃO funciona

- **Hermes CLI como backend do Office:** O `hermes` CLI não expõe os endpoints WebSocket PTY que o Clawd3D espera.
- **Usar profiles Hermes no Clawd3D:** Os profiles são do Hermes CLI, não do OpenClaw. São sistemas de memória/persona separados.
- **Sincronização automática:** Não existe. O estado Hermes (sessões, skills, memory) não flui automaticamente para o OpenClaw ou vice-versa.

## Alternativa: Multi-Agent do Hermes CLI (sem Clawd3D)

Se o utilizador quer coordenar agentes mas não precisa do ambiente 3D, o Hermes CLI já tem:

| Feature | Comando/API | Escala |
|---------|-------------|--------|
| Kanban multi-agent | `hermes kanban init` + dispatch | Durable, SQLite-backed |
| Subagentes síncronos | Tool `delegate_task` | Inline, bound to turn |
| Spawn de processos | `tmux` + `hermes chat` | Totalmente independente |
| Profiles | `hermes profile create NAME` | Persistente, isolado |

## Recomendação para utilizadores Hermes CLI

1. **Se querem o 3D office:** Instalar OpenClaw separadamente, aceitando que é um ecossistema paralelo.
2. **Se querem só multi-agent:** Usar Kanban/profiles/delegation do Hermes CLI diretamente, fechar o wizard Clawd3D.
3. **Para sincronização Hermes ↔ OpenClaw:** Não existe solução built-in. Seria necessário um bridge custom.
