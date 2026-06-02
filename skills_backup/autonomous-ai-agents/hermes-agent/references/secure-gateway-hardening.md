# Secure Gateway Hardening Guide

> Session-specific detail extracted from a security-hardening session for a Hermes Agent + Telegram bot setup on WSL2 + Tailscale.
> Covers gateway-level access control, Docker sidecar port exposure, and Tailscale mesh ACLs.

## Scope

This guide addresses the specific scenario where:
- Hermes Agent runs as a Telegram bot via systemd service
- WSL2 is the runtime environment (Windows host + Linux subsystem)
- Tailscale provides private mesh networking
- Multiple AI tools run as Docker containers alongside Hermes

## Hardening Layers

### Layer 1 — Gateway Access Control (CRITICAL)

**Risk:** If `TELEGRAM_ALLOWED_USERS` is unset or commented, anyone in the world who discovers the bot handle can send commands to Hermes, which will execute with your user privileges.

**Fix:**
1. Obtain your Telegram User ID: message `@userinfobot` → copy the numeric ID
2. Add to `~/.hermes/.env`:
   ```env
   TELEGRAM_ALLOWED_USERS=7777720835
   # Multiple users: TELEGRAM_ALLOWED_USERS=ID1,ID2,ID3
   ```
3. Restart gateway:
   ```bash
   systemctl --user restart hermes-gateway
   ```

**Verification:**
```bash
# Check .env line
grep TELEGRAM_ALLOWED_USERS ~/.hermes/.env
# Check gateway status
systemctl --user status hermes-gateway
```

### Layer 2 — Hermes Security Toggles

Recommended `config.yaml` settings for exposed-gateway scenarios:

```yaml
approvals:
  mode: manual              # default: ask before destructive commands
  timeout: 60

security:
  redact_secrets: true      # mask API keys in tool output before they hit context/logs
  tirith_enabled: true      # run security scan on flagged commands
  allow_private_urls: false # prevent model from accessing private/internal URLs

privacy:
  redact_pii: true          # hash user IDs / strip phone numbers from gateway context
```

Apply with:
```bash
hermes config set approvals.mode manual
hermes config set security.redact_secrets true
hermes config set security.tirith_enabled true
hermes config set privacy.redact_pii true
```

Most changes require a fresh session (`/reset` in chat, or `systemctl --user restart hermes-gateway` for gateway).

### Layer 3 — Docker Port Exposure Audit

**Risk:** Docker containers often publish ports as `0.0.0.0:PORT → CONTAINER:PORT`, making them reachable from any interface including the WSL2 network adapter (e.g., 192.168.144.17). This means other machines on the same LAN can reach them.

**Inventory technique:**
```bash
# List all containers with port mappings
docker ps

# Identify which services are on which ports
curl -s --max-time 2 http://127.0.0.1:PORT/ | head -c 200
```

**Example stack from the session:**
- `3001/tcp` → AnythingLLM (Docker)
- `5678/tcp` → n8n (Docker)
- `5055/tcp` → Open Notebook API (Docker)
- `8502/tcp` → Open Notebook UI (Docker)
- `8000/tcp` → SurrealDB (Docker)
- `11434/tcp` → Ollama (native, localhost-only ✅)
- `631/tcp`   → CUPS printing (native, localhost-only ✅)

**Remediation options (pick based on access pattern):**

1. **Bind to localhost only** (most secure) — change Docker Compose from:
   ```yaml
   ports:
     - "3001:3001"
   ```
   to:
   ```yaml
   ports:
     - "127.0.0.1:3001:3001"
   ```

2. **Use Tailscale subnet routing** — keep containers on Tailscale IPs only, not exposed to LAN.

3. **Never expose to `0.0.0.0`** by default — always prefer `127.0.0.1:PORT` unless cross-device access is required.

**WSL-specific warning:** WSL2 gets its own IP (e.g., 192.168.144.17) via virtual switch. Other Windows PCs on the same network may route to it unexpectedly if port binds are `0.0.0.0`.

### Layer 4 — Tailscale ACL Restrictions

When Tailscale is active on the Windows host (covering WSL via internal routing), the Hermes node is visible to the entire mesh.

**Recommended ACL policy** (to be set in Tailscale admin console):

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:desktop", "tag:mobile"],
      "dst": ["tag:hermes:*"]
    }
  ],
  "nodeAttrs": [
    {
      "target": ["tag:hermes"],
      "attr": ["funnel:off", "node:immutable"]
    }
  ]
}
```

**Enable device approval** in Tailscale admin → Settings → Device approval. New devices must be manually approved before joining the mesh.

**Verification:**
```bash
# From another Tailscale node, confirm Hermes node is visible
tailscale status
# Should show "100.x.x.x  hermes-host" with your tags
```

### Layer 5 — Matrix-Specific E2EE

If using Matrix instead of Telegram:

```env
MATRIX_DEVICE_ID=hermes_stable_01
```

Without this, keys rotate every gateway restart and historical encrypted messages become undecryptable.

## Checklist Before Going Live

After the gateway is enabled, run through this checklist:

- [ ] `TELEGRAM_ALLOWED_USERS` set in `.env` (not just `TELEGRAM_BOT_TOKEN`)
- [ ] `TELEGRAM_ALLOWED_USERS` not commented out and no duplicates in `.env`
- [ ] Gateway restarted after `.env` change (`systemctl --user restart hermes-gateway`)
- [ ] `security.redact_secrets: true` in config.yaml
- [ ] `privacy.redact_pii: true` in config.yaml (if sharing bot)
- [ ] Docker containers with `0.0.0.0` ports inventoried and confirmed intentional
- [ ] Tailscale ACLs restrict access to authorized devices only
- [ ] Device approval enabled on Tailscale
- [ ] Test: send a message from a different Telegram account → should get no response

## Pitfall: `.env` Comment vs Active Line Duplicates

During the session we found that `TELEGRAM_ALLOWED_USERS` existed in the `.env` as both a commented line (`# TELEGRAM_ALLOWED_USERS=`) and a real line (`TELEGRAM_ALLOWED_USERS=ID`). After patching with a regex, duplicates were created. Always deduplicate and keep only the active (non-commented) line.

To safely edit (prefer a Python script over sed for complex `.env` files):
```python
import re
env_path = "/home/xlybris/.hermes/.env"
with open(env_path) as f: lines = f.readlines()
kept = []
saw = False
for line in lines:
    if re.match(r'^[ \t]*TELEGRAM_ALLOWED_USERS[ \t]*=', line):
        if not saw:
            kept.append('TELEGRAM_ALLOWED_USERS=7777720835\n')
            saw = True
        continue
    kept.append(line)
with open(env_path, "w") as f: f.writelines(kept)
```
