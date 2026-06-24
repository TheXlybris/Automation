#!/usr/bin/env bash
# AgentGUI v2.0 — Startup Script
# Usage: ./start_agentgui.sh [port]

set -euo pipefail

PORT=${1:-5020}
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="/home/xlybris/venv_agentgui"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         AGENTGUI v2.0 LAUNCHER               ║"
echo "║         React + Socket.IO + Flask            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Check Python venv
if [[ ! -f "$VENV/bin/python" ]]; then
    echo "⚠️  VIRTUAL ENV not found at $VENV"
    echo "   Creating..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install flask flask-cors flask-socketio
fi

# Check Node.js for rebuild
REACT_DIR="/home/xlybris/projects/react-frontend"
if command -v node >/dev/null; then
    if [[ ! -d "$REACT_DIR/node_modules" ]]; then
        echo "📦 Installing React dependencies..."
        cd "$REACT_DIR"
        npm install
    fi
    
    # Auto-rebuild if source changed
    if [[ "$REACT_DIR/src/" -nt "$PROJECT_DIR/static/index.html" ]] 2>/dev/null; then
        echo "🔨 Building React frontend..."
        cd "$REACT_DIR"
        npm run build
        cp -r "$REACT_DIR/dist/"* "$PROJECT_DIR/static/"
        echo "✅ Build complete"
    fi
else
    echo "⚠️  Node.js not found. Skipping React build."
fi

echo ""
echo "🚀 Starting AgentGUI server..."
echo "   URL: http://192.168.0.188:$PORT"
echo ""

# Start server
exec "$VENV/bin/python" "$PROJECT_DIR/server.py"
