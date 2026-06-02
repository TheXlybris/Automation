# Hermes Desktop App — Remote Backend Setup

> ⚠️ **CRITICAL WARNING (2026-05-19):** The Hermes Desktop app's "Remote Connection" and "Connect via SSH" modes **do NOT work** with the standard `hermes-agent` CLI package. The desktop app expects a chat API server (WebSocket/PTY endpoint) that the Hermes CLI does **not** expose. The `hermes dashboard` command (port 9119) only serves a **configuration/management dashboard** (FastAPI + React) — it is NOT the chat backend the desktop app requires. This document is preserved for historical reference and for users running a custom Hermes server build. For the standard CLI, use **Local Mode** on Windows instead. See `references/hermes-desktop-windows-local.md` for the working setup.

## Architecture (Intended, But Not Supported by Standard CLI)

```
┌────────────────────┐     SSH tunnel or direct IP     ┌─────────────────────┐
│ Windows Host       │ ─────────────────────────────►│ Headless Linux VM   │
│ (hermes-desktop    │                                 │ (Hermes Agent CLI)  │
│  .exe GUI app)     │                                 │                     │
│                    │     Server URL in desktop app  │ hermes dashboard    │
│                    │     → http://127.0.0.1:9119     │  --host 0.0.0.0     │
│                    │     (via SSH tunnel)             │  --port 9119        │
└────────────────────┘                                 │                     │
                                                     │ LLM provider config │
                                                     │ already set in VM   │
                                                     │ (Ollama Cloud etc.) │
                                                     └─────────────────────┘
```

## Why Remote Mode Fails

The desktop app (fathah/hermes-desktop) presents three connection options on first launch:
1. **Get Started** — installs Hermes CLI locally (Windows)
2. **Connect to Remote Hermes** — expects a URL + API key to a chat API server
3. **Connect via SSH** — expects SSH key-based auth to a machine running the chat API server

The standard `hermes-agent` pip package (v0.14.0) provides:
- `hermes` — interactive CLI chat
- `hermes dashboard` — web dashboard for config/management (port 9119)
- `hermes gateway` — messaging platform gateway (Telegram, Discord, etc.)
- `hermes mcp serve` — MCP server for IDE integration

**None of these expose a chat API that the desktop app can consume.** The dashboard at port 9119 serves `/api/status`, `/api/model/info`, `/api/config`, etc. — all management endpoints. There is no `/chat`, `/stream`, or WebSocket endpoint for real-time conversation. Attempting to connect the desktop app to port 9119 results in a silent failure or "connection refused" because the desktop app cannot find the expected chat protocol.

## What Actually Works

Use the desktop app in **Local Mode** on Windows. It will:
1. Install the Hermes CLI into `%USERPROFILE%\.hermes` on Windows
2. Configure providers (Ollama Cloud, OpenRouter, etc.) directly on Windows
3. Run chat locally with the full desktop GUI

The VM can still be used for:
- Long-running Hermes CLI sessions (headless, via SSH)
- Gateway (Telegram bot, Discord bot)
- Cron jobs
- File processing pipelines

But the desktop app's remote connection modes are **not viable** with the standard CLI.

## Prerequisites (If You Still Want to Try)

1. Hermes Agent installed and configured on the remote VM (`hermes --version` works)
2. SSH access from Windows to the VM (`ssh user@vm-ip` works)
3. VirtualBox shared folders configured if you need file sharing (Screenshots etc.)
4. The `vboxsf` group membership fix: `sudo usermod -aG vboxsf xlybris` then logout/login

## Step 1 — Start the Hermes dashboard server on the VM

The `hermes dashboard` command starts a FastAPI + React web server.

```bash
# Default: localhost only, port 9119
hermes dashboard

# For remote access (needed for desktop app on another machine):
hermes dashboard --host 0.0.0.0 --port 9119 --no-open --insecure
```

**Flags explained:**
- `--host 0.0.0.0` — listen on all interfaces (not just 127.0.0.1)
- `--port 9119` — default port, explicitly stated
- `--no-open` — don't auto-open browser (headless VM has no browser)
- `--insecure` — REQUIRED to bind to non-localhost; acknowledges this exposes API keys on the network

**Verify it's running:**
```bash
ss -tlnp | grep 9119
curl -s http://127.0.0.1:9119/api/model/info
```

## Step 2 — Set up SSH tunnel from Windows (recommended)

On Windows PowerShell / Terminal:
```bash
ssh -L 9119:127.0.0.1:9119 xlybris@192.168.0.188 -N
```

Leave this window open. It redirects your local port 9119 to the VM's port 9119.

**Why use a tunnel?**
- More secure than exposing port 9119 to the LAN
- Works even if the VM firewall blocks port 9119
- No need for `--insecure` on the server if you only tunnel

## Step 3 — Configure the desktop app

On first launch of hermes-desktop, choose **"Connect to Remote Hermes"** (NOT "Get Started" which installs local Hermes CLI).

Fill in:

| Field | Value |
|-------|-------|
| **Server URL** | `http://127.0.0.1:9119` (if using SSH tunnel) OR `http://192.168.0.188:9119` (direct, no tunnel) |
| **API Key (optional)** | Leave EMPTY unless you configured explicit token auth on the server |
| **Connection Name** | Any label, e.g. "VM Linux" |

**Important:** The API Key field is for *server authentication*, NOT for the LLM provider. The LLM provider (Ollama, OpenRouter, etc.) is already configured in the VM's `~/.hermes/config.yaml`. If you put your Ollama key here, it will fail.

## Step 4 — Shared folders for screenshots / file sharing

If you want the VM to access Windows files (or vice versa):

**VirtualBox Settings → Shared Folders:**
- Add `C:\Users\Fil_B\Pictures\Screenshots` → mount point `/media/sf_Screenshots`
- Enable: Auto-mount + Permanent

**Inside VM (one-time fix):**
```bash
sudo usermod -aG vboxsf xlybris
# Then logout and login again for group change to take effect
```

After that, Windows screenshots appear at `/media/sf_Screenshots/` in the VM.

## Port confusion — what NOT to use

| Port | What it is | Why NOT to use for desktop app |
|------|-----------|-------------------------------|
| `8642` | Old/incorrect assumption from prior session | NOT a Hermes port. This was a mistake. |
| `9119` | `hermes dashboard` — **CORRECT** | This is the port. |
| `11434` | Ollama local server | The VM talks to Ollama Cloud via HTTPS, not local port. |

## Troubleshooting

**"Connection refused" in desktop app:**
1. Verify `hermes dashboard` is running on the VM: `ss -tlnp | grep 9119`
2. Verify the tunnel is active (if using one)
3. Try `curl http://127.0.0.1:9119/api/status` from Windows

**"Unauthorized" on API calls:**
- The `/api/config` endpoint requires a session token. Use `/api/model/info` or `/api/status` for health checks instead.

**Desktop app stuck at "Connecting...":**
1. The server might be bound to 127.0.0.1 only. Restart with `--host 0.0.0.0 --insecure`
2. Firewall on VM: `sudo ufw allow 9119/tcp` (if ufw is active)

**SSH tunnel closes unexpectedly:**
- Add `-o ServerAliveInterval=60` to keep the tunnel alive:
  ```bash
  ssh -o ServerAliveInterval=60 -L 9119:127.0.0.1:9119 xlybris@192.168.0.188 -N
  ```

## Related resources

- `references/vm-dedicated-server-setup.md` — Full VM creation + Hermes install recipe
- `references/wsl-setup-pitfalls.md` — Windows/WSL-specific issues
- Hermes Desktop repo: https://github.com/fathah/hermes-desktop
- Hermes Agent docs: https://hermes-agent.nousresearch.com/docs/
