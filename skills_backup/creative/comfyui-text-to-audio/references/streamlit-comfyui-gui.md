# Pattern: Streamlit GUI para ComfyUI API (Music Creation)

## Contexto
Quando o utilizador precisa de uma interface web para controlar geração T2A via ComfyUI API, construir um GUI Streamlit é preferível a CLI puro (o utilizador explicitamente prefere GUI para ferramentas criativas).

---

## Problema: Presets não actualizam campos no Streamlit

### Sintoma
Ao escolher um preset, os campos Tags/BPM/Key mantêm o valor anterior.

### Solução: `st.session_state` + `on_change`

```python
# Inicializar (executa apenas na primeira vez)
if "t1_tags" not in st.session_state:
    st.session_state.t1_tags = DEFAULT_TAGS
    st.session_state.t1_bpm = 60
    st.session_state.t1_key = "A minor"

def apply_preset_t1():
    """Callback chamada quando o selectbox muda."""
    p = st.session_state.get("t1_preset", "(Custom)")
    if p in PRESETS:
        st.session_state.t1_tags = PRESETS[p]["tags"]
        st.session_state.t1_bpm = PRESETS[p]["bpm"]
        st.session_state.t1_key = PRESETS[p]["keyscale"]

# O selectbox chama a callback quando o valor muda
preset = st.selectbox(
    "Preset", ["(Custom)"] + list(PRESETS.keys()),
    key="t1_preset",
    on_change=apply_preset_t1     # ← critico
)

# Widget lê do session_state, nao da variavel local
tags = st.text_area("Tags", value=st.session_state.t1_tags, key="t1_tags")
bpm = st.number_input("BPM", value=st.session_state.t1_bpm, key="t1_bpm")
key = st.selectbox("Key", KEYS, index=KEYS.index(st.session_state.t1_key), key="t1_key")
```

**Regra:** NUNCA usar `value=variavel_python` com presets. Sempre `st.session_state` + `on_change`.

---

## Pattern: Auto-Polling para Batch Jobs

Para batch processing (enviar N clips ao ComfyUI sequencialmente), o Streamlit precisa de **auto-polling** — verificar periodicamente se o ComfyUI completou o job actual antes de enviar o proximo.

### Abordagem correcta: `time.sleep(2) + st.rerun()`

```python
if st.session_state.batch_running:
    running  = [...]  # items com status "running"
    pending  = [...]  # items com status "pending"

    if running:
        # Ainda ha um job a correr — verificar se terminou
        status = get_job_status(running[0]["prompt_id"])
        if status["found"] and status["completed"]:
            st.rerun()   # ← refresh para marcar como completed e avancar
        else:
            time.sleep(2)      # ← pausa entre polls (evita bombardeio)
            st.rerun()         # ← voltar a verificar daqui a 2 segundos
    elif pending:
        # Nada a correr, ha pendentes → lançar proximo
        process_one_batch()    # envia o proximo clip
        time.sleep(1)
        st.rerun()
    else:
        st.success("Batch terminado!")
        st.session_state.batch_running = False
```

**Regra:** `time.sleep()` + `st.rerun()` funciona correctamente **desde que haja uma pausa** (≥2s) entre polls. Sem `sleep`, o browser refresha em loop sem parar (flood). Com `sleep`, dá tempo para interacção.

### Execution Order for Auto-Polling (Critical, validated 2026-06-02)

The `refresh_batch()` function that polls ComfyUI history and updates item statuses to `completed`/`failed` MUST run at the **very beginning of each tab render cycle**, before checking any counts. If the motor auto-progressive checks the counts first, it will always see `running=1, pending=2` even after the job finished, and will sleep forever instead of advancing.

```python
# CORRECT — refresh first, then check counts
refresh_batch()  # ← runs on EVERY render, not just when batch_running=True

running   = [i for i in queue if i["status"] == "running"]
pending   = [i for i in queue if i["status"] == "pending"]
completed = [i for i in queue if i["status"] == "completed"]

if st.session_state.batch_running:
    if running:
        status = get_job_status(running[0]["prompt_id"])
        if status["completed"]:
            st.rerun()      # item became completed → next render will see it
        else:
            time.sleep(2)
            st.rerun()
    elif pending:
        process_one_batch()  # ← launches next pending item
        time.sleep(1)
        st.rerun()
    else:
        st.success("Done!")
        st.session_state.batch_running = False
```

**Pitfall verified in production (Music_creation project, 2026-06-02):** When `refresh_batch()` was placed inside the `if st.session_state.batch_running:` block, the first rerun after an item completed still showed `running=1` because `refresh_batch()` was skipped when `batch_running` was `True`. On the rerun after completion detection, `running` was recomputed from stale session_state before refresh, so it never advanced. Items 2+ stayed pending forever.

**Fix verified:** Move `refresh_batch()` to the top of the tab block — it must execute on every Streamlit re-render, even when `batch_running` is already `True`.

### Botão "Parar Batch" para interromper o auto-polling

```python
if st.button("Parar Batch"):
    st.session_state.batch_running = False
    st.rerun()
```

---

## Pattern: Queue Management Buttons in Streamlit UIs

For batch queues, provide control buttons that allow the user to manage state without restarting the app:

```python
# Clear all queue items
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Limpar Queue (todos)"):
        st.session_state.batch_queue = []
        st.session_state.batch_running = False
        st.rerun()
with col2:
    if st.button("Limpar concluidos"):
        st.session_state.batch_queue = [
            i for i in st.session_state.batch_queue if i["status"] != "completed"
        ]
        st.rerun()
with col3:
    if st.button("Parar Batch"):
        st.session_state.batch_running = False
        st.rerun()
```

### Individual item removal

Each item needs a globally unique `key` including both index and item ID to prevent collisions after removals:

```python
for idx, item in enumerate(queue[:20]):
    if item["status"] in ("pending", "failed"):
        if st.button("X", key=f"rm_{idx}_{item['id']}", help="Remover"):
            queue.pop(idx)
            st.rerun()
```

### Bulk file deletion with confirmation

For destructive operations (e.g., deleting all MP3s), use a confirmation pattern:

```python
with st.expander("🗑️ Gestao de ficheiros", expanded=False):
    if st.checkbox("Confirmo que quero apagar TODOS os MP3s"):
        if st.button("APAGAR TUDO"):
            for mp3 in mp3s:
                mp3.unlink()
            st.rerun()
```

---

## Pattern: Coherence Mode for Batch Generation

When generating multiple audio clips that must sound musically coherent (same "DNA"), use a **Coherence Mode** that shares the seed across all clips:

### Concept

Diffusion models (ACE Step, MusicGen) use the seed as the random noise starting point. Same seed + same prompt = structurally similar output. This produces "variations" rather than completely different compositions.

### Implementation

```python
if "coherence_seed" not in st.session_state:
    st.session_state.coherence_seed = None
if "coherence_mode" not in st.session_state:
    st.session_state.coherence_mode = False

def add_to_queue(tags, lyrics, bpm, duration, keyscale, cfg, temp, count, seed_start):
    dur = max(duration, 90) if st.session_state.coherence_mode else duration
    for i in range(count):
        if st.session_state.coherence_mode and st.session_state.coherence_seed is not None:
            s = st.session_state.coherence_seed
        else:
            s = seed_start + i if seed_start > 0 else random.randint(1, 2**63 - 1)
        queue.append({..., "seed": s, "status": "pending"})

def process_one_batch():
    for item in queue:
        if item["status"] == "pending":
            if coherence_mode and coherence_seed is not None:
                use_seed = coherence_seed
            else:
                use_seed = item["seed"]
            ok, pid, seed = send_workflow(..., seed=use_seed)
            if ok and coherence_mode and coherence_seed is None:
                coherence_seed = seed  # capture seed from 1st clip
```

### Rules

1. **1st clip seed is random** (set by ComfyUI when seed=0 or random)
2. **Subsequent clips reuse that seed** captured from the 1st successful job
3. **Coherence Mode forces duration >= 90s** — shorter clips (< 90s) lack enough musical structure to be meaningfully coherent
4. **Seed persists between batches** — a new batch reuses the seed until the user explicitly disables then re-enables Coherence Mode
5. **Disable → seed cleared** — turning Coherence OFF immediately resets the stored seed

### CRITICAL PITFALL: ComfyUI Deduplicates Identical Workflows

ComfyUI internally deduplicates prompts that have **exactly the same node graph, parameters, and payload**. When Coherence Mode submits 3 clips with the same seed, same tags, same lyrics, same BPM, same duration, etc., the ComfyUI server executes the 1st normally (~40s) and returns "completed" for items 2 and 3 in `0.00s` with NO audio output. The GUI sees `prompt_id` in history and marks them done, but no file exists.

**IMPORTANT:** `client_id` and `filename_prefix` alone are **NOT sufficient** to prevent deduplication. ComfyUI deduplicates based on the **workflow node graph hash**, not the API request metadata. The `client_id` is only used for WebSocket client tracking, and `filename_prefix` is just a node input — if all other node inputs are identical, the hash is still the same.

**Fix (validated in production — Music_creation project, 2026-06-02):** Keep the seed identical but make **at least one real workflow input** strictly unique per item. The reliable approach is a tiny **duration jitter** (imperceptible but changes the hash):

**Confirmed path:** A batch of 3 items with Coherence Mode ON, unique `client_id`, and unique `filename_prefix` still deduplicated (ComfyUI log: item 1 = 42s, items 2+3 = 0.00s, no MP3 output). Adding `jitter=round(idx * 0.01, 2)` to the `duration` and `seconds` node inputs resolved it — all 3 items executed in ~40s each and produced distinct files.

```python
def process_one_batch():
    for idx, item in enumerate(queue):
        if item["status"] == "pending":
            use_seed = coherence_seed if coherence_mode else item["seed"]
            ok, pid, seed = send_workflow(
                item["tags"], item["lyrics"], item["bpm"],
                item["duration"], item["keyscale"],
                item["cfg_scale"], item["temperature"],
                seed=use_seed,
                prefix=f"{DEFAULT_PREFIX}_item{item['id'][-5:]}",  # still unique for filenames
                client_id=f"gui-batch-{item['id']}",                  # still unique for WS
                jitter=round(idx * 0.01, 2)  # ← 0.00, 0.01, 0.02s — changes workflow hash
            )
```

The `jitter` is added to both the `duration` input (node 94) and the `seconds` input (node 98). At 44.1kHz, a 0.01s difference is less than 1 sample — completely imperceptible. But the workflow JSON hash changes, forcing ComfyUI to execute each item independently.

**This applies to ANY ComfyUI batch where you want deterministic/repeatable parameters:** same seed for coherence, same prompt for variations, etc. Always vary a real workflow input (duration jitter, a dummy float, etc.) to force actual execution. `client_id` and `prefix` are necessary for filenames and WebSocket tracking, but they do NOT prevent deduplication.

### Implementation with Jitter in `send_workflow()`

```python
def send_workflow(..., jitter=0.0):
    wf = get_base_workflow()
    # ... other assignments ...
    wf["94"]["inputs"]["duration"] = float(duration) + jitter
    wf["98"]["inputs"]["seconds"] = float(duration) + jitter
    # ... rest of payload ...
```

### Streamlit Toggle

```python
coh = st.toggle("Coherence Mode", value=st.session_state.coherence_mode,
                help="Todas as musicas do batch usam a mesma seed")
st.session_state.coherence_mode = coh
if coh:
    if duration < 90:
        st.warning("Duracao subida automaticamente para 90s (Coherence Mode).")
```

## Problema: Encoding em ficheiros .bat no Windows

### Sintoma
Caracteres acentuados (`é`, `á`, `ç`) num `.bat` quebram parsing do batch interpreter, mostrando erros como `'verificar' is not recognized`.

### Solução

1. **Não usar acentos** em `.bat` — manter tudo ASCII:
   ```batch
   REM OK
   echo A verificar dependencias...

   REM EVITAR
   echo A verificar dependencias...   ← quebra!
   ```

2. Ou usar `chcp 65001` no topo + guardar ficheiro como UTF-8 com BOM:
   ```batch
   @echo off
   chcp 65001 > nul
   echo Dependencias   ← funciona COM BOM
   ```

3. Preferir evitar acentos em `echo` statements dentro de `.bat`.

---

## Pattern: Tabs no Streamlit com state isolado

Cada tab deve ter `key` unicos para evitar conflito de session_state:

```python
tab1, tab2 = st.tabs(["Gerar", "Batch"])

with tab1:
    preset = st.selectbox("Preset", options, key="t1_preset")

with tab2:
    preset = st.selectbox("Preset", options, key="t2_preset")  # key diferente!
```

---

## Estrutura do Music Creator GUI

```
music_creator_gui.py        — GUI principal (Streamlit)
Start_Music_Creator.bat     — Lancador (ASCII-safe)
requirements.txt            — streamlit, requests
ambient_prompts.json        — 8 presets validados (lyrics = [instrumental])
```

## Regras ACE Step (independentes da UI)

- Lyrics = `[instrumental]` apenas
- Não usar marcadores `[Verse]`, `[rain]`, etc.
- Tags devem incluir `no vocals, no lyrics`
- `generate_audio_codes: True` mesmo para instrumental
- Ver skill `comfyui-text-to-audio` para detalhes completos
