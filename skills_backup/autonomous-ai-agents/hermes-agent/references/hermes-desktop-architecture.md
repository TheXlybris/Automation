# Hermes Desktop App Architecture Notes

Session: 2026-05-19 — User: Fil_B

## Core Discovery

The `hermes-desktop` Electron app has 3 modes: Local, Remote, SSH. Only **Local** works reliably with the standard Hermes CLI.

### Why Remote / SSH Don't Work Out-of-the-Box

The desktop app expects the backend to expose:
- PTY (pseudo-terminal) over WebSocket for interactive chat
- Session management endpoints
- Tool execution streaming

The standard `hermes` CLI is a single-session terminal app. It does NOT expose these endpoints persistently.

What exists:
| Component | Port | Purpose | Desktop uses it? |
|-----------|------|---------|-------------------|
| `hermes dashboard` | 9119 | FastAPI management UI | No |
| Gateway `api_server` | 8642 | OpenAI-compatible API | Partially (for external frontends, not native desktop chat) |
| `hermes acp` | varies | IDE protocol | No |

### Desktop App Source Reality

`src/main/hermes.ts` shows all modes eventually resolve to `http://127.0.0.1:8642`. The backend must expose the desktop app's expected API surface.

### SSH Tunnel Misconception

"Connect via SSH" spawns `ssh -N -L <local_port>:127.0.0.1:8642` and expects a Hermes backend on 8642 inside the remote. The standard CLI does NOT auto-start this.

### Correct Approach: Local + Migration

For a user wanting desktop app on Windows with same state as VM:

1. Install desktop app on Windows, choose **Local**
2. Stop the app
3. Copy `~/.hermes` from VM to `%USERPROFILE%\.hermes`
   - Preserves: config.yaml, .env, sessions/, skills/, memories/, state.db
4. Restart desktop app

This is the only reliable path.

### Migration Steps

```bash
# On Linux VM:
cd ~
tar czf hermes_backup.tar.gz .hermes/
# Transfer to Windows, extract to C:\Users\USERNAME\.hermes\
```
