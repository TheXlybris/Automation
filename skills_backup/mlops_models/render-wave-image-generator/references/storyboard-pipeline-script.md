# Storyboard Pipeline Script (storyboard_pipeline.py)

## Estado actual (2026-05-13)

Local: `D:/AI_Ecosystem/05_Code/storyboard_pipeline.py`

### Propsito
Gera videos narrativos multi-cena (60s, loopavel) via:
1. `storyboard.json` → lista de cenas (caminho imagem + motion prompt)
2. Para cada cena: chama ComfyUI API com `Image2Video_LTXV.json` modificado
3. Valida clips com VAO (opcional)
4. Junta clips com ffmpeg xfade crossfade
5. Cria versao loopavel (crossfade fim→inicio)

### Dependencias
- Workflow API: `03_Workflows/API/Image2Video_LTXV.json` (ja existe, validado)
- ffmpeg com xfade (verificado: suportado)
- ComfyUI a correr em `127.0.0.1:8188`
- Imagens pre-geradas em 2400×1350 (depois redimensionadas pelo script para LTX params)
- storyboard.json com paths reais das imagens

### Configuracao no script
```python
COMFYUI_URL = "http://127.0.0.1:8188"
WORKFLOW_API_PATH = Path("/mnt/d/AI_Ecosystem/03_Workflows/API/Image2Video_LTXV.json")
OUTPUT_DIR = Path("/mnt/d/AI_Ecosystem/04_Data/video_clips")
FINAL_OUTPUT_DIR = Path("/mnt/d/AI_Ecosystem/04_Data/video_final")
STORYBOARD_PATH = Path("/mnt/d/AI_Ecosystem/08_Config/storyboard.json")

LTX_WIDTH = 768
LTX_HEIGHT = 960
LTX_LENGTH = 49        # frames (~4s a 12fps)
LTX_BATCH_SIZE = 1
LTX_STRENGTH = 0.15

TRANSITION_DURATION = 2.0
TRANSITION_TYPE = "fade"  # fade, dissolve, wipeleft, wiperight
```

### Nodes modificados pelo script
O script procura nodes pelo `class_type` (nao pelo ID, porque IDs podem variar entre exports):
- `LoadImage` → altera `image` para o path da cena
- `CLIPTextEncode` (primeiro) → altera `text` para prompt positivo
- `CLIPTextEncode` (segundo) → altera `text` para prompt negativo (BUG: procura "blurry" no texto, mas o workflow actual tem "low quality, worst quality..." — nunca encontra)
- `LTXVImgToVideo` → altera width, height, length, batch_size, strength
- `SamplerCustom` / `KSampler` → altera seed se fornecido

### BUG conhecido: deteccao do negative prompt
O script procura o negative encode com:
```python
if "negative" in text.lower() or "blurry" in text.lower():
    negative_encode_id = nid
```
O workflow actual tem texto negativo: "low quality, worst quality, deformed, distorted, disfigured..."
— nao contem "blurry" nem "negative". Resultado: o script nunca encontra o node negative, e o prompt negativo nao e modificado.

**Fix:** Procurar por palavras que existam no texto actual ("low quality", "worst quality", "deformed") ou usar logica diferente (segundo CLIPTextEncode apos o primeiro, ou verificar se o node ja tem texto com "low" ou "worst").

### Fluxo de execucao
1. `main()` verifica WORKFLOW_API_PATH existe
2. Se storyboard.json nao existe, cria exemplo com cenas de teste (cascata, campo flores, mao, voltar_cascata)
3. Para cada cena:
   - `load_workflow_api()` → carrega JSON
   - `modify_workflow_for_clip()` → deep copy + modifica nodes
   - `queue_prompt()` → POST /prompt
   - `wait_for_completion()` → polling /history/{prompt_id}
   - `get_output_path()` → resolve path do ficheiro gerado pelo ComfyUI
   - Copia/converte para OUTPUT_DIR
4. `stitch_clips_with_xfade()` → ffmpeg concat com crossfade
5. `create_loopable_video()` → versao com crossfade fim→inicio

### Estado: PENDENTE teste end-to-end
- [x] Workflow API existe e e valido
- [x] Script criado e corrigido (path)
- [ ] Negative prompt bug corrigido
- [ ] Imagens geradas com IP-Adapter
- [ ] Storyboard.json editado com paths reais
- [ ] Pipeline executado com sucesso
