# WSL → ComfyUI Secure Proxy (sem expor portas)

## Contexto
O utilizador reforçou a segurança do ComfyUI — NÃO quer `--listen 0.0.0.0` porque expõe a porta 8188 para a rede local. O ComfyUI deve permanecer em `127.0.0.1:8188` (localhost only). Mas scripts no WSL2 precisam de aceder ao ComfyUI.

## Problema: WSL2 NAT não funciona com `netsh portproxy`

`netsh interface portproxy add v4tov4` é a solução "oficial" da Microsoft para encaminhar portas. Mas **não funciona com WSL2** porque o tráfego WSL2 passa pelo Hyper-V virtual switch (NAT), não pela interface física onde o portproxy opera. O portproxy recebe tráfego da interface física (Wi-Fi/Ethernet) mas o WSL2 nunca passa por aí.

Sintoma: proxy configurado, serviço IP Helper ativo, firewall com regra allow, mas curl do WSL dá timeout.

## Solução: Proxy TCP Python no Windows

Um script Python simples que corre no Windows, escuta em `192.168.144.1:8188` (interface virtual WSL) e redireciona tudo para `127.0.0.1:8188` (ComfyUI localhost).

**Porque é seguro:**
- `192.168.144.1` é um IP da **rede virtual interna** do Hyper-V (`vEthernet (WSL)`)
- Nenhum PC externo consegue aceder a este IP — o Windows não encaminha tráfego da internet para interfaces virtuais internas
- Apenas o **WSL2** e o **próprio Windows host** conseguem aceder
- O ComfyUI continua em localhost — nenhuma ligação externa chega a ele diretamente

**Ficheiros:**
- `D:\AI_Ecosystem\08_Config\wsl_comfyui_proxy.py` — proxy TCP genérico (HTTP + WebSockets)
- `D:\AI_Ecosystem\08_Config\start_wsl_proxy.bat` — atalho para arrancar

## Como usar

1. **No Windows:** Arrancar o proxy (deixa a janela aberta)
   ```cmd
   cd /d D:\AI_Ecosystem\08_Config
   python wsl_comfyui_proxy.py
   ```

2. **Confirmar que está ativo:**
   ```
   ==================================================
   WSL → ComfyUI Proxy
   ==================================================
   A escutar:    192.168.144.1:8188
   A redirecionar: 127.0.0.1:8188
   ==================================================
   Proxy ativo. Ctrl+C para parar.
   ```

3. **No WSL:** Testar conectividade
   ```bash
   curl -s --max-time 5 http://192.168.144.1:8188/system_stats
   ```

4. **Scripts Python no WSL:** Já detectam `192.168.144.1` automaticamente via `comfyui_config.py`

## Alternativas descartadas

| Opção | Porque foi descartada |
|-------|----------------------|
| `--listen 0.0.0.0` | Utilizador recusou — expõe ComfyUI para rede local |
| `netsh portproxy` | Não funciona com WSL2 NAT (Hyper-V virtual switch) |
| WSL2 mirrored networking | Requer alterar configuração global do WSL2 (`networkingMode=mirrored`), pode afetar Docker e outros serviços |
| Correr scripts no Windows | Requer instalar dependências Python no Windows (requests, flask) — mais complexo que o proxy |

## Proxy TCP — Implementação

```python
import socket, threading

LOCAL = ('192.168.144.1', 8188)   # interface WSL virtual
REMOTE = ('127.0.0.1', 8188)      # ComfyUI localhost
BUFFER = 65536

def forward(src, dst):
    while True:
        data = src.recv(BUFFER)
        if not data: break
        dst.sendall(data)

def handle(client, addr):
    server = socket.create_connection(REMOTE)
    t1 = threading.Thread(target=forward, args=(client, server), daemon=True)
    t2 = threading.Thread(target=forward, args=(server, client), daemon=True)
    t1.start(); t2.start()
    t1.join(); t2.join()

listener = socket.socket()
listener.bind(LOCAL)
listener.listen(128)
while True:
    client, addr = listener.accept()
    threading.Thread(target=handle, args=(client, addr), daemon=True).start()
```

O proxy é **genérico TCP** — funciona com HTTP REST API e WebSockets (ambos usados pelo ComfyUI).

## Quando usar esta solução

- ComfyUI corre no Windows host
- Scripts/automação correm no WSL2
- NÃO se quer expor o ComfyUI para a rede local (`--listen 0.0.0.0` inaceitável)
- WSL2 mirrored networking não é uma opção (afeta outros serviços)

## Pitfall: Proxy esquecido

Se o proxy não estiver a correr, os scripts do WSL dão timeout. O `comfyui_config.py` deteta o IP correcto (`192.168.144.1`) mas a ligação falha porque ninguém está a escutar nessa porta.

**Sintoma:**
```
Failed to connect to 192.168.144.1 port 8188 after 3003 ms: Timeout
```

**Fix:** Verificar se a janela do proxy está aberta e ativa no Windows.

## Pitfall: IP do host muda após `wsl --shutdown`

O IP `192.168.144.1` é atribuído pelo Hyper-V virtual switch. Após `wsl --shutdown` + restart, pode mudar (ex: `172.25.0.1`).

**Fix:** `comfyui_config.py` detecta automaticamente o IP atual via `ip route`. O proxy precisa de ser reiniciado com o IP correcto se mudar. Na prática, o IP é estável durante sessões normais — só muda após reboot ou `wsl --shutdown`.
