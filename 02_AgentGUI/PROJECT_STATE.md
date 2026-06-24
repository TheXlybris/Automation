# AgentGUI — PROJECT STATE
> Snapshot: 2026-06-18
> Estado: Tab PRODUZIR refatorada + Cascade Water Inpaint + 12 efeitos Pillow

## Arquitetura Atual

```
[Flask Backend]  server.py  (192.168.0.188:5020)
    |
    ├── /api/video/cascade/generate     → CASCADE WATER (Pillow+FFmpeg, CPU-only)
    ├── /api/media/*                    → upload/list/thumbnail/delete
    ├── /api/cron/tasks                 → agendamento recorrente
    ├── /api/restart                    → restart seguro
    ├── Socket.IO                       → real-time updates
    └── dispatch profiles               → dev/mm/res/wiki via tmux

[React Frontend]  build/ (static) → served by Flask
    |
    ├── App.jsx                         → 4 tabs, PRODUZIR = 4 secoes colapsaveis
    ├── AgentPanel.jsx                  → dispatch cards
    ├── OrchestratorChat.jsx            → Chat v1.0
    ├── MediaTimeline.jsx               → Timeline v2.9
    ├── ImageAnimator.jsx               → Efeitos atmosfericos (porta 5021)
    └── CascadeWaterInpaint.jsx         → Canvas mascara + parametros + gerar

[Image Animator Service]  Windows Host (opcional, porta 5021)
    |
    ├── core/image_animator.py          → 12 efeitos Pillow (incl. cascading_water)
    └── Efeitos: fog, god_rays, fireflies, particles, ken_burns,
                 pulse_light, lightning, lightning_bolt, snow, ripple,
                 rain, cascading_water
```

## Estado Componentes

| # | Componente | Localizacao | Estado | Nota |
|---|---|---|---|---|
| 1 | VM server.py | `10_Projects/02_AgentGUI/server.py` | OK | Porta 5020. Endpoint /api/video/cascade/generate novo |
| 2 | ImageAnimator svc | `engines/image_animator_service.py` | NEEDS_RESTART | Porta 5021 Windows. Reiniciar com `python -B` |
| 3 | Effects engine | `core/image_animator.py` | OK (12 efeitos) | CascadeWaterLayer adicionado. Compilado |
| 4 | React frontend | `react-frontend/src/` | OK | Build deploy OK. Emojis reais. 4 secoes colapsaveis |
| 5 | CascadeWaterInpaint | `src/components/CascadeWaterInpaint.jsx` | OK | Canvas mascara + parametros + gerar video |
| 6 | ComfyUI | Windows:8188 | OK | Independente. Nao usado pelo cascade water |
| 7 | Wiki | `12_LLM_Wiki/AgentGUI/Wiki/` | ✅ Atualizado | Index, log, cascade-water-inpaint, comfyui-model-registry |

## Tab PRODUZIR (4 Secoes Colapsaveis)

| Secao | Estado | Conteudo |
|---|---|---|
| IMAGE GENERATOR | Placeholder | "Em breve" — ComfyUI T2I |
| MUSIC GENERATOR | Placeholder | "Em breve" — batch_engine v6 |
| IMAGE ANIMATOR | Ativo | Efeitos atmosfericos (porta 5021) |
| INPAINT CASCATA | Ativo | Canvas mascara + efeito cascading_water (VM) |

## Efeito cascading_water (Tecnico)

- Scroll vertical com loop na zona da mascara
- Streaks verticais (linhas de agua em movimento)
- Espuma no topo (15%) e na base (12%) da zona
- Motion blur vertical
- Tint azulado (#4a7fb5)
- CPU-only, ~5s por 10s de video @ 1080p

## Parâmetros

| Parametro | Range | Default |
|---|---|---|
| fall_speed | 0.5..10 | 2.0 |
| foam_intensity | 0..1 | 0.7 |
| streak_density | 0..100 | 30 |
| blur_amount | 0..10 | 3.0 |
| duration | 1..60 | 10 |
| fps | 12..60 | 24 |

## Proximos Passos (prioridade)

1. **Generalizar inpainting** — mascara interativa para QUALQUER efeito (nao so cascata)
2. **Cursor pincel visivel** — mostrar tamanho do brush no rato no canvas
3. **Ken Burns + multi-efeitos com mascara separada** por efeito
4. **Opcional futuro:** API Runway/Kling como fallback pago

## Notas

- VideoGenerator (LTX img2vid) REMOVIDO do frontend (descartado)
- Emojis corrigidos: `\uXXXX` escapes → caracteres reais
- Build: `npm run build` + `cp dist/* static/` OK
- Server: reiniciado e operacional
