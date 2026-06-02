# Web Search "No provider configured" — Diagnóstico Completo

## Sintoma

`web_search` retorna:
```
{"success": false, "error": "No web search provider configured. Run `hermes tools` to set one up."}
```

Apesar de:
- `config.yaml` ter `web.backend: tavily`, `web.search_backend: tavily`, `web.extract_backend: tavily`
- `~/.hermes/.env` ter `TAVILY_API_KEY=tvly-dev-...` (key válida)
- `/reset` ter sido executado na conversa

## Causa Raiz

O **gateway process** foi iniciado *antes* da `TAVILY_API_KEY` ser adicionada ao `.env`. O gateway carrega o `.env` uma vez no arranque e fork de worker processes. Alterações ao `.env` NÃO são propagadas para processos já em execução.

### Verificação

Verificar ambiente do processo gateway:
```bash
for pid in $(pgrep -f hermes); do
  echo "--- PID $pid ---"
  cat /proc/$pid/environ 2>/dev/null | tr '\0' '\n' | grep -i TAVILY || echo "  Nenhuma"
done
```

Resultado: `Nenhuma` em todos os PIDs Hermes.

A variável `TAVILY_API_KEY` está no `.env` mas NÃO no ambiente do processo.

## Fix

Reiniciar o gateway:
```bash
hermes gateway restart
```

Se não funcionar, matar e reiniciar completamente:
```bash
kill <gateway-pid> && hermes
```

SÓ DEPOIS do gateway reiniciar é que `/reset` na conversa faz sentido (para carregar o novo tool schema).

## Lição: /reset vs gateway restart

| Situação | `/reset` resolve? | Gateway restart necessário? |
|---|---|---|
| Troca de modelo de conversa | Sim | Não |
| Enable/disable toolsets | Sim | Não |
| Mudança de backend de web search (firecrawl → tavily) | Não | Sim |
| Adição de nova API key ao `.env` | Não | Sim |
| Mudança de config.yaml (qualquer secção) | Não | Sim |
| Instalação de novo skill | Sim | Não |

## Log de diagnóstico desta sessão (2026-05-19)

```
2026-05-19 14:15:08,506 WARNING ... Tool web_search returned error (0.01s):
  {"success": false,
   "error": "No web search provider configured. Run `hermes tools` to set one up."}
>>> config.yaml (correcto):   web: backend: tavily, search_backend: tavily
>>> .env (correcto):         TAVILY_API_KEY=tvly-dev-2NJeTl-...
>>> PID 914 env check:        TAVILY_API_KEY MISSING
>>> Conclusão: gateway stale, reiniciar necessário
```

## Scenario 2: Gateway runs as systemd service (does NOT auto-load `.env`)

If the gateway was started via `systemctl --user start hermes-gateway` (or auto- start on boot), the service definition does **not** read `~/.hermes/.env` automatically. The `EnvironmentFile=` directive must be added explicitly.

**Symptom:**
- `web_search` returns `No web search provider configured`
- `check-gateway-env.py` shows `TAVILY_API_KEY MISSING` in all gateway PIDs
- The key is present in `~/.hermes/.env` and valid
- The user starts sessions via SSH then runs `hermes` — neither systemd nor the shell loads `.env`

**Verify:**
```bash
# Check if gateway is a systemd service
systemctl --user status hermes-gateway

# Check if the service loads .env
grep -c "EnvironmentFile" ~/.config/systemd/user/hermes-gateway.service || echo "NOT LOADED"

# Check environment of running gateway process
cat /proc/$(pgrep -f "hermes_cli.main gateway")/environ | tr '\0' '\n' | grep TAVILY || echo "MISSING"
```

**Fix:**
```bash
# Step 1: Add EnvironmentFile to the systemd unit
sed -i '/Environment="HERMES_HOME=/a EnvironmentFile=-/home/xlybris/.hermes/.env' \
    ~/.config/systemd/user/hermes-gateway.service

# Step 2: Reload systemd and restart gateway
systemctl --user daemon-reload
systemctl --user restart hermes-gateway

# Step 3: Verify the key is now loaded
cat /proc/$(pgrep -f "hermes_cli.main gateway")/environ | tr '\0' '\n' | grep TAVILY
```

> **Note:** The `-` prefix in `EnvironmentFile=-/path` means systemd will not fail if the file does not exist. Remove the dash only if you want a hard dependency.

> **Important:** This fix is for the gateway service only. The interactive `hermes` CLI (PID 1132) also needs `.env` loaded but is typically started from a shell. For SSH sessions, add `source ~/.hermes/.env` to `~/.bashrc` or export the variable at login.

## Script de verificação rápida

```bash
python ~/.hermes/skills/autonomous-ai-agents/hermes-agent/scripts/check-gateway-env.py
```

Este script faz o mesmo que o loop manual acima, mas de forma compacta.

## Scenario 3: Bug #31918 — PluginContext stale-class failure (ALL web plugins affected)

**Added 2026-05-31.**

If you've ruled out the two scenarios above and `web_search` STILL returns `No web search provider configured`, the root cause is likely **bug #31918**.

### Diagnosis checklist

1. `config.yaml` has correct backends (`search_backend: tavily`, `extract_backend: tavily`)
2. `~/.hermes/.env` contains valid `TAVILY_API_KEY`
3. `use_gateway` is `false` (or gateway restart attempted)
4. **But** `web_search` still fails with the exact same error

### Confirming the bug

Check the Hermes logs for plugin load errors:
```bash
grep -i "register_web_search_provider" ~/.hermes/logs/errors.log ~/.hermes/logs/*.log 2>/dev/null || echo "No log entries found"
```

Expected pattern when bug is active:
```
Failed to load plugin 'web-tavily': 'PluginContext' object has no attribute 'register_web_search_provider'
```

This same error occurs for: `web-exa`, `web-firecrawl`, `web-parallel`, `web-searxng`, `web-brave-free`, `web-ddgs`.

### Fix

The upstream fix (commit `deef901`) is not yet in any release as of 0.15.2. Two options:

**Option A — Apply manual patch:**
Follow the step-by-step patch instructions in `references/bug-31918-plugincontext-patch.md`.
This modifies `hermes_cli/plugins.py` to resolve `PluginContext` from `sys.modules` at load time.

**Option B — Use browser workaround:**
As a temporary workaround, use `browser_navigate` to search engines (Google, DuckDuckGo) instead of `web_search`.
This bypasses the broken plugin system entirely.

**Option C — Call Tavily API directly:**
Use `execute_code` with Python `requests` to call the Tavily API directly.
Example script available in `references/bug-31918-plugincontext-patch.md`.

> **Critical:** After applying the manual patch, a **full Hermes restart** is required.
> `/reset` is not sufficient — the gateway must reload plugins from scratch.

### Related files

- Full reproduction and patch recipe: `references/bug-31918-plugincontext-patch.md`
- Upstream issue: https://github.com/NousResearch/hermes-agent/issues/31918
- Upstream fix commit: `deef901` (not yet in any release branch as of 2026-05-31)
