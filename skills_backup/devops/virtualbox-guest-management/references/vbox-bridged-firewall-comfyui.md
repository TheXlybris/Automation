# VirtualBox Bridged + Windows Firewall — VM-to-Host ComfyUI Access

## Context
Session: 2026-06-01  
Problem: Hermes agent (VM Ubuntu) needs REST API access to ComfyUI running on Windows host.  
User constraint: NAT breaks SSH access; user needs to keep Bridged mode to maintain SSH to VM.  
User constraint: User does NOT want ComfyUI exposed to all network interfaces (`0.0.0.0`); must be restricted.

## What Was Tried and Failed

### Option A — Port Forwarding with NAT
- Changed VM network adapter to NAT
- Added port forwarding rule in VirtualBox: Host 8188 → Guest 8188
- SSH from Windows PowerShell to VM timed out (`Connection timed out`)
- Reason: NAT gives VM a private IP (10.0.2.15); the bridged IP (192.168.0.188) disappears
- User reverted to Bridged immediately to restore SSH

### Option B — NAT + SSH Port Forward
- Would require forwarding BOTH port 22 (SSH) AND port 8188 (ComfyUI)
- Complicated and fragile; user rejected

## What Worked — Option C: Bridged + Windows Firewall Rule (Restricted IP)

### On Windows Host

1. **Find Windows IP** (for `--listen`):
   ```powershell
   ipconfig | findstr "IPv4"
   ```
   Result: `192.168.0.187`

2. **ComfyUI launch file** (`run_nvidia_gpu.bat` or equivalent):
   ```
   .\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --listen 192.168.0.187 --port 8188
   ```
   This binds ComfyUI ONLY to the bridged interface, NOT to all interfaces.

3. **Windows Firewall — GUI steps:**
   - Start → search "Firewall do Windows com Segurança Avançada"
   - Left pane: **Regras de Entrada**
   - Right pane: **Nova Regra...**
   - Rule type: **Personalizada**
   - Program: **Todos os programas**
   - Protocol: **TCP**, Local port: **8188**
   - **IP addresses — CRITICAL:**
     - Local IP address: **IP do Windows** (e.g. `192.168.0.187`)
     - Remote IP address: **These IP addresses** → Add → `192.168.0.188` (VM IP)
   - Action: **Permitir a ligação**
   - Profile: **Privado** only (disable Public/Domain if desired)
   - Name: `ComfyUI-VM-Only`

### Verification from VM

```bash
curl -s http://192.168.0.187:8188/system_stats
```
Returns ComfyUI system stats JSON. Confirmed working.

## Key Parameters Recovered

| Parameter | Value |
|---|---|
| Windows IP | `192.168.0.187` |
| VM IP | `192.168.0.188` |
| Gateway | `192.168.0.1` |
| ComfyUI port | `8188` |
| Firewall rule | `ComfyUI-VM-Only` (TCP 8188, Remote: 192.168.0.188) |

## Security Properties

- ComfyUI only listens on `192.168.0.187` (not `0.0.0.0`)
- Firewall only allows port 8188 from `192.168.0.188`
- No other device on the LAN can reach ComfyUI
- VM has full SSH access (bridged)

## Pitfalls

1. **Must restart ComfyUI** after changing `--listen` flag — not retroactive
2. **Windows IP must be static or DHCP-reserved** — if it changes, firewall rule and `--listen` break
3. **Do NOT use `0.0.0.0`** if user wants restriction — but `--listen <specific_ip>` + firewall is tighter
4. **Firewall GUI in Portuguese** — exact menu names depend on Windows display language
5. **Bridged adapter must be the correct physical NIC** — VirtualBox must select the active network adapter (Wi-Fi or Ethernet)

## Related

- [[../../comfyui/references/ace-step-audio.md]] — ACE Step audio generation via this same network path
- [[../vboxsf-debug-session.md]] — Previous vboxsf debugging session
