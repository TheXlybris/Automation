#!/usr/bin/env bash
# docscraper — Launcher executável para a GUI tkinter
# Uso: ./docscraper_gui.sh ou duplo-clique no .desktop
# Detecta/cria venv automaticamente, instala dependências se faltarem

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$HOME/docscraper-venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# ── 1. Criar venv se não existir ────────────────────────────
if [ ! -f "$VENV_PYTHON" ]; then
    echo "A criar ambiente virtual Python em $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
fi

# ── 2. Verificar e instalar dependências ─────────────────────
NEEDS_INSTALL=false
if ! "$VENV_PYTHON" -c "import requests, bs4, lxml, markdownify" 2>/dev/null; then
    NEEDS_INSTALL=true
fi

if [ "$NEEDS_INSTALL" = true ]; then
    echo "A instalar dependências Python..."
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install requests beautifulsoup4 lxml markdownify playwright
    echo "A instalar Chromium para Playwright (isto pode demorar)..."
    "$VENV_PYTHON" -m playwright install chromium
    echo "Dependências instaladas."
fi

# ── 3. Verificar tkinter ────────────────────────────────────
if ! "$VENV_PYTHON" -c "import tkinter" 2>/dev/null; then
    echo "A instalar python3-tk..."
    sudo apt-get install -y python3-tk 2>/dev/null || true
fi

# ── 4. Lançar GUI ────────────────────────────────────────────
echo "A iniciar docscraper GUI..."
exec "$VENV_PYTHON" "$SCRIPT_DIR/docscraper_gui.py" "$@"