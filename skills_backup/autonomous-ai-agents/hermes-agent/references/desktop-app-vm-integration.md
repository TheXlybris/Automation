# Hermes Desktop App + Remote VM Integration

Session-proven guide for connecting the Hermes Desktop app (fathah/hermes-desktop)
to a Hermes CLI instance running inside a VirtualBox Linux VM.

## What the desktop app actually expects

The desktop app has **three connection modes** on first launch:

1. **Local** — installs/runs Hermes CLI on the same machine (Windows). This is
the primary, best-supported path.
2. **Remote URL** — expects a Hermes **API server** at a URL, not just the CLI.
3. **SSH Tunnel** — creates an SSH tunnel and also expects an API server on the
remote end.

Pitfall: the standard `hermes` CLI interactive session does **not** expose a
chat API by default. The dashboard web server (`hermes dashboard`, port 9119)
is a management UI (config, sessions, logs) — it does not serve chat endpoints.

## Architecture on the VM side

| Component | Port | Purpose | Desktop app connects? |
|-----------|------|---------|----------------------|
| `hermes dashboard` | 9119 | Web UI for management | No — not a chat API |
| `hermes gateway` with `api_server` platform | 8642 | OpenAI-compatible API | Yes — this is what remote/SSH modes need |
| `hermes chat` (interactive TUI) | none | Terminal chat | No — no network endpoint |

To make the VM accessible from the desktop app you must either:

- Run the Hermes **gateway** with the `api_server` platform enabled in
  `config.yaml` under `platforms.api_server`, binding to `0.0.0.0:8642`.
- Or simply accept that the desktop app is designed for **local mode** and
  copy the `~/.hermes` folder to the Windows host so both instances share state.

## Recommended practical approach

Because the VM-to-desktop API server path is fragile (needs passwordless SSH
or exposed ports, plus a running gateway), the pragmatic workflow is:

1. **Run desktop app in Local mode** on Windows.
2. **Copy `~/.hermes` from the VM** to `%USERPROFILE%\.hermes` on Windows
   periodically (or vice-versa) so sessions, skills, memory, and config stay
   in sync.
3. Use **Obsidian vault** or a shared markdown folder as a lightweight
   knowledge bridge for high-level context the other instance should read on
   startup (see `obsidian` skill).

## VirtualBox shared-folder permission fix

When sharing a Windows folder into a Linux VM, the guest user must be in the
`vboxsf` group:

```bash
sudo usermod -a -G vboxsf <username>
# Logout/login required for group change to take effect
```

Without this, the shared mount at `/media/sf_<FolderName>` is inaccessible.

## Ollama Cloud configuration in desktop app

When using a **cloud provider** via the desktop app's Local mode:

- Select **Local → Ollama** (or the relevant provider pill)
- **Base URL**: must be the **cloud endpoint**, not localhost.
  - Example for Ollama Cloud: `https://ollama.com/v1`
  - Not `http://localhost:11434/v1` (that is local Ollama)
- **API Key**: the provider's cloud key (e.g. Ollama Cloud API key)
- **Model Name**: the exact model identifier (e.g. `kimi-k2.6`)

## SSH mode requirements

The desktop app's SSH mode requires:
- Passwordless SSH (`ssh user@host` works without prompt)
- An **SSH private key** configured on the Windows side
- The remote Hermes API server listening on the port specified in
  "Remote Hermes Port" (default 8642)

If SSH still asks for a password, configure key-based auth first or use the
manual tunnel method (`ssh -L 8642:127.0.0.1:8642 user@host -N`) and then
connect the desktop app via the Remote URL mode to `http://127.0.0.1:8642`.
