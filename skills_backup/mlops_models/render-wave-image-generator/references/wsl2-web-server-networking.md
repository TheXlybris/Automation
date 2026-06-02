# WSL2 NAT Networking — Exposing Web Servers to Windows Host

WSL2 uses NAT (not bridged networking like WSL1). The WSL IP (e.g. `192.168.144.17`) is NOT directly accessible from the Windows host. This breaks the intuition that `--host 0.0.0.0` on a WSL server makes it available to Windows.

## Symptoms
- `curl http://localhost:5000` works inside WSL
- `curl http://127.0.0.1:5000` works inside WSL  
- Chrome on Windows at `http://192.168.144.17:5000` fails (connection refused or timeout)
- Chrome on Windows at `http://localhost:5000` may or may not work depending on WSL version/settings

## Why
WSL2 runs in a virtual NIC with its own subnet. The Windows host sees WSL through a virtual switch with NAT. WSL `localhost` is WSL-local only. Windows `localhost` is Windows-local only. They are different loopback interfaces.

## Solutions

### Option A — Browser inside WSL (simplest, zero config)
Requires WSLg (GUI support). Works on Windows 11 and recent Windows 10.
```bash
google-chrome http://localhost:5000
# or
firefox http://localhost:5000
```

### Option B — Windows port proxy (permanent, requires admin PowerShell)
```powershell
# Run in Windows PowerShell as Administrator
netsh interface portproxy add v4tov4 listenport=5000 listenaddress=0.0.0.0 connectport=5000 connectaddress=192.168.144.17
netsh advfirewall firewall add rule name="WSL Flask" dir=in action=allow protocol=tcp localport=5000
```
Then access `http://localhost:5000` from Windows Chrome.

To remove later:
```powershell
netsh interface portproxy delete v4tov4 listenport=5000 listenaddress=0.0.0.0
netsh advfirewall firewall delete rule name="WSL Flask"
```

### Option C — Run the server on Windows instead of WSL
Install Python/Flask on Windows Python and run `server.py` there. Then `localhost:5000` works natively. The script can still call ComfyUI at `192.168.144.1:8188` since that's the Windows host IP from WSL perspective.

### Option D — `.wslconfig` bridge mode (advanced, experimental)
Can configure WSL2 to use mirrored networking mode where `localhost` is shared between Windows and WSL:
```ini
# C:\Users\<username>\.wslconfig
[wsl2]
networkingMode=mirrored
localhostForwarding=true
```
Requires WSL restart: `wsl --shutdown`

## Diagnosis checklist
1. `curl http://localhost:5000` inside WSL — server running?
2. `ss -tlnp | grep 5000` — port actually listening?
3. `ip addr show eth0` — what is the WSL IP today?
4. Try `curl http://192.168.144.17:5000` from Windows PowerShell — does it timeout or refuse?
5. Check Windows Defender / firewall rules for port 5000

## Relevant for THE RENDER WAVE
The Flask UI server (`ui/server.py`) runs in WSL by default. The user typically opens Chrome on Windows. Option B (portproxy) is the most reliable for repeated use. Option A is fastest for a quick test if WSLg is available.
