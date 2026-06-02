# Bug #31918 — PluginContext stale-class failure

## Sintoma

`web_search` retorna:
```
{"success": false, "error": "No web search provider configured. Run `hermes tools` to set one up."}
```

- `config.yaml` tem `web.backend: tavily`, `web.search_backend: tavily`, `web.extract_backend: tavily`
- `~/.hermes/.env` tem `TAVILY_API_KEY` válida
- `check-gateway-env.py` confirma que a key está no ambiente do processo
- `use_gateway` está `false`
- Mas mesmo assim `web_search` continua a falhar

## Causa Raiz

GitHub issue #31918: O plugin `web-tavily` falha ao carregar durante o gateway startup com erro:
```
Failed to load plugin 'web-tavily': 'PluginContext' object has no attribute 'register_web_search_provider'
```

O método `register_web_search_provider()` existe no ficheiro `plugins.py` mas o `PluginContext` usado pelo plugin é uma **stale class** — uma versão antiga do módulo carregada via editable install ou forked gateway process. O plugin recebe uma `PluginContext` que não tem o método, falha ao chamar `register_fn(ctx)`, e o provider nunca é registado.

Isto afecta **todos os web plugins**: `web-tavily`, `web-exa`, `web-firecrawl`, `web-parallel`, `web-searxng`, `web-brave-free`, `web-ddgs`.

## Estado do Fix Upstream

- Commit `deef901` por `jpoindexter` (co-authored by Claude Sonnet 4.6) contém o fix
- O commit ainda **não pertence a nenhuma branch** no repositório upstream
- Release 0.15.2 (29 Mai 2026) **não inclui** o fix
- Significa que `pipx upgrade hermes-agent` para 0.15.2 não resolve

## Fix Manual (até release com patch)

### Passo 1: Localizar `plugins.py`

```bash
SITE=$(python3 -c "import hermes_cli.plugins, pathlib, sys; print(pathlib.Path(hermes_cli.plugins.__file__).parent)")
echo "Path: $SITE/hermes_cli/plugins.py"
```

Tipicamente:
- pipx install: `~/.local/share/pipx/venvs/hermes-agent/lib/python3.12/site-packages/hermes_cli/plugins.py`
- pip install: `~/.local/lib/python3.12/site-packages/hermes_cli/plugins.py`

### Passo 2: Aplicar patch

Editar o ficheiro `plugins.py`, procurar a secção `_load_plugin` onde `ctx = PluginContext(manifest, self)` é criado (cerca da linha 1428 na 0.15.2), e substituir por:

```python
            else:
                # Resolve PluginContext from the authoritative sys.modules
                # entry at call time.  If hermes_cli/plugins.py was imported
                # under a secondary module name (e.g. by a stale editable
                # install or a forked gateway process), the module-level name
                # could refer to an older class that predates methods like
                # register_web_search_provider.  Pulling from sys.modules
                # ensures the plugin always receives the live, fully-defined
                # PluginContext, matching bug #31918.
                _live_mod = sys.modules.get("hermes_cli.plugins")
                _PluginContext = (
                    getattr(_live_mod, "PluginContext", None) or PluginContext
                )
                ctx = _PluginContext(manifest, self)
                register_fn(ctx)
```

### Passo 3: Reiniciar Hermes

O gateway precisa de recarregar os plugins. Reiniciar completamente:
```bash
# Matar processos hermes existentes
kill $(pgrep -f hermes)

# Reiniciar
hermes
```

Ou simplesmente sair da sessão TUI e voltar a entrar.

## Workaround Alternativo (sem patch no código)

Se não puderes aplicar o patch manual, usar **workaround por browser**:

```
browser_navigate <-- URL do motor de busca (Google, DuckDuckGo, etc.)
```

Ou chamar a API Tavily directamente via `execute_code` + `requests`:

```python
import os, requests
key = os.environ["TAVILY_API_KEY"]
resp = requests.post("https://api.tavily.com/search", json={
    "api_key": key,
    "query": "sua pesquisa",
    "search_depth": "basic",
    "max_results": 5
})
for r in resp.json()["results"]:
    print(r["title"], "|", r["url"])
```

## Verificação após fix

```bash
python3 -c "
from hermes_cli.plugins import PluginContext
print('register_web_search_provider exists:', hasattr(PluginContext, 'register_web_search_provider'))
"
```

Deve retornar `True`.

Depois de reiniciar:
```
web_search(query="test", limit=2)
```
Deve retornar resultados em vez do erro "No provider configured".

## Metadata

- Issue: https://github.com/NousResearch/hermes-agent/issues/31918
- Commit fix: `deef901` (por `jpoindexter`, co-authored by `Claude Sonnet 4.6`)
- Commit message: "fix: six upstream bug fixes (#31918, #31548, #31658, #31570, #31480, #31983)"
- Fix descrição: "plugins: resolve PluginContext from sys.modules at load time to prevent stale-class failures when web plugins call register_web_search_provider() at gateway startup"
- Primeiro reportado: ~2026-05-20
- Sessão de patch aplicado: 2026-05-31
