#!/usr/bin/env bash
# AgentGUI restart script
# Kills existing server on port 5020, waits, then starts fresh

set -e

PORT=5020
PROJECT_DIR="/media/sf_AI_Ecosystem/10_Projects/02_AgentGUI"
VENV_PYTHON="/home/xlybris/venv_agentgui/bin/python"
LOG_FILE="/tmp/agentgui.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restarting AgentGUI server..."

# Kill any process on port 5020
fuser -k ${PORT}/tcp 2>/dev/null || true
pkill -f "python.*server.py" 2>/dev/null || true

# Wait for port to be freed
sleep 2
for i in {1..10}; do
    if ! ss -tlnp | grep -q ":${PORT} "; then
        break
    fi
    sleep 1
done

# Clear log
cat /dev/null > "$LOG_FILE"

# Start server
nohup "$VENV_PYTHON" "$PROJECT_DIR/server.py" > "$LOG_FILE" 2>&1 &
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Server started (PID $!)"
