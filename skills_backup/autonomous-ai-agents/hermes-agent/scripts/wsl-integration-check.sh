#!/bin/bash
# wsl-integration-check.sh — Quick health check for WSL Hermes integrations
# Run with: bash ~/.hermes/skills/autonomous-ai-agents/hermes-agent/scripts/wsl-integration-check.sh

set -euo pipefail

echo "=== WSL Integration Health Check ==="
echo

# 1. Chrome / Chromium (non-snap)
echo "◆ Chrome installation:"
if command -v google-chrome-stable &> /dev/null; then
    echo "  ✓ google-chrome-stable: $(google-chrome-stable --version 2>/dev/null | head -1)"
elif command -v google-chrome &> /dev/null; then
    echo "  ✓ google-chrome: $(google-chrome --version 2>/dev/null | head -1)"
else
    echo "  ✗ No Google Chrome found (install from .deb, not snap)"
fi

# Check for snap Chromium (bad on WSL)
if command -v chromium-browser &> /dev/null && file "$(which chromium-browser)" | grep -q snap; then
    echo "  ⚠ chromium-browser is a snap stub — will fail in WSL"
fi
echo

# 2. OpenCode
echo "◆ OpenCode CLI:"
if command -v opencode &> /dev/null; then
    echo "  ✓ opencode version: $(opencode --version 2>/dev/null)"
    AUTH_COUNT=$(opencode auth list 2>/dev/null | grep -c "provider" || echo "0")
    if [ "$AUTH_COUNT" -gt 0 ]; then
        echo "  ✓ Authenticated providers: $AUTH_COUNT"
    else
        echo "  ⚠ No auth providers configured — run 'opencode auth login'"
    fi
else
    echo "  ✗ opencode not in PATH"
fi
echo

# 3. .env active keys
echo "◆ Active .env keys (non-comment, non-blank):"
if [ -f ~/.hermes/.env ]; then
    ACTIVE=$(grep -v "^#" ~/.hermes/.env | grep -v "^$" | grep -c "=" || echo "0")
    echo "  $ACTIVE active variable(s)"
    
    for KEY in TAVILY_API_KEY GITHUB_TOKEN WEB_TOOLS_DEBUG VISION_TOOLS_DEBUG MOA_TOOLS_DEBUG IMAGE_TOOLS_DEBUG; do
        VAL=$(grep "^${KEY}=" ~/.hermes/.env 2>/dev/null || true)
        if [ -n "$VAL" ]; then
            # Mask the actual value
            MASKED=$(echo "$VAL" | sed 's/=.*$/=***/')
            echo "  ✓ $MASKED"
        else
            echo "  ✗ $KEY (not set)"
        fi
    done
else
    echo "  ✗ ~/.hermes/.env not found"
fi
echo

# 4. Hermes doctor summary
echo "◆ Hermes doctor (key tools only):"
hermes doctor 2>&1 | grep -E "browser-cdp|web |computer_use|discord|image_gen|moa|rl " || true
echo

echo "=== Check complete ==="
