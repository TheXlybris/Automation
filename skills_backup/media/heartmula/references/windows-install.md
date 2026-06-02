# HeartMuLa Windows Host Installation — Session 2026-05-26

## Context
- **Host:** Windows 11 + RTX 4060 Ti 16GB
- **VM:** Ubuntu 24.04.4 (headless, no GPU passthrough)
- **HeartMuLa runs on Windows host**, accessed from VM via network share mounted at `/mnt/ai`
- **Models:** 3B only (fits in 6.2GB VRAM with lazy_load)

## Installation Steps

### 1. Clone + Environment
```powershell
cd D:\AI_Ecosystem\09_Tools
git clone https://github.com/HeartMuLa/heartlib.git
cd heartlib
uv venv --python 3.10 .venv
.venv\Scripts\activate
uv pip install -e .
```

### 2. Fix Dependencies
```powershell
uv pip install --upgrade datasets transformers huggingface-hub
```

### 3. Download Models
```powershell
cd heartlib
hf download HeartMuLa/HeartMuLaGen --local-dir .\ckpt
hf download HeartMuLa/HeartMuLa-oss-3B-happy-new-year --local-dir .\ckpt\HeartMuLa-oss-3B
hf download HeartMuLa/HeartCodec-oss-20260123 --local-dir .\ckpt\HeartCodec-oss
```

### 4. Apply Source Patches

**Patch 1 — RoPE cache fix** (in `src\heartlib\heartmula\modeling_heartmula.py`):
In `setup_caches()` method, add after the `reset_caches()` try/except block:
```python
# Re-initialize RoPE caches that were skipped during meta-device loading
from torchtune.models.llama3_1._position_embeddings import Llama3ScaledRoPE
for module in self.modules():
    if isinstance(module, Llama3ScaledRoPE) and not module.is_cache_built:
        module.rope_init()
        module.to(device)
```

**Patch 2 — HeartCodec loading fix** (in `src\heartlib\pipelines\music_generation.py`):
Add `ignore_mismatched_sizes=True` to **both** `HeartCodec.from_pretrained()` calls:
1. In `__init__` (eager load block)
2. In the `codec` property (lazy load block)

**Example for property `codec`:**
```python
self._codec = HeartCodec.from_pretrained(
    self.codec_path,
    device_map=self.codec_device,
    dtype=self.codec_dtype,
    ignore_mismatched_sizes=True,
)
```

### 5. Create Streamlit UI
See `templates/streamlit_heartmula_app.py` in the heartmula skill for starter code. Place in:
```
D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation\app.py
```

Run with:
```powershell
cd D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation
.venv\Scripts\activate
streamlit run app.py
```

## Project Layout
```
D:\AI_Ecosystem\
├── 09_Tools\heartlib\           # HeartMuLa installation
│   ├── src\heartlib\pipelines\music_generation.py
│   ├── ckpt\                      # Downloaded models
│   └── .venv\                     # Python env
├── 10_Projects\01_YTAutomation\Music_creation\
│   ├── app.py                     # Streamlit UI
│   ├── heartmula_bridge.py      # Wrapper import
│   ├── output\                    # Generated MP3s
│   └── .streamlit\config.toml   # UI theme
└── Arranque.txt                   # Master startup guide (section 8.5)
```

## Key Paths for VM Access
- VM mounts Windows drive at: `/mnt/ai`
- HeartMuLa source: `/mnt/ai/09_Tools/heartlib/`
- Music project: `/mnt/ai/10_Projects/01_YTAutomation/Music_creation/`

## Instrumental / Ambient Settings
| Parameter | Value | Why |
|---|---|---|
| `--temperature` | 1.0 | Smooth, consistent texture |
| `--cfg_scale` | 1.2-1.5 | Less aggressive guidance |
| `--topk` | 25-50 | Predictable soundscapes |
| `--lazy_load` | true | Essential for RTX 4060 Ti |
| Lyrics | Empty or minimal | Less lyrics = more ambient |
| Tags | `piano,ambient,relaxing,nature,soft,meditation,calm` | Mood match |

## Looping for 8h
Generate multiple 4-minute clips, then concatenate:
```powershell
# After generating N clips in output\ folder
ffmpeg -f concat -safe 0 -i files.txt -acodec libmp3lame -q:a 2 ambient_8h.mp3
```
Where `files.txt` lists each clip path with `file '...'` prefix.

## Gotchas
- **Python 3.10 ONLY** — pinned `torch==2.4.1` breaks on 3.11+
- **Tab vs Spaces** — if editing on Windows, check `music_generation.py` uses spaces for indent (tabs cause `IndentationError`)
- **HF CLI** — use `hf` not `huggingface-cli` for downloads
- **VRAM peak** — 3B model peaks at ~6.2GB with lazy_load, ~12GB without
- **Triton unavailable** on Windows — expect slower generation than Linux, but still usable
