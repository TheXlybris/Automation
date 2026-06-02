# Clawd3D — OpenClaw Dependency in Hermes Desktop

Session: 2026-05-19
User: Fil_B
Context: THE RENDER WAVE

## O que é Clawd3D

O Clawd3D é uma feature da app `fathah/hermes-desktop` (Hermes Desktop) que
apresenta um "3D office" — um ambiente visual onde os agentes colaboram e
trabalham em paralelo. O wizard de setup tem 6 passos e começa com:

1. Welcome to Clawd3D — Your AI office in 3D
2. Before You Start — requisitos

## O problema: dependência do OpenClaw

A feature **requer OpenClaw** como backend, NÃO o Hermes CLI. O wizard pede:
- OpenClaw installed
- Gateway running (`openclaw gateway start`)
- Gateway URL and token
- Node.js 20+

Isto deixa o utilizador contrariado porque instalaou "Hermes Desktop" e a
feature principal pede-lhe para instalar outro produto (OpenClaw).

## Porquê acontece isto

1. O **standard Hermes CLI** é terminal-first. Não expõe um servidor
   WebSocket/PTY persistente que o Clawd3D possa consumir.
2. O **OpenClaw** já tem um gateway persistente com endpoints WebSocket.
3. O Clawd3D conecta-se a esse gateway.
4. O `fathah/hermes-desktop` é um wrapper de terceiros (não oficial NousResearch).

## Alternativas nativas do Hermes (sem OpenClaw)

Se o utilizador quer coordenar agentes em paralelo mas não quer instalar
OpenClaw, as opções do Hermes CLI são:

| Funcionalidade | Comando/Tool | Descrição |
|---|---|---|
| Kanban | `/kanban` ou `hermes kanban` | Board de tarefas com dispatcher automático |
| Agents ativos | `/agents` ou `/tasks` | Lista agentes e tarefas running na sessão |
| Profiles | `hermes profile list` | Agentes especializados permanentes |
| Delegation | `delegate_task` | Subagentes síncronos inline |

## Recomendação prática

- **Usar Kanban nativo** para multi-agent sem 3D visual:
  ```bash
  hermes kanban init
  hermes kanban create --title "Setup ComfyUI pipeline" --profile developer
  hermes kanban list
  ```
- **Fechar o wizard Clawd3D** e usar o resto da app Desktop normalmente.
  A app ainda suporta chat, profiles, sessions, skills, etc. sem OpenClaw.
- **Não migar para OpenClaw** — a app é para Hermes, não OpenClaw.

## Referências

- Sessões Hermes 2026-05-19 (madrugada + manhã)
- Ficheiro SKILL.md `hermes-agent` section "Desktop App Pitfall"
