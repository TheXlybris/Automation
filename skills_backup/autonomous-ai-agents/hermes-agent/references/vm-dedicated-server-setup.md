# VM Dedicated Server Setup for Hermes

Full recipe for running Hermes on a dedicated Ubuntu Server VM (VirtualBox) while keeping ComfyUI and GPU workloads on the Windows host.

## Why this architecture

WSL2 introduces friction when Hermes needs stable networking, long-running processes, and direct browser/Docker access. A dedicated VM with bridged networking gives Hermes a real IP on the local network, eliminating proxies, gateway IP guessing, and WSLg GPU crashes.

## Hardware context (this session)

- Host: Windows PC, 32 GB RAM, RTX 4060 Ti 16 GB
- ComfyUI stays on Windows host (GPU passthrough not available in consumer VirtualBox)
- VM: Ubuntu Server 24.04 LTS, 12 GB RAM, 4 vCPUs, 80 GB disk
- Network: Bridged Adapter (VM gets `192.168.0.xxx` from router)

## VirtualBox VM creation

1. New → Linux → Ubuntu (64-bit)
2. RAM: 12288 MB (12 GB)
3. CPUs: 4
4. Disk: 80 GB VDI (dynamically allocated is fine)
5. Settings → Network → Adapter 1 → Bridged Adapter → choose the host's Ethernet NIC
6. Storage → mount Ubuntu Server ISO
7. Start VM

## Ubuntu Server installation

- Language: English (avoids encoding bugs in scripts)
- Keyboard: Portuguese (eliminate dead keys)
- Type: Ubuntu Server (not minimised)
- Network: note the IP assigned (e.g. `192.168.0.188`)
- Storage: Use entire disk → Done → Continue
- Profile: username `xlybris`, server name `hermes-server`
- Enable: [x] Install OpenSSH server
- Snaps: none (install Docker/Hermes manually)

## First login via SSH

From Windows Terminal:
```
ssh xlybris@192.168.0.188
```
Initial password setup was done during install.

## Shared folder (Windows D:\AI_Ecosystem → VM)

VirtualBox Settings → Shared Folders → add `D:\AI_Ecosystem` as permanent + automount.

Inside VM:
```bash
sudo apt install virtualbox-guest-utils
sudo mkdir -p /mnt/ai
sudo mount -t vboxsf ai_ecosystem /mnt/ai
ls /mnt/ai   # confirm contents appear
```

Automount on boot:
```bash
echo 'ai_ecosystem /mnt/ai vboxsf defaults 0 0' | sudo tee -a /etc/fstab
```

## Hermes install when `install.sh` fails

The official `curl .../scripts/install.sh | bash` silently exits if `pip3` is missing. On Ubuntu Server 24.04, pip is NOT installed by default and `python3-pip` must be added first.

```bash
# Step 1: install pip
sudo apt update
sudo apt install -y python3-pip python3-venv

# Step 2: install Hermes via pip (PEP 668: use --break-system-packages on Ubuntu Server 24.04)
pip3 install --break-system-packages hermes-agent

# Step 3: ensure PATH
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# Verify
hermes --version
```

**Post-installation:** After Hermes is installed, install per-platform gateway dependencies. For Telegram:
```bash
PIP_BREAK_SYSTEM_PACKAGES=1 pip install --user python-telegram-bot
```
Then restart the gateway: `systemctl --user restart hermes-gateway` and verify with `tail -20 ~/.hermes/logs/gateway.log` — you should see `INFO gateway.run: Telegram connected` instead of `WARNING: python-telegram-bot not installed`.

Pitfall — PEP 668 even for `--user`:

## Hermes setup on VM

Run interactively:
```bash
hermes setup
```
Typical choices for this architecture:
- Model: `qwen3.5:35b-a3b` via `ollama-cloud` (same API key as WSL)
- Terminal backend: `local`
- Gateway working directory: `.` (or `/mnt/ai` for project access)
- Sudo support: `y` (convenient for a single-user VM)
- Telegram: same bot token and config as WSL

After setup:
```bash
hermes config env-path   # shows ~/.hermes/.env
hermes config path        # shows ~/.hermes/config.yaml
```

## Skills installation

Built-in skills install via CLI (none are present by default on a fresh pip install):
```bash
hermes skills list
hermes skills install autonomous-ai-agents
hermes skills install creative
hermes skills install data-science
hermes skills install devops
hermes skills install dogfood
hermes skills install email
hermes skills install gaming
hermes skills install github
hermes skills install media
hermes skills install mlops
hermes skills install mlops_models
hermes skills install note-taking
hermes skills install productivity
hermes skills install red-teaming
hermes skills install research
hermes skills install smart-home
hermes skills install social-media
hermes skills install software-development
hermes skills install yuanbao
```

**Pitfall:** Custom skills (user-created SKILL.md files) and custom Python tools (e.g. `video_analyze_ollama.py`, `mixture_of_agents_ollama.py`) are NOT in the skills hub. They must be recreated or copied from the old WSL installation. The paths are:
- Skills: `~/.hermes/skills/`
- Tools: `~/.hermes/plugins/` ← **never** put them in `~/.hermes/hermes-agent/tools/` (destroyed by `hermes update`)

## Dashboards / Flask servers from VM → Windows browser

Any Flask dashboard running on the VM (e.g. storyboard pipeline on port 5010, AgentGUI on port 5020) must bind to `0.0.0.0` so the Windows host can reach it:
```python
app.run(host='0.0.0.0', port=5010)
```

Access from Windows Chrome:
```
http://192.168.0.188:5010
http://192.168.0.188:5020
```

## ComfyUI access from VM → Windows

ComfyUI stays on Windows host. From VM scripts, point to the Windows host IP (not `127.0.0.1`):
```python
COMFYUI_URL = "http://192.168.0.100:8188"   # Windows host IP on LAN
```

If the Windows host IP is dynamic, either:
1. Set a static IP on Windows, or
2. Use the technique from `references/wsl-setup-pitfalls.md` Section 7 (Ollama/ComfyUI Windows host access via gateway IP) and adapt the proxy script to forward `0.0.0.0:8188` on the VM to Windows.

## No GUI = no local browser inside VM

Ubuntu Server has no desktop environment. Browser-dependent Hermes tools (Playwright, Chromium) will report "Browser engine not installed" unless you:
- Install Chrome for Linux inside the VM (`wget` the `.deb` from Google), OR
- Use CDP remote debugging pointing to a browser running on Windows, OR
- Accept that browser tools run headlessly/in-memory via Playwright's bundled Chromium.

For most server-side pipelines (ComfyUI API calls, ffmpeg, Python scripts) this is irrelevant.

## File delivery

User created outputs on the VM can be written directly to `/mnt/ai/...` and appear instantly on `D:\AI_Ecosystem\...` in Windows. No SCP required for project files.

## Checklist before calling the VM production-ready

- [ ] SSH working from Windows Terminal
- [ ] `/mnt/ai` mounts and shows D:\ contents
- [ ] `hermes --version` returns version
- [ ] `hermes chat --once "olá"` gets a model response (no 404 / empty model)
- [ ] All required built-in skills installed (`hermes skills list` shows them)
- [ ] Custom skills/tools recreated or copied from WSL
- [ ] Port 5010/5020 reachable from Windows (`curl http://<vm-ip>:5010` from Windows)
- [ ] ComfyUI API callable from VM (test with a curl to Windows host IP)
