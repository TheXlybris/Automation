# Correção: image_generator.html + server.py
## Data: 2026-05-09
## Problema: "[ERRO] Failed to fetch" ao usar image_generator.html

### Sintoma
O utilizador abre `image_generator.html` no navegador, clica "Gerar Imagem", e vê:
```
[ERRO] Failed to fetch
Verifique se o servidor Flask esta a correr na porta 5000.
```

### Causas

1. **URLs relativas no fetch** — Quando o HTML é aberto via `file://` (duplo-clique no ficheiro), `fetch('/generate')` falha porque não há servidor HTTP. URLs relativas só funcionam quando o HTML é servido pelo Flask (`http://127.0.0.1:5000`).

2. **Bug NameError no server.py** — Linha 96 usava variável `json_line` que nunca existiu. Se o script `generate_image.py` retornasse JSON mal formatado, o servidor crashava com NameError em vez de retornar erro útil ao cliente.

### Fixes aplicados

#### Fix 1: image_generator.html — URLs absolutas com fallback

Adicionado no início do script:
```javascript
const API_BASE = window.location.protocol === 'file:'
    ? 'http://127.0.0.1:5000'
    : '';
```

E alterado todos os `fetch('/...')` para `fetch(API_BASE + '/...')`.

Resultado: Se aberto via `file://`, o HTML aponta para `http://127.0.0.1:5000`. Se aberto via servidor, usa URLs relativas como antes.

#### Fix 2: image_generator.html — Tratamento de erro HTTP

Adicionado após `fetch()`:
```javascript
if (!res.ok) {
    const text = await res.text();
    throw new Error('HTTP ' + res.status + ': ' + text.substring(0, 200));
}
```

Antes: respostas HTTP 404/500 eram silenciosamente passadas para `res.json()`, que falhava com parse error genérico.
Depois: mostra código HTTP e texto da resposta, facilitando diagnóstico.

#### Fix 3: image_generator.html — Mensagens de erro contextuais

```javascript
if (window.location.protocol === 'file:') {
    log('O HTML foi aberto via ficheiro local. Certifica-te de que:', true);
    log('  1. O servidor Flask esta a correr: python server.py', true);
    log('  2. Abres o HTML via http://127.0.0.1:5000', true);
} else {
    log('Verifique se o servidor Flask esta a correr na porta 5000.', true);
}
```

#### Fix 4: server.py — NameError corrigido

Linha 96 original:
```python
"raw": json_line if 'json_line' in dir() else str(e)
```

Corrigido para:
```python
"raw": output_text[-500:]
```

A variável `json_line` nunca foi definida nesta função. `output_text` é a saída real do subprocess `generate_image.py`, que contém o JSON bruto (ou a mensagem de erro) que falhou ao fazer parse.

### Como usar corretamente

**1. Iniciar o servidor Flask:**
```bash
cd D:\AI_Ecosystem\10_Projects\01_YTAutomation\Image_creation
.\venv\Scripts\python.exe server.py
```

**2. Abrir o HTML:**
- **Correto:** Navegador → `http://127.0.0.1:5000`
- **Também funciona agora:** Duplo-clique no ficheiro HTML (apresenta aviso informativo)

**3. Porta 5000 já em uso:**
Se aparecer "Address already in use", verificar:
```bash
netstat -ano | findstr :5000
# ou
lsof -i :5000
```
Matar processo existente ou alterar porta no `server.py` (linha `app.run(host="0.0.0.0", port=5000)`).

### Ficheiros relevantes
- `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Image_creation\server.py` — Flask backend (porta 5000)
- `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Image_creation\image_generator.html` — UI dark-theme (served by Flask or opened via file://)
- `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Image_creation\generate_image.py` — script de CLI que faz POST ao ComfyUI
- `D:\AI_Ecosystem\03_Workflows\API\Text2Image.json` — workflow API JSON (formato de dict plano, exportado via "Save (API Format)")

---

## Problema (sessão 2026-05-11): "Failed to fetch" mesmo com servidor a correr

### Sintoma
O utilizador:
1. Apagou a pasta `Video_creation` para recomeçar de novo
2. Consegue gerar imagem no ComfyUI UI manualmente
3. Ao abrir `http://127.0.0.1:5000` — página abre mas não aparece nada (vazia/loading infinito)
4. Ao abrir `image_generator.html` via duplo-clique — página abre, mas ao clicar "Gerar Imagem":
   ```
   [ERRO] Failed to fetch
   O HTML foi aberto via ficheiro local. Certifica-te de que:
     1. O servidor Flask esta a correr: python server.py
     2. Abres o HTML via http://127.0.0.1:5000
   ```

### Diagnóstico realizado

1. **Porta 5000 vazia** — `lsof -i :5000` e `ss -tlnp | grep 5000` confirmaram que nada estava a ouvir na porta 5000.
2. **Servidor não estava a correr** — O utilizador assumia que o servidor estava ativo, mas tinha sido encerrado ou nunca foi iniciado nesta sessão.
3. **Caminho do workflow desatualizado no `generate_image.py`** — Linha 15 apontava para `/mnt/c/Users/Fil_B/Downloads/Text2Image_API.json` (ficheiro que já não existe). O workflow actual está em `D:\AI_Ecosystem\03_Workflows\API\Text2Image.json`.

### Fixes aplicados (2026-05-11)

#### Fix A: Corrigir WORKFLOW_PATH em generate_image.py

**Antes:**
```python
WORKFLOW_PATH = "/mnt/c/Users/Fil_B/Downloads/Text2Image_API.json"
```

**Depois:**
```python
WORKFLOW_PATH = "/mnt/d/AI_Ecosystem/03_Workflows/API/Text2Image.json"
```

**Porquê:** O script falhava silenciosamente a validação `os.path.exists(WORKFLOW_PATH)` e retornava erro "Workflow nao encontrado" no JSON de resposta. O server.py parseava esse erro como JSON inválido, resultando em `Failed to fetch` para o browser.

#### Fix B: Garantir que o servidor Flask está a correr

O utilizador precisa de iniciar o servidor explicitamente:
```bash
cd /mnt/d/AI_Ecosystem/10_Projects/01_YTAutomation/Image_creation
venv/bin/python3 server.py
```

**Output esperado:**
```
==================================================
RENDER WAVE - Image Generator Server
==================================================
Pasta de imagens: /mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output
Workflow: /mnt/d/AI_Ecosystem/03_Workflows/API/Text2Image.json

Abre no navegador: http://127.0.0.1:5000
==================================================
```

#### Fix C: Abrir a página corretamente

- **Correto:** Navegador → `http://127.0.0.1:5000` (servido pelo Flask)
- **Funciona com fallback:** Duplo-clique no `image_generator.html` (o HTML detecta `file://` e aponta para `http://127.0.0.1:5000/generate`)
- **Errado:** Esperar que a página abra sozinha sem o servidor estar a correr

### Validação final
- `curl -s http://127.0.0.1:5000` → retorna HTML
- `curl -s -X POST ... -d '{"prompt":""}'` → `Status: error | Msg: Prompt vazio` (validação funciona)
- `venv/bin/python3 generate_image.py --prompt "test" ...` → gera imagem com sucesso
- Imagem aparece em `/mnt/d/AI_Ecosystem/02_Engines/ComfyUI/ComfyUI/output/RENDERWAVE_20260511_233459_00001_.png`

### Pitfalls adicionais identificados nesta sessão

| Problema | Causa | Solução |
|----------|-------|---------|
| Servidor Flask parado | Não foi iniciado nesta sessão | Sempre verificar `lsof -i :5000` antes de diagnosticar o browser |
| Workflow path hardcoded errado | Script aponta para Downloads antigo | Actualizar `WORKFLOW_PATH` para `03_Workflows/API/Text2Image.json` |
| `generate_image.py` usa `C:\Users\...` (Windows path) no WSL | Mistura de path formats | Usar sempre paths WSL (`/mnt/d/...`) em scripts Python que correm no WSL |
| Imagem gerada mas não aparece no browser | `image_generator.html` aberto via `file://` sem servidor | Abrir via `http://127.0.0.1:5000` ou garantir que o servidor está a correr |
| `Failed to fetch` genérico | Erro no backend (workflow não encontrado) propagado como fetch failure | Verificar logs do `server.py` no terminal; o erro real está lá |

### Workflow path conventions

| Tipo | Localização WSL | Localização Windows |
|------|-----------------|---------------------|
| API format | `/mnt/d/AI_Ecosystem/03_Workflows/API/Text2Image.json` | `D:\AI_Ecosystem\03_Workflows\API\Text2Image.json` |
| UI format | `/mnt/d/AI_Ecosystem/03_Workflows/Text2Image.json` | `D:\AI_Ecosystem\03_Workflows\Text2Image.json` |

**API format** = dict plano com node IDs como chaves (ex: `"3"`, `"4"`, `"5"`). Usado por `generate_image.py`.
**UI format** = lista de nodes com metadados (ex: `nodes`, `links`, `groups`). NÃO é compatível com injeção direta de parâmetros.

**Exportação do ComfyUI:**
1. Abrir workflow no ComfyUI UI
2. Clicar "Save (API Format)" → salva em `03_Workflows/API/`
3. Verificar que o JSON tem estrutura de dict plano (ex: `{"3": {"inputs": ...}, "4": {...}}`)
4. NUNCA usar o ficheiro guardado via "Save" normal (formato UI) para automação

### Checklist de troubleshooting do image generator

Antes de reportar erro "Failed to fetch":
1. [ ] Verificar porta 5000: `lsof -i :5000` ou `ss -tlnp | grep 5000`
2. [ ] Se vazio, iniciar servidor: `venv/bin/python3 server.py`
3. [ ] Verificar workflow path: `ls -la /mnt/d/AI_Ecosystem/03_Workflows/API/Text2Image.json`
4. [ ] Testar script CLI: `venv/bin/python3 generate_image.py --prompt "test" --width 512 --height 512 --steps 5`
5. [ ] Testar endpoint: `curl -s http://127.0.0.1:5000 | head -3`
6. [ ] Abrir browser em `http://127.0.0.1:5000` (não duplo-clique no HTML)

---

## Data: 2026-05-09
## Problema: "[ERRO] Failed to fetch" ao usar image_generator.html

### Sintoma
O utilizador abre `image_generator.html` no navegador, clica "Gerar Imagem", e vê:
```
[ERRO] Failed to fetch
Verifique se o servidor Flask esta a correr na porta 5000.
```

### Causas

1. **URLs relativas no fetch** — Quando o HTML é aberto via `file://` (duplo-clique no ficheiro), `fetch('/generate')` falha porque não há servidor HTTP. URLs relativas só funcionam quando o HTML é servido pelo Flask (`http://127.0.0.1:5000`).

2. **Bug NameError no server.py** — Linha 96 usava variável `json_line` que nunca existiu. Se o script `generate_image.py` retornasse JSON mal formatado, o servidor crashava com NameError em vez de retornar erro útil ao cliente.

### Fixes aplicados

#### Fix 1: image_generator.html — URLs absolutas com fallback

Adicionado no início do script:
```javascript
const API_BASE = window.location.protocol === 'file:'
    ? 'http://127.0.0.1:5000'
    : '';
```

E alterado todos os `fetch('/...')` para `fetch(API_BASE + '/...')`.

Resultado: Se aberto via `file://`, o HTML aponta para `http://127.0.0.1:5000`. Se aberto via servidor, usa URLs relativas como antes.

#### Fix 2: image_generator.html — Tratamento de erro HTTP

Adicionado após `fetch()`:
```javascript
if (!res.ok) {
    const text = await res.text();
    throw new Error('HTTP ' + res.status + ': ' + text.substring(0, 200));
}
```

Antes: respostas HTTP 404/500 eram silenciosamente passadas para `res.json()`, que falhava com parse error genérico.
Depois: mostra código HTTP e texto da resposta, facilitando diagnóstico.

#### Fix 3: image_generator.html — Mensagens de erro contextuais

```javascript
if (window.location.protocol === 'file:') {
    log('O HTML foi aberto via ficheiro local. Certifica-te de que:', true);
    log('  1. O servidor Flask esta a correr: python server.py', true);
    log('  2. Abres o HTML via http://127.0.0.1:5000', true);
} else {
    log('Verifique se o servidor Flask esta a correr na porta 5000.', true);
}
```

#### Fix 4: server.py — NameError corrigido

Linha 96 original:
```python
"raw": json_line if 'json_line' in dir() else str(e)
```

Corrigido para:
```python
"raw": output_text[-500:]
```

A variável `json_line` nunca foi definida nesta função. `output_text` é a saída real do subprocess `generate_image.py`, que contém o JSON bruto (ou a mensagem de erro) que falhou ao fazer parse.

### Como usar corretamente

**1. Iniciar o servidor Flask:**
```bash
cd D:\AI_Ecosystem\10_Projects\01_YTAutomation\Image_creation
.\venv\Scripts\python.exe server.py
```

**2. Abrir o HTML:**
- **Correto:** Navegador → `http://127.0.0.1:5000`
- **Também funciona agora:** Duplo-clique no ficheiro HTML (apresenta aviso informativo)

**3. Porta 5000 já em uso:**
Se aparecer "Address already in use", verificar:
```bash
netstat -ano | findstr :5000
# ou
lsof -i :5000
```
Matar processo existente ou alterar porta no `server.py` (linha `app.run(host="0.0.0.0", port=5000)`).

### Ficheiros alterados
- `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Image_creation\image_generator.html`
- `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Image_creation\server.py`

### Não alterado
- Workflow `Text2Image_API.json` — intocável, funcional
- `generate_image.py` — intocável, funcional
