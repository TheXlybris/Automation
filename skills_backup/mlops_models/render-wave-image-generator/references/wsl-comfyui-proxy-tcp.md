# WSL → ComfyUI TCP Proxy (Secure Alternative to --listen 0.0.0.0)

**Problem:** ComfyUI runs on Windows 127.0.0.1:8188. WSL2 scripts need to reach it. User refused `--listen 0.0.0.0` for security. `netsh portproxy` does NOT work with WSL2 NAT (Hyper-V virtual switch limitation). The rule shows as active but WSL requests timeout.

**Solution: Python TCP proxy** that listens on the WSL virtual gateway IP (`192.168.144.1`) and forwards to `127.0.0.1:8188`.
- `192.168.144.1` is a Hyper-V internal virtual network IP — no external PC can reach it.
- ComfyUI stays on localhost. Windows browser uses `127.0.0.1:8188` normally.
- WSL uses `192.168.144.1:8188` → proxy → ComfyUI.

**Files:**
- `D:\AI_Ecosystem\08_Config\wsl_comfyui_proxy.py` — proxy script
- `D:\AI_Ecosystem\08_Config\start_wsl_proxy.bat` — launcher

**Run:**
1. Windows: `python wsl_comfyui_proxy.py` (leave window open)
2. WSL: `curl http://192.168.144.1:8188/system_stats` → JSON

**Auto-detection in scripts:**
```python
import os, subprocess
def get_host_ip() -> str:
    try:
        result = subprocess.run(["ip","route"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if line.startswith("default"):
                parts = line.split()
                if "via" in parts: return parts[parts.index("via") + 1]
    except: pass
    return os.environ.get("COMFYUI_HOST_IP", "127.0.0.1")
```
This returns 192.168.144.1 automatically. Scripts import from `comfyui_config.py` shared module.

**Why proxy > alternatives:**
- `--listen 0.0.0.0`: exposes to LAN (user rejected)
- `--listen 192.168.144.1`: ComfyUI no longer works on 127.0.0.1 (Windows browser breaks)
- *This is the only option that keeps ComfyUI on localhost while letting WSL in.*

**Firewall:** If proxy is running but curl still fails, Windows firewall may be blocking inbound TCP 8188 on the Hyper-V interface. Add an allow rule for python.exe on that port.

**Validated:** 2026-05-14. `netsh portproxy` confirmed non-functional.
