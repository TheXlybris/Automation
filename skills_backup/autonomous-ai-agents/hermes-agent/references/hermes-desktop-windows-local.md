# Hermes Desktop App — Windows Local Mode Setup

Working setup for running the Hermes Desktop app (fathah/hermes-desktop) on Windows with a local Hermes CLI backend. This is the only mode that works reliably with the standard `hermes-agent` pip package.

## Why Local Mode Is the Only Viable Option

The Hermes Desktop app offers three connection modes on first launch:
1. **Get Started** (Local) — installs Hermes CLI on Windows ✅ WORKS
2. **Connect to Remote Hermes** — expects a chat API server ❌ NOT SUPPORTED by standard CLI
3. **Connect via SSH** — expects SSH key auth + chat API server ❌ NOT SUPPORTED by standard CLI

The standard `hermes-agent` CLI (v0.14.0) does not expose a WebSocket/PTY chat API. The `hermes dashboard` command (port 9119) serves a management dashboard (config, sessions, logs) — not a chat backend. Attempting remote/SSH connection results in silent failure.

## Installation Steps

### 1. Download the installer

From https://github.com/fathah/hermes-desktop/releases/
- Windows: `.exe` (NSIS installer)
- The installer is not code-signed — click "More info" → "Run anyway" on SmartScreen

### 2. Run the installer

Double-click the `.exe`. The app installs to a standard Windows location.

### 3. First Launch — Choose "Get Started"

On the welcome screen, select **"Get Started"** (NOT "Connect to Remote Hermes" or "Connect via SSH").

This will:
- Download and install the Hermes CLI into `%USERPROFILE%\.hermes`
- Run dependency resolution (Git, uv, Python 3.11+)
- Present the provider setup wizard

### 4. Provider Setup

During first-run setup, the app prompts for LLM provider configuration:

**For Ollama Cloud:**
- Provider: `ollama-cloud`
- Base URL: `https://ollama.com/v1`
- API Key: your Ollama Cloud key (from https://ollama.com/settings)
- Model: e.g. `kimi-k2.6`, `qwen3.5:35b-a3b`

**For other providers:**
- OpenRouter, Anthropic, OpenAI, Google Gemini, xAI Grok, etc.
- Follow the in-app prompts for each provider's API key

### 5. Verification

After setup completes:
1. The desktop app opens the chat interface
2. Type a test message — the model should respond
3. Check Settings → Model to verify the provider and model are correct

## Where Things Are Installed

| Location | Purpose |
|----------|---------|
| `%USERPROFILE%\.hermes` | Hermes CLI, config, sessions, skills |
| `%USERPROFILE%\.hermes\config.yaml` | Main configuration |
| `%USERPROFILE%\.hermes\.env` | API keys and secrets |
| Desktop app install dir | Electron app, auto-updater |

## If You Previously Chose the Wrong Option

If you accidentally selected "Connect to Remote Hermes" or "Connect via SSH" on first launch:

1. **Close the desktop app**
2. **Delete local Hermes data** (if any was created):
   ```powershell
   # In PowerShell
   Remove-Item -Recurse -Force "$env:USERPROFILE\.hermes"
   ```
3. **Uninstall the desktop app** via Windows Settings → Apps
4. **Reinstall** the desktop app from the `.exe`
5. **Choose "Get Started"** this time

## Coexisting with a VM-based Hermes

You can run Hermes in multiple places simultaneously:

| Location | Use Case |
|----------|----------|
| **Windows (desktop app)** | Daily chat, quick tasks, GUI comfort |
| **VM (SSH terminal)** | Long-running sessions, cron jobs, gateway |
| **VM (dashboard)** | Remote management, config tweaks via browser |

They are independent — each has its own `~/.hermes` directory and config. The desktop app's Hermes CLI lives in `%USERPROFILE%\.hermes` on Windows; the VM's lives in `/home/xlybris/.hermes`.

## Updating

The desktop app has an auto-updater (via `electron-updater`). When a new release is available, a notification appears in the app.

To update the underlying Hermes CLI:
- The desktop app manages this automatically
- Or run `hermes update` from a terminal on Windows (if Hermes CLI is in PATH)

## Troubleshooting

**"Hermes not installed" error in desktop app:**
- The app tries to auto-install on first launch. If it fails:
  1. Install Python 3.11+ manually from python.org
  2. Install Git from git-scm.com
  3. Re-run the desktop app setup

**Model returns empty responses:**
- Check Settings → Model → verify provider and API key
- Try `hermes doctor` in a terminal to diagnose

**Desktop app won't start after wrong initial choice:**
- Fully uninstall (app + `%USERPROFILE%\.hermes`), then reinstall

## Related Resources

- `references/hermes-desktop-remote-backend.md` — Investigation into why remote mode does not work
- `references/vm-dedicated-server-setup.md` — Full VM creation + Hermes install recipe
- Hermes Desktop repo: https://github.com/fathah/hermes-desktop
- Hermes Agent docs: https://hermes-agent.nousresearch.com/docs/
