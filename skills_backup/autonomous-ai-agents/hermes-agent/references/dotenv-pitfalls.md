# `.env` File Pitfalls for Hermes Gateway

Common mistakes in `~/.hermes/.env` that prevent the gateway from starting or the Telegram bot from working.

## 1. Trailing `#` is NOT a comment

The parser treats `#` as data when it directly follows the value with no whitespace.

```
# BROKEN — causes TEMPFAIL on startup
telegram_home_channel=7777720835#

# CORRECT
TELEGRAM_HOME_CHANNEL=7777720835
```

**Gateway symptom:**
```
ValueError: invalid literal for int() with base 10: '7777720835#'
hermes-gateway.service: Failed with result 'exit-code' (status 75/TEMPFAIL)
```

Root cause: the gateway reads the value as `7777720835#`, then `int(chat_id)` fails.

**Other examples that silently corrupt values:**
- `TELEGRAM_BOT_TOKEN=1234:abc#comment` → token becomes `1234:abc#comment`
- `OLLAMA_API_KEY=sk-proj#key` → key becomes `sk-proj#key`

**Fix:** ensure there is at least one space between the value and any inline comment, or put comments on their own lines.

## 2. Variables scattered at the bottom

Placing variables outside their logical section is valid but makes debugging harder. Group them under their section header.

## 3. Commented-out required variables

For Telegram, three must be active (no `#`):
- `TELEGRAM_BOT_TOKEN=<token>`
- `TELEGRAM_ALLOWED_USERS=<user_id>`
- `TELEGRAM_HOME_CHANNEL=<id>`

## 4. `read_file` masking can mislead diagnosis

The `read_file` tool masks sensitive data (tokens, passwords) with `***` in its output. This is a display artifact — the actual bytes on disk are correct. **Never tell the user their token is "masked" or incomplete based on `read_file` output alone.** If the user confirms a line is correct, trust them. To verify the exact bytes on disk, use terminal `grep` instead:
```bash
grep '^TELEGRAM_BOT_TOKEN' ~/.hermes/.env
```

## 5. Systemd gateway service does NOT read `.env`

When the gateway runs as a systemd user service (`systemctl --user start hermes-gateway`), it does **not** auto-load `~/.hermes/.env`. Only the `[Service]` section of the systemd unit file controls the environment.

**Symptom:**
- `TAVILY_API_KEY` present in `~/.hermes/.env` but gateway returns `No web search provider configured`
- `check-gateway-env.py` reports `TAVILY_API_KEY MISSING`

**Fix:**
```bash
# Add EnvironmentFile to the systemd unit
sed -i '/Environment="HERMES_HOME=/a EnvironmentFile=-/home/xlybris/.hermes/.env' \
    ~/.config/systemd/user/hermes-gateway.service
systemctl --user daemon-reload
systemctl --user restart hermes-gateway
```

Note: For the interactive `hermes` CLI to see the keys too, either:
- Add `set -a; source ~/.hermes/.env; set +a` to `~/.bashrc`, or
- Export the variable before running `hermes`
- Or create a shell alias: `alias hermes='set -a && source ~/.hermes/.env && set +a && /home/xlybris/.local/bin/hermes'`

**Pitfall:** The gateway (Telegram/Discord/Cron) can have the key while the interactive TUI does not, if the TUI is started from a shell that never ran `source ~/.hermes/.env`. Always verify via the specific process's environment, not just checking `.env` on disk:
```bash
# Check the TUI / hermes chat process specifically
hermes_pid=$(pgrep -f "hermes.*chat" | head -1)
cat /proc/$hermes_pid/environ 2>/dev/null | tr '\0' '\n' | grep TAVILY || echo "MISSING in TUI process"
```

---

## Quick TEMPFAIL diagnosis

```bash
# 1. Check HOME_CHANNEL for trailing #
grep '^TELEGRAM_HOME_CHANNEL' ~/.hermes/.env

# 2. Check gateway logs
journalctl --user -u hermes-gateway --since "5 minutes ago" | grep -i "tempfail\|error"

# 3. Verify all three TELEGRAM_ vars are active
grep -E '^TELEGRAM_' ~/.hermes/.env
```
