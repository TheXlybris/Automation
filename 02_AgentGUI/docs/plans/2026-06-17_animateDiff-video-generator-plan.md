# Plano: Sistema de Video Generator Avançado (AnimateDiff + IPAdapter)

## Objetivo
Substituir completamente o video generator atual (LTX img2vid) por um sistema baseado em **AnimateDiff + IPAdapter + Motion LoRAs** no ComfyUI, com controlo de qualidade artística e separação clara entre efeitos simples (Pillow) e complexos (IA generativa).

---

## 1. Estrutura de Pastas (AgentGUI)

```
D:\AI_Ecosystem\10_Projects\02_AgentGUI\
├── docs\
│   ├── plans\                    # Planos de implementação
│   ├── architecture\             # Diagramas e documentação técnica
│   └── catalogs\                 # Catálogos de efeitos e modelos
├── config\
│   └── workflows\               # JSONs de workflows ComfyUI
├── engines\
│   ├── image_animator_service.py    # Serviço Pillow (efeitos simples)
│   └── comfyui\                  # Integração ComfyUI API
│       ├── api_client.py        # Cliente HTTP para ComfyUI
│       ├── workflow_loader.py   # Carrega e customiza workflows JSON
│       └── model_registry.py    # Registo de modelos/LoRAs disponíveis
├── core\
│   ├── image_animator.py        # Efeitos procedural (11 efeitos)
│   └── effects\                # Efeitos simples isolados
│       ├── particles.py
│       ├── rain.py
│       ├── snow.py
│       ├── fog.py
│       ├── fireflies.py
│       ├── god_rays.py
│       ├── ken_burns.py
│       ├── pulse_light.py
│       ├── ripple.py
│       └── lightning_bolt.py   # (atualizado com midpoint displacement)
├── assets\
│   ├── models\                  # Modelos baixados (não versionados)
│   └── previews\               # Previews de efeitos
├── static\                      # Frontend build
├── temp\                       # Ficheiros temporários
└── react-frontend\              # Código React
    └── src\
        └── components\
            └── VideoGenerator.jsx    # Novo componente
```

---

## 2. Arquitetura do Sistema

```
┌──────────────────────────────────────────────────────────────┐
│                    AGENTGUI FRONTEND (React)                   │
│                    Tab: PRODUZIR → Video Generator           │
│                                                              │
│  [Upload Imagem] → [Análise Automática de Cena]            │
│                    ↓                                         │
│  [Escolher Tipo de Movimento]                                │
│    - Simples (Pillow): particles, rain, snow, fog...        │
│    - Complexo (AnimateDiff): ocean, fire, lightning, wind  │
│                    ↓                                         │
│  [Parâmetros Avançados]                                     │
│    motion_scale | denoise | frame_count | preview            │
│                    ↓                                         │
│  [Render] → [Preview 4 frames] → [Aprovar/Render Full]     │
└────────────────────┬─────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  VM:5020     │ │ Windows:5021 │ │ Windows:8188 │
│  server.py   │ │  Pillow      │ │  ComfyUI     │
│  (API Proxy) │ │  (rápido)    │ │  (qualidade) │
└──────────────┘ └──────────────┘ └──────────────┘
```

---

## 3. Fases de Implementação

### Fase 1: Infraestrutura ComfyUI (Windows Host)
**Responsável:** User (instalação) + Eu (documentação)

1. **Instalar nodes no ComfyUI Manager:**
   - `ComfyUI-AnimateDiff-Evolved` (pack essencial)
   - `ComfyUI-VideoHelperSuite` (exportar MP4/GIF)
   - `ComfyUI_IPAdapter_plus` (manter identidade da imagem)
   - `ComfyUI-ControlNet-Aux` (preprocessors: depth, openpose)
   - `ComfyUI-Depth-Anything-TensorRT` (depth map, opcional)

2. **Descarregar modelos:**
   - Motion Module: `mm_sd_v15_v2.ckpt` (SD 1.5) ou `mm_sdxl_v10_beta.ckpt` (SDXL)
   - IPAdapter models: `ip-adapter_sd15.bin` + image encoder `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors`
   - VAE: `vae-ft-mse-840000-ema-pruned.safetensors`
   - ControlNet: `control_v11f1p_sd15_depth.pth` (para depth-based motion)

3. **Descarregar Motion LoRAs:**
   - `ocean_wave_v1.safetensors` — ondas do mar
   - `fire_and_smoke_motion.safetensors` — fogo e fumo
   - `lightning_bolt_motion.safetensors` — relâmpagos
   - `water_splash_v2.safetensors` — salpicos de água
   - `wind_grass_motion.safetensors` — vento em ervas/cabelo
   - `smoke_drift_v1.safetensors` — fumo a flutuar

4. **Localização dos modelos:**
   - ComfyUI standard: `D:\AI_Ecosystem\02_Engines\ComfyUI\ComfyUI\models\`
     - `animatediff_models\` — motion modules
     - `loras\` — motion LoRAs
     - `ipadapter\` — IPAdapter models
     - `vae\` — VAE
     - `controlnet\` — ControlNet

### Fase 2: Workflows JSON Pré-Configurados
**Responsável:** Eu
**Local:** `D:\AI_Ecosystem\10_Projects\02_AgentGUI\config\workflows\`

Criar workflows para cada tipo de movimento:

| Workflow | Motion LoRA | Denoise | Motion Scale | ControlNet | Notas |
|---|---|---|---|---|---|
| `ocean_wave.json` | ocean_wave_v1 | 0.55 | 1.0 | depth (opcional) | Ondas suaves a quebrar |
| `fire_smoke.json` | fire_and_smoke | 0.60 | 1.2 | none | Fogo intenso, fumo ascendente |
| `lightning_flash.json` | lightning_bolt | 0.45 | 0.8 | none | Flash rápido, curta duração |
| `water_splash.json` | water_splash | 0.55 | 1.1 | depth | Salpicos em rochas/mais |
| `wind_grass.json` | wind_grass | 0.50 | 0.9 | none | Movimento suave de vegetação |
| `smoke_drift.json` | smoke_drift | 0.50 | 0.6 | none | Fumo a flutuar lentamente |
| `cloud_movement.json` | (modelo base) | 0.40 | 0.7 | none | Nuvens a deslocarem-se |

**Estrutura comum de cada workflow:**
```
Load Image → Encode (VAE) → 
→ AnimateDiff Loader (Motion Module + Motion LoRA) →
→ IPAdapter Apply (mantém identidade da imagem) →
→ KSampler (denoise controlado, seed fixa opcional) →
→ VAE Decode →
→ Video Combine (16-32 frames, 8fps) →
→ Save Video / Preview
```

### Fase 3: API Client (Python)
**Responsável:** Eu
**Local:** `D:\AI_Ecosystem\10_Projects\02_AgentGUI\engines\comfyui\api_client.py`

**Funcionalidades:**
1. **Submeter workflow** — POST para `192.168.0.187:8188/prompt` com JSON do workflow
2. **Poll status** — GET `192.168.0.187:8188/history/{prompt_id}` até completion
3. **Download output** — GET o ficheiro gerado (MP4 ou sequência de PNGs)
4. **Error handling** — retry, timeout, VRAM OOM detection
5. **Progress reporting** — Socket.IO ou polling para frontend

**Interface:**
```python
class ComfyUIClient:
    def __init__(self, base_url="http://192.168.0.187:8188"):
        ...
    
    def submit_workflow(self, workflow_json: dict, image_path: str) -> str:
        """Submete workflow, retorna prompt_id"""
    
    def get_status(self, prompt_id: str) -> dict:
        """Retorna status: queued/running/completed/error"""
    
    def get_output(self, prompt_id: str) -> str:
        """Retorna path do vídeo gerado"""
    
    def cancel(self, prompt_id: str) -> bool:
        """Cancela job em execução"""
```

### Fase 4: Workflow Loader
**Responsável:** Eu
**Local:** `D:\AI_Ecosystem\10_Projects\02_AgentGUI\engines\comfyui\workflow_loader.py`

**Funcionalidades:**
1. Carregar workflow base do JSON
2. Substituir placeholders:
   - `{IMAGE_PATH}` → path da imagem uploadada
   - `{SEED}` → seed aleatória ou fixa
   - `{MOTION_SCALE}` → valor do slider
   - `{DENOISE}` → valor do slider
   - `{FRAME_COUNT}` → 16, 24, 32
3. Validar se modelos necessários existem no disco
4. Fallback para workflow alternativo se modelo em falta

### Fase 5: VM server.py — Novos Endpoints
**Responsável:** Eu
**Local:** `D:\AI_Ecosystem\10_Projects\02_AgentGUI\server.py`

**Novos endpoints:**
```
POST /api/video/enhanced/analyze    → Analisa imagem, sugere tipo de movimento
POST /api/video/enhanced/render     → Renderiza com ComfyUI (AnimateDiff)
GET  /api/video/enhanced/status/<job_id>
GET  /api/video/enhanced/preview/<job_id>  → Retorna 4 frames de preview
POST /api/video/enhanced/approve    → Aprova preview, renderiza vídeo completo
POST /api/video/simple/render       → Mantém endpoints Pillow existentes
```

**Lógica de routing:**
- Se efeito está em `EFFECT_REGISTRY` (Pillow) → usa Windows:5021 (rápido)
- Se efeito está em `WORKFLOW_REGISTRY` (AnimateDiff) → usa Windows:8188 (qualidade)

### Fase 6: Frontend React — Novo VideoGenerator
**Responsável:** Eu (com ajuda do user para testar)
**Local:** `D:\AI_Ecosystem\10_Projects\02_AgentGUI\react-frontend\src\components\VideoGenerator.jsx`

**Interface nova:**
```
┌─────────────────────────────────────────────┐
│  UPLOAD IMAGEM                              │
├─────────────────────────────────────────────┤
│  ANÁLISE DA CENA: "Praia com ondas"        │
│  SUGESTÃO: Motion Complexo (Ondas)          │
├─────────────────────────────────────────────┤
│  TIPO DE MOVIMENTO:                         │
│  [○] Simples (rápido)  [●] Complexo (IA)   │
├─────────────────────────────────────────────┤
│  SE COMPLEXO:                               │
│  Motion: [Ocean Wave ▼]                     │
│  Intensidade: [====|====] 1.0              │
│  Fidelidade: [====|====] 0.55 (denoise)     │
│  Frames: [16 ▼] 8fps                        │
├─────────────────────────────────────────────┤
│  [ PREVIEW 4 FRAMES ]                      │
├─────────────────────────────────────────────┤
│  [ APROVAR E RENDERIZAR VÍDEO COMPLETO ]    │
├─────────────────────────────────────────────┤
│  [ DOWNLOAD MP4 ]                           │
└─────────────────────────────────────────────┘
```

### Fase 7: Model Registry
**Responsável:** Eu
**Local:** `D:\AI_Ecosystem\10_Projects\02_AgentGUI\engines\comfyui\model_registry.py`

**Funcionalidades:**
1. Scan automático de `models/` no ComfyUI
2. Verificar existência de motion modules, LoRAs, IPAdapter, VAE
3. Expor via endpoint: `GET /api/video/models`
4. Marcar workflows como "available" ou "missing models"

---

## 4. Migração do LTX img2vid

### O que remover:
- Referências a LTX no frontend
- Endpoints `/api/video/ltx/*` no server.py
- Dependências de modelos LTX no ComfyUI

### O que manter:
- Sistema de upload de imagens
- Sistema de job tracking (JOBS dict)
- Sistema de download de vídeos
- Integração Socket.IO para progress

### O que adaptar:
- Endpoint `/api/video/animate` → mantém para efeitos Pillow
- Novo endpoint `/api/video/enhanced/render` → para AnimateDiff
- Unificar status tracking (mesma estrutura JOBS)

---

## 5. Catálogo de Efeitos (Documentação)

**Local:** `D:\AI_Ecosystem\10_Projects\02_AgentGUI\docs\catalogs\`

**Ficheiros:**
- `simple-effects.md` — Documentação dos 11 efeitos Pillow
- `complex-effects.md` — Documentação dos workflows AnimateDiff
- `model-requirements.md` — Lista de modelos necessários com links de download
- `workflow-parameters.md` — Guia de parâmetros (denoise, motion_scale, etc.)

---

## 6. Testes e Validação

### Teste 1: Workflow isolado no ComfyUI
- Abrir ComfyUI browser (192.168.0.187:8188)
- Carregar workflow `ocean_wave.json`
- Fazer upload de imagem de teste
- Verificar se gera 16 frames com movimento natural
- Medir tempo e VRAM usada

### Teste 2: API via Python
- Script standalone que chama `ComfyUIClient`
- Submeter workflow, poll status, download output
- Verificar MP4 válido

### Teste 3: Integração AgentGUI
- Frontend → VM server.py → ComfyUI API
- Verificar progress reporting
- Verificar preview de 4 frames
- Verificar renderização completa

### Teste 4: Performance
- Medir tempo por workflow (target: <60s para 16 frames)
- Monitorar VRAM (target: <12GB dos 16GB disponíveis)
- Testar com múltiplos jobs em fila

---

## 7. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| VRAM 16GB insuficiente para SDXL+AnimateDiff | Média | Alto | Usar SD 1.5 em vez de SDXL; reduzir resolução; usar batch size 1 |
| ComfyUI API instável (crashes, timeouts) | Média | Médio | Retry com backoff; fallback para efeito Pillow; timeout 5min |
| Motion LoRAs de baixa qualidade | Média | Alto | Testar antes de documentar; manter catálogo de LoRAs validados |
| User não quer instalar nodes no ComfyUI | Baixa | Alto | Documentar passo a passo; oferecer script de instalação automática |
| IPAdapter não mantém identidade da imagem | Baixa | Alto | Ajustar weight do IPAdapter; usar denoise mais baixo |
| Sistema fica muito complexo | Média | Médio | Manter separação clara simples vs complexo; documentar bem |

---

## 8. Próximos Passos Imediatos

1. **User:** Confirmar instalação dos nodes no ComfyUI Manager
2. **Eu:** Criar workflow JSON base (`ocean_wave.json`) como proof-of-concept
3. **Eu:** Criar `api_client.py` e testar submit via Python
4. **User/Eu:** Descarregar modelos essenciais (motion module + IPAdapter)
5. **Eu:** Integrar endpoint no `server.py` VM
6. **Eu/Eu:** Criar frontend React (primeira versão)
7. **Testar:** Pipeline completo end-to-end

---

## 9. Notas de Longo Prazo

- Considerar **batch processing** para múltiplas imagens
- Considerar **template system** — workflows parametrizáveis por templates
- Considerar **user-defined workflows** — upload de JSON customizado
- Considerar **cache de modelos** — não recarregar se já em VRAM
- Monitorar **comunidade AnimateDiff** — novos motion modules aparecem frequentemente

---

**Data do Plano:** 2026-06-17
**Versão:** 1.0
**Próxima revisão:** Após Fase 2 completa
