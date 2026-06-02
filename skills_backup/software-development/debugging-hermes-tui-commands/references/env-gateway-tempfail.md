# Gateway TEMPFAIL Debugging for Slash Commands

## Symptom

Gateway service exits immediately with `status=75/TEMPFAIL`. Slash commands
worked previously but now the TUI or Telegram bot won't start.

## Most Common Cause: `.env` Malformation

### Trailing `#` character

The `.env` parser treats `#` as literal data when directly appended to a
value with no whitespace before it:

```bash
# BROKEN — gateway reads the channel ID as 7777720835# and fails int()
TELEGRAM_HOME_CHANNEL=7777720835#

# CORRECT
TELEGRAM_HOME_CHANNEL=7777720835
```

### Why this happens

The user edits the `.env` file and removes the `#` comment marker from a line
but leaves a trailing `#` at the end of the value. Or, the `read_file` tool
shows lines in a way that makes it hard to see the exact boundary between the
value and any trailing characters.

### How to verify

```bash
# grep shows exact bytes on disk (read_file may mask with ***)
grep '^TELEGRAM_HOME_CHANNEL' ~/.hermes/.env

# Check all TELEGRAM_ vars
grep -E '^TELEGRAM_' ~/.hermes/.env

# Check gateway logs for the exact error
journalctl --user -u hermes-gateway --since "5 minutes ago"
```

### Fix

1. Edit `~/.hermes/.env`
2. Remove any trailing `#` from the value
3. Restart the gateway: `hermes gateway restart`

## Second Most Common Cause: Required Variables Commented Out

For Telegram integration, all three must be **active** (no leading `#`):
- `TELEGRAM_BOT_TOKEN=<token>`
- `TELEGRAM_ALLOWED_USERS=<user_id>`
- `TELEGRAM_HOME_CHANNEL=<chat_id>`

If any is commented out, the gateway may start but the Telegram bot will not
function.

## Less Common Causes

- Syntax error in `config.yaml` (e.g., `api_key: ''` when `.env` has the key)
- Missing dependency in the gateway process (`websockets`, etc.)
- Port conflict on the Telegram webhook port (if using webhook mode)

## Cross-Reference

See also `hermes-agent/references/dotenv-pitfalls.md` for the full `.env` guide.
