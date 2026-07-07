#!/bin/bash
# docscraper — Launcher executável para o GUI web
# Uso: ./docscraper.sh
# Abre um servidor web local e lança o browser automaticamente

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Procurar venv em vários locais
VENV_PATHS=(
    "$SCRIPT_DIR/.venv/bin/activate"
    "$HOME/docscraper-venv/bin/activate"
    "$HOME/.hermes/scripts/docscraper/.venv/bin/activate"
)

VENV_ACTIVATED=false
for venv in "${VENV_PATHS[@]}"; do
    if [ -f "$venv" ]; then
        source "$venv"
        VENV_ACTIVATED=true
        break
    fi
done

# Verificar dependências
if ! python3 -c "import requests, bs4, markdownify" 2>/dev/null; then
    echo "Aviso: dependências Python em falta."
    if [ "$VENV_ACTIVATED" = false ]; then
        echo "Nenhum venv encontrado. A instalar dependências..."
        python3 -m venv "$HOME/docscraper-venv"
        source "$HOME/docscraper-venv/bin/activate"
        pip install requests beautifulsoup4 lxml markdownify playwright
        playwright install chromium
    fi
fi

# Lançar GUI web
echo "A iniciar docscraper GUI web…"
exec python3 "$SCRIPT_DIR/docscraper_web.py" "$@"