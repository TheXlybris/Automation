# TUI / Interactive CLI Environment Loading Diagnosis

> Session: 2026-05-25
> Context: "No web search provider configured" persists in TUI even after gateway env fix.

## Symptom

- `web_search` fails with `No web search provider configured` in the TUI / `hermes chat`
- Gateway (Telegram) works fine after `EnvironmentFile=%h/.hermes/.env`
- The user did `/exit` then `hermes chat` — error persists

## Root cause

The `hermes chat` interactive CLI process **does not inherit** the `.env` variables automatically. The `hermes-cli` entrypoint calls `load_hermes_dotenv()`, but **if the shell that launched `hermes chat` never had `TAVILY_API_KEY` exported**, the Python `os.getenv` inside the agent loop still returns `None`.

This can happen when:
1. The `.bashrc` does not contain `source ~/.hermes/.env`
2. The user opens a new terminal/SSH session that does not source `.env`
3. The `hermes` command is an alias or wrapper that bypasses shell env

## Quick diagnosis

```bash
# Check if the current shell has the key
env | grep TAVILY

# If NOT present, source it first
set -a && source ~/.hermes/.env && set +a

# Verify
env | grep TAVILY

# Then launch hermes
hermes chat
# Inside TUI, type: search teste
```

If it works after `source`, the fix is permanent:
```bash
echo "source ~/.hermes/.env" >> ~/.bashrc
```

## Process-level verification

```bash
# Find the PID of the active hermes chat process
PID=$(pgrep -f "hermes.*chat" | head -1)
# Inspect its environment
xargs -0 -n1 < /proc/$PID/environ | grep TAVILY
```

If this returns **nothing**, the key is not in the process env. Source `.env` and restart `hermes chat`.

## Permanent fixes

### Fix A: `.bashrc` alias wrapper (recommended)
```bash
cat >> ~/.bashrc <> 'EOF'
alias hermes='set -a && source ~/.hermes/.env && set +a && /home/xlybris/.local/bin/hermes'
EOF
source ~/.bashrc
```

### Fix B: Shell function (more robust, supports args)
```bash
cat >> ~/.bashrc <> 'EOF'
hermes() {
    set -a
    source ~/.hermes/.env 2>/dev/null || true
    set +a
    /home/xlybris/.local/bin/hermes "$@"
}
EOF
source ~/.bashrc
```

### Fix C: `~/.profile` or `~/.bash_profile` (for login shells)
```bash
echo "source ~/.hermes/.env" >> ~/.profile
```

**Note:** Use Fix A or B only if you are fine replacing the native `hermes` command. Otherwise, just ensure `~/.bashrc` has a `source ~/.hermes/.env` line and that you restart your terminal session.

## Gateway vs. TUI env split

| Process | `.env` loaded by | How to ensure vars are present |
|---|---|---|
| Gateway (systemd) | `EnvironmentFile=...` in unit file | Edit unit + `daemon-reload` + `restart` |
| TUI (`hermes chat`) | `hermes_cli.env_loader` (called once at startup) | Ensure shell env has vars before launching, or source `.env` in shell init |
| `execute_code` | Python `load_hermes_dotenv()` succeeds | Works because it explicitly calls `load_dotenv()` |
| Cron jobs | Inherits from gateway env | Works if gateway unit has `EnvironmentFile` |

The key insight: **TUI and gateway use separate process trees.** Fixing one does not fix the other.
