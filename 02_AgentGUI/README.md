# AgentGUI — Painel de Controlo de Agentes Paralelos

## Objetivo
Dashboard web para lançar, monitorizar, e gerir agentes Hermes em paralelo via tmux.

## Estado
- [x] Core state.py (JSON state manager)
- [x] Core runner.py (tmux launcher)
- [ ] Server Flask + SSE
- [ ] UI HTML/CSS/JS
- [ ] Scripts de perfil (researcher, developer, multimedia)

## Como funciona
1. Utilizador clica "Lançar Researcher" no dashboard
2. Server Flask cria ficheiro de tarefa + lança sessão tmux
3. O tmux corre `hermes chat -q` com o prompt + SOUL.md do perfil
4. O agente escreve output para um ficheiro de log
5. Dashboard faz SSE (Server-Sent Events) para receber atualizações
6. Utilizador pode clicar "Ver output" para ver o terminal live

## Estrutura
```
02_AgentGUI/
├── server.py                 # Flask API + SSE
├── core/
│   ├── state.py              # JSON state manager
│   └── runner.py             # tmux launcher
├── profiles/
│   ├── run_researcher.py     # Script que corre hermes chat -q
│   ├── run_developer.py
│   └── run_multimedia.py
├── templates/index.html      # Dashboard UI
├── static/style.css
├── static/app.js             # Frontend JS (SSE, botões)
└── data/                     # agent_state.json, logs, tasks
```
