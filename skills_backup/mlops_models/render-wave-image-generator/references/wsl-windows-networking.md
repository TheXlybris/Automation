# Lição: WSL → Windows Host Networking

## Contexto
O ComfyUI corre no Windows host (localhost:8188) mas o agent Hermes opera no WSL. A comunicação entre WSL e Windows host tem nuances críticas.

## IPs Involvidos
- `127.0.0.1` (localhost) no WSL → referencia-se a si próprio, NÃO ao Windows host
- `127.0.0.1` no Windows → referencia-se a si próprio (onde o ComfyUI corre)
- IP do host Windows visto pelo WSL → descobrir via `ip route | grep default`

## Como Descobrir o IP Correcto
```bash
ip route | grep default | awk '{print $3}'
# Tipicamente retorna: 192.168.144.1 (ou similar, depende da config WSL)
```

## Regra de Ouro
> **NUNCA use `127.0.0.1` ou `localhost` desde o WSL para aceder ao Windows host. Use sempre o IP descoberto via `ip route`.**

## Padrão Robustez — Módulo Partilhado (v2, 2026-05-13)

Em vez de hardcodear o IP em cada script, criar um módulo `comfyui_config.py` reutilizável:

```python
# comfyui_config.py
import os
import subprocess

def get_host_ip() -> str:
    try:
        result = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if line.startswith("default"):
                parts = line.split()
                if "via" in parts:
                    return parts[parts.index("via") + 1]
    except Exception:
        pass
    return os.environ.get("COMFYUI_HOST_IP", "127.0.0.1")

def get_comfyui_url() -> str:
    return f"http://{get_host_ip()}:{os.environ.get('COMFYUI_PORT', '8188')}"
```

Usar nos scripts via import:
```python
from comfyui_config import get_comfyui_url
COMFYUI_URL = get_comfyui_url()  # "http://192.168.144.1:8188"
```

Benefícios:
- Scripts auto-detectam o IP sem edição manual
- Fallback via env var `COMFYUI_HOST_IP` se detecção falhar
- Um único local para mudar a porta (env var `COMFYUI_PORT`)

## Dashboard HTML — Verificar ComfyUI via Backend

O dashboard HTML nunca deve fazer `fetch` direto ao ComfyUI (`http://127.0.0.1:8188`) porque:
1. O browser corre em WSL ou Windows — `127.0.0.1` pode não ser o ComfyUI
2. O IP correcto é dinâmico e conhecido apenas pelo backend Python

**Solução:** Criar endpoint `/comfyui_status` no Flask:
```python
@app.route("/comfyui_status")
def comfyui_status():
    try:
        r = requests.get(f"{COMFYUI_URL}/system_stats", timeout=3)
        return jsonify({"online": True, "url": COMFYUI_URL})
    except Exception as e:
        return jsonify({"online": False, "url": COMFYUI_URL, "error": str(e)})
```

O JavaScript consulta `/comfyui_status` (mesma origem) em vez do ComfyUI diretamente:
```javascript
async function checkComfyUI() {
    const r = await fetch('/comfyui_status', {signal: AbortSignal.timeout(3000)});
    const data = await r.json();
    // data.online = true/false, data.url = "http://192.168.144.1:8188"
}
```

**Pitfall antigo:** Tentar fazer `fetch('http://127.0.0.1:8188/system_stats')` do browser — isto falha quando:
- O browser corre no Windows e o ComfyUI também está em Windows (`127.0.0.1` funciona)
- O browser corre no WSL e o ComfyUI está no Windows (`127.0.0.1` no WSL = WSL, não Windows)
- O IP do host muda (ex: depois de `wsl --shutdown`)

## Configuração do ComfyUI — Segurança reforçada (sem expor portas)

**NÃO usar `--listen 0.0.0.0`** se o objetivo é manter o ComfyUI acessível apenas localmente. O utilizador do THE RENDER WAVE reforçou a segurança — o ComfyUI deve permanecer em `127.0.0.1:8188` (localhost only).

**Solução correta:** Proxy TCP Python no Windows que redireciona `192.168.144.1:8188` → `127.0.0.1:8188`. Detalhes completos em `references/wsl-comfyui-secure-proxy.md`.

**Quando `--listen 0.0.0.0` é aceitável:** Apenas em ambientes isolados ou redes domésticas onde expor a porta não é um risco.

## Verificação
```bash
# Desde o WSL, testar conectividade
curl -s http://192.168.144.1:8188/system_stats
# Deve retornar JSON com info do sistema
```

## Se Falhar
1. Confirmar que ComfyUI está a correr no Windows (ver janela/terminal)
2. Confirmar que foi iniciado com `--listen 0.0.0.0`
3. Confirmar firewall do Windows não bloqueia porta 8188
4. Tentar `ping 192.168.144.1` desde o WSL
5. Se WSL2: verificar se WSL config permite networking (geralmente sim por defeito)

## Pitfall Comum
O script pode estar configurado com `127.0.0.1:8188` por conveniência/localidade, mas isso só funciona se o script correr NO MESMO host que o ComfyUI. Desde o WSL, isso falha com `Connection refused`.

## Solução Antiga (hardcode)
O script deve ter uma função de auto-descoberta:
```python
def get_host_ip():
    import subprocess
    result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if 'default' in line:
            return line.split()[2]  # Ex: 192.168.144.1
    return '127.0.0.1'  # fallback
```

**Preferir o padrão de módulo partilhado (2026-05-13)** — mais limpo e reutilizável.