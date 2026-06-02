# Storyboard Pipeline — Organização por Projeto e Automação IP-Adapter

## Contexto
Sessão: 2026-05-13 (reset após memória compilada)

## Regra: NUNCA colocar scripts de projeto em `05_Code/`
O utilizador exigiu scripts em `10_Projects/01_YTAutomation/Script_creation/` para facilitar commits git.

## Pattern de path auto-relacional
```python
SCRIPT_DIR = Path(__file__).parent.resolve()
STORYBOARD_IMAGES_DIR = SCRIPT_DIR / "storyboard_images"
STORYBOARD_JSON_PATH = SCRIPT_DIR / "storyboard.json"
```

## Pipeline Storyboard
### Passo 1: generate_storyboard_images.py
Gera cena master (Text2Image) + 5 variantes (IP-Adapter) → storyboard_images/ + storyboard.json
### Passo 2: storyboard_pipeline.py
storyboard.json → clips img2vid LTX → ffmpeg xfade → video_final/*.mp4

## Pitfall: Assumir API workflows não existem
Antes de pedir export, SEMPRE listar `03_Workflows/API/` e validar formato.

## Pitfall: Path absoluto vs relacional
Scripts apontavam para `05_Code/` e output para `04_Data/`. Quando copiados, paths quebravam.
Fix: Usar `Path(__file__).parent.resolve()` para todos os paths de output.
