# Pitfall: web.use_gateway = true quebra web_search mesmo com config correta

## Sintoma

- `config.yaml` tem `web.backend: tavily`, `search_backend: tavily`, `extract_backend: tavily` — corretos.
- `~/.hermes/.env` tem `TAVILY_API_KEY` válida.
- `check-gateway-env.py` confirma que a key está no ambiente do processo gateway.
- Mesmo assim, `web_search` continua a retornar:
  > `No web search provider configured.`

## Causa Raiz

`web.use_gateway: true` no `config.yaml` faz com que todas as chamadas `web_search` / `web_extract` sejam encaminhadas pelo **gateway process**, não pelo agente diretamente.

O gateway não carrega a config de `web:` dinamicamente. Se:
1. O gateway foi iniciado **antes** da key estar no `.env`, **ou**
2. O gateway tem um bug interno nas rotas de delegação de pesquisa,

… a chamada falha apesar de tudo estar configurado corretamente no lado do config/agente.

## Fix

Mudar para `use_gateway: false`:
```bash
hermes config set web.use_gateway false
```

Depois **reiniciar o gateway** (não apenas `/reset` na conversa):
```bash
hermes gateway restart
```

## Porquê funciona com o workaround execute_code + Tavily API direta?

Quando o agente corre `execute_code` com requests diretos à API Tavily, o Python roda como processo filho do agente, tendo acesso ao ambiente real (incluindo variáveis carregadas do `.env`). Desta forma contorna completamente o `use_gateway: true`.

## Regra de ouro para depuração

Sempre que `web_search` falha, verificar esta sequência:
1. `grep search_backend ~/.hermes/config.yaml`
2. `grep TAVILY_API_KEY ~/.hermes/.env`
3. `python3 ~/.hermes/skills/autonomous-ai-agents/hermes-agent/scripts/check-gateway-env.py`
4. **`grep use_gateway ~/.hermes/config.yaml`** ← o passo esquecido até 2026-05-25
5. Se `use_gateway: true`, mudar para `false` e reiniciar o gateway.
