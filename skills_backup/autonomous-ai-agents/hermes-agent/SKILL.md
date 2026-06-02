---
name: hermes-agent
description: "Configure, extend, or contribute to Hermes Agent."
version: 2.2.1
author: Hermes Agent + Teknium
license: MIT
metadata:
  hermes:
    tags: [hermes, setup, configuration, multi-agent, spawning, cli, gateway, development]
    homepage: https://github.com/NousResearch/hermes-agent
    related_skills: [claude-code, codex, opencode]
---

> **Pitfall observado 2026-05-25:** `web.use_gateway: true` pode quebrar `web_search` mesmo quando `backend: tavily` e `TAVILY_API_KEY` estão corretos. Ver `references/web-use-gateway-pitfall.md`.

> **Pitfall observado 2026-05-25:** Se o gateway correr como systemd service (`systemctl --user`), NÃO carrega `~/.hermes/.env` automaticamente — é necessário adicionar `EnvironmentFile=` ao ficheiro do serviço. Ver `references/dotenv-pitfalls.md` Secção 5.

> **Pitfall observado 2026-05-25:** Mesmo com `EnvironmentFile=` adicionado, o gateway pode continuar sem acesso se a `~/.hermes/.env` contiver variáveis SSH (`TERMINAL_SSH_*`) acima de `TERMINAL_ENV=local`. Isso quebra o backend local após o setup. O erro genérico "No web search provider configured" pode esconder tanto `.env` não carregado como API key inválida. Ver `references/gateway-env-diagnosis.md` para árvore de diagnóstico completa.

> **Pitfall observado 2026-05-25:** O TUI (`hermes chat`) e o gateway (`hermes gateway`) usam árvores de processo separadas. Corrigir o `.env` num não corrige no outro. O TUI carrega `.env` no startup do Python via `env_loader`, mas se a shell que lançou não exportou a variável, ela ainda é `None`. A fix mais robusta é adicionar `source ~/.hermes/.env` ao `~/.bashrc` ou usar `set -a && source ~/.hermes/.env && hermes chat`. Ver `references/tui-env-loading-diagnosis.md`.

> **Pitfall observado 2026-05-31:** Bug #31918 — `web_search` retorna "No web search provider configured" mesmo com `search_backend: tavily` e `TAVILY_API_KEY` válida. Causa: o plugin `web-tavily` falha ao carregar com erro `'PluginContext' object has no attribute 'register_web_search_provider'`. O fix upstream (commit `deef901`) ainda não está em nenhuma release (0.15.2 não inclui). Solução: aplicar patch manual em `plugins.py` (ver `references/bug-31918-plugincontext-patch.md`) ou usar workaround `browser_navigate` para pesquisas online. Ver `references/web-search-no-provider-diagnosis.md` Secção "Scenario 3: Bug #31918 — PluginContext stale class".

---
