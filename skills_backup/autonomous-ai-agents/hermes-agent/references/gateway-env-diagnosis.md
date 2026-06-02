# Gateway Environment Diagnosis

> Session: 2026-05-25 — Troubleshooting "No web search provider configured" despite TAVILY_API_KEY existing in ~/.hermes/.env

## Symptom

`web_search` returns instantly:
```
No web search provider configured. Run `hermes tools` to set one up.
```

But `config.yaml` has:
```yaml
web:
  backend: tavily
  search_backend: tavily
  extract_backend: tavily
```

And `~/.hermes/.env` contains `TAVILY_API_KEY=tvly-...`.

## Root causes (in order of likelihood)

### 1. Gateway process not reading `.env`

When the gateway runs under `systemd --user`, the unit file **must** contain:
```ini
[Service]
EnvironmentFile=%h/.hermes/.env
```

Without this, the gateway Python process has **zero** env vars from `.env`, no matter how correct the file is.

**Fix:**
```bash
nano ~/.config/systemd/user/hermes-gateway.service
# Add inside [Service]: EnvironmentFile=%h/.hermes/.env
systemctl --user daemon-reload
systemctl --user restart hermes-gateway
```

### 2. `.env` contains stale SSH vars that override `TERMINAL_ENV=local`

Even after `hermes setup` sets `terminal.backend: local`, if `.env` still has old SSH entries **above** `TERMINAL_ENV=local`, some code paths may read the SSH vars first:
```bash
TERMINAL_SSH_HOST=192.168.0.188
TERMINAL_SSH_USER=xlybris
TERMINAL_SSH_KEY=/home/xlybris/.ssh/id_rsa
TERMINAL_ENV=local
```

**Fix:** Comment or delete all `TERMINAL_SSH_*` lines:
```bash
# TERMINAL_SSH_HOST=192.168.0.188
# TERMINAL_SSH_USER=xlybris
# TERMINAL_SSH_KEY=/home/xlybris/.ssh/id_rsa
TERMINAL_ENV=local
```

Restart gateway after editing `.env`.

### 3. API key actually invalid (masked as "no provider")

The Tavily client raises `MissingAPIKeyError` or a network/auth error on init. The Hermes tool wrapper catches this and falls back to the generic message "No web search provider configured".

**Fix:** Test the key directly:
```bash
source ~/.hermes/.env
curl -s "https://api.tavily.com/search" \
  -H "Content-Type: application/json" \
  -d "{\"api_key\":\"$TAVILY_API_KEY\",\"query\":\"test\",\"search_depth\":\"basic\",\"max_results\":1}"
```

Expected: JSON with `results` array or `answer` field.
Unexpected: `{"error":"Invalid API key"}` or `{"detail":...}` → regenerate key at https://app.tavily.com/home.

## Verification commands

### Check if gateway process actually has the env var
```bash
# Get PID
GWPID=$(systemctl --user show hermes-gateway --property=MainPID --value)

# Read environment (trick: replace null bytes with newlines)
cat /proc/$GWPID/environ | tr '\0' '\n' | grep -i tavily
```

If this returns **nothing**, the env var is not reaching the process. Go to Fix #1.

If it returns the key but web_search still fails, go to Fix #3 (key invalid).

### Check if the TUI process has the env var
The interactive `hermes chat` TUI runs in a **separate process tree** from the gateway. Even if the gateway has the key, the TUI may not:
```bash
TUIPID=$(pgrep -f "hermes.*chat" | head -1)
cat /proc/$TUIPID/environ 2>/dev/null | tr '\0' '\n' | grep TAVILY || echo "MISSING in TUI process"
```

If missing in the TUI but not in the gateway, see `references/tui-env-loading-diagnosis.md`.

### Check gateway restart time vs file edit time
```bash
systemctl --user status hermes-gateway | grep "Active:"
stat ~/.config/systemd/user/hermes-gateway.service | grep Modify
```

If the gateway started **before** the file was modified, `daemon-reload` was not enough or restart was skipped.

## Pitfall: `hermes config get` does not exist

The Hermes CLI does **not** have `hermes config get`. Valid subcommands are:
```
show, edit, set, path, env-path, check, migrate
```

Use `hermes config show` or `hermes config path` instead.
