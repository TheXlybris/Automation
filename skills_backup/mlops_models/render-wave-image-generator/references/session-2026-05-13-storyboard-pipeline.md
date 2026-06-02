# Sessão 2026-05-13 — Storyboard Pipeline com IP-Adapter Plus + Dashboard HTML

## Problema resolvido
O user queria gerar um vídeo de ~1 minuto com coerência visual entre cenas (mesmo cenário, diferentes perspetivas de câmara), mas nao conseguia manter consistência ao gerar imagens independentes.

## Solução
Pipeline automatizado com IP-Adapter Plus SDXL:
1. Cena master (Text2Image normal)
2. 5 variantes usando IP-Adapter com a cena master como referência
3. Script gera storyboard.json automaticamente
4. Pipeline img2vid LTX 2B gera clips e junta com ffmpeg xfade

## Ficheiros criados

| Ficheiro | Localização | Função |
|----------|-------------|--------|
| generate_storyboard_images.py | Script_creation/ | Gera cena master + 5 variantes coerentes |
| storyboard_pipeline.py | Script_creation/ | Chama ComfyUI API N vezes + ffmpeg crossfade |
| storyboard_dashboard.html | Script_creation/ | Dashboard com botões e logs em tempo real |
| server.py | Script_creation/ | Flask backend (auto-detect venv) |
| start.sh | Script_creation/ | Script bash para arrancar servidor |
| RENDER_WAVE_Storyboard.bat | Desktop (Fil_B) | Atalho Windows: arranca servidor + abre browser |
| CreateAutoStartTask.ps1 | Script_creation/ | PowerShell: cria tarefa agendada Windows auto-start |

## Arquitetura do servidor Flask

```
Browser (port 5010) ← HTTP ← Flask server.py
                           ↓
                    Python scripts (background)
                           ↓
                    ComfyUI API (port 8188)
```

### Endpoints do servidor
- `POST /start_images` → Inicia generate_storyboard_images.py em background, devolve job_id
- `POST /start_video` → Inicia storyboard_pipeline.py em background, devolve job_id
- `GET /status/<job_id>` → Devolve log em tempo real (últimas 50 linhas) + status
- `GET /list_images` → Lista imagens em Script_creation/storyboard_images/
- `GET /list_videos` → Lista vídeos em Script_creation/video_final/

### Auto-detect do venv
O server.py detecta automaticamente se Flask está disponível. Se não estiver, faz `os.execv()` para reiniciar com o Python do venv existente em `Image_creation/venv/bin/python3`.

## Configuração do pipeline

| Parâmetro | Valor |
|-----------|-------|
| Resolução imagens | 2048×1152 (16:9) |
| Resolução vídeo LTX | 768×960 |
| Nº cenas | 6 (1 master + 5 variantes) |
| Duração alvo | ~60 segundos |
| IP-Adapter | PLUS preset, weight=0.8, linear, concat |
| Crossfade | 2 segundos entre clips |

## Cenas pré-definidas

1. **cena_master** — Wide shot completo (cascata + prado + flores)
2. **closeup_cascata** — Close-up da cascata
3. **flores_primeiro_plano** — Flores em primeiro plano, cascata desfocada
4. **lago_cristalino** — Lago na base da cascata
5. **vista_panoramica** — Vista ligeiramente elevada
6. **regresso_wide** — Regresso ao wide shot (para loop perfeito)

## Como usar

### Modo automático (tudo pelo browser)
1. Dá duplo-clique no atalho `RENDER_WAVE_Storyboard.bat` no Desktop
2. O servidor arranca em background e o browser abre automaticamente em `http://127.0.0.1:5010`
3. No dashboard, clica em "🎬 Gerar Imagens Agora"
4. Aguardar ~15-25 minutos (6 imagens)
5. Quando terminar, clica em "🎞️ Gerar Vídeo Final"
6. Aguardar ~30 minutos (6 clips + crossfade)
7. O vídeo final fica em `Script_creation/video_final/`

### Modo manual (linha de comandos)
```bash
cd /mnt/d/AI_Ecosystem/10_Projects/01_YTAutomation/Script_creation
python3 generate_storyboard_images.py  # Passo 1
python3 storyboard_pipeline.py         # Passo 2
```

## Requisitos prévios
- ComfyUI a correr em http://127.0.0.1:8188
- Modelos IP-Adapter instalados (ver SKILL.md seção IP-Adapter Configuration)
- Modelo LTX 2B v0.9.5 carregado no ComfyUI
- ffmpeg com suporte xfade

## Auto-start no Windows
Para que o servidor arraque automaticamente ao iniciar sessão:
1. Abrir PowerShell como Administrador
2. Correr: `CreateAutoStartTask.ps1`
3. A tarefa `THE_RENDER_WAVE_Storyboard` fica registada e arranca o servido em background

## Lições desta sessão
- Quando o user pede "botões em vez de comandos", criar dashboard HTML + Flask backend + atalho desktop
- Sempre usar auto-detect de venv nos scripts Flask (não assumir que o sistema tem Flask)
- Separar output do pipeline na pasta do projeto (Script_creation/) em vez de pastas globais (04_Data/, 05_Code/)
- O workflow API img2vid já existia em 03_Workflows/API/ — não precisava de exportar novamente

## Notas
- Toda a pasta `Script_creation/` está pronta para commit em git (paths relativos, auto-contained)
- Os workflows em `03_Workflows/API/` são a única dependência externa (partilhados entre projetos)
