---
name: heartmula
description: "HeartMuLa: Suno-like song generation from lyrics + tags."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [music, audio, generation, ai, heartmula, heartcodec, lyrics, songs]
    related_skills: [audiocraft]
---

# HeartMuLa - Open-Source Music Generation

## Overview
HeartMuLa is a family of open-source music foundation models (Apache-2.0) that generates music conditioned on lyrics and tags, with multilingual support. Generates full songs from lyrics + tags. Comparable to Suno for open-source. Includes:
- **HeartMuLa** - Music language model (3B/7B) for generation from lyrics + tags
- **HeartCodec** - 12.5Hz music codec for high-fidelity audio reconstruction
- **HeartTranscriptor** - Whisper-based lyrics transcription
- **HeartCLAP** - Audio-text alignment model

## When to Use
- User wants to generate music/songs from text descriptions
- User wants an open-source Suno alternative
- User wants local/offline music generation
- User asks about HeartMuLa, heartlib, or AI music generation

## Hardware Requirements
- **Minimum**: 8GB VRAM with `--lazy_load true` (loads/unloads models sequentially)
- **Recommended**: 16GB+ VRAM for comfortable single-GPU usage
- **Multi-GPU**: Use `--mula_device cuda:0 --codec_device cuda:1` to split across GPUs
- 3B model with lazy_load peaks at ~6.2GB VRAM

## Installation Steps

### 1. Clone Repository
```bash
cd ~/  # or desired directory
git clone https://github.com/HeartMuLa/heartlib.git
cd heartlib
```

### 2. Create Virtual Environment (Python 3.10 required)
```bash
uv venv --python 3.10 .venv
. .venv/bin/activate
uv pip install -e .
```

**Python version lock**: HeartMuLa requires Python 3.10 exactly. Do not use 3.11+ — the pinned `torch==2.4.1` and `torchtune` dependencies are not compatible. On Windows, if the machine has 3.14 installed, the `--python 3.10` flag above tells `uv` to download and use 3.10 automatically; otherwise install 3.10 from https://www.python.org/downloads/release/python-31011/ first.

### 3. Fix Dependency Compatibility Issues

**IMPORTANT**: As of Feb 2026, the pinned dependencies have conflicts with newer packages. Apply these fixes:

```bash
# Upgrade datasets (old version incompatible with current pyarrow)
uv pip install --upgrade datasets

# Upgrade transformers (needed for huggingface-hub 1.x compatibility)
uv pip install --upgrade transformers
```

### 4. Patch Source Code (Required for transformers 5.x)

**Patch 1 - RoPE cache fix** in `src/heartlib/heartmula/modeling_heartmula.py`:

In the `setup_caches` method of the `HeartMuLa` class, add RoPE reinitialization after the `reset_caches` try/except block and before the `with device:` block:

```python
# Re-initialize RoPE caches that were skipped during meta-device loading
from torchtune.models.llama3_1._position_embeddings import Llama3ScaledRoPE
for module in self.modules():
    if isinstance(module, Llama3ScaledRoPE) and not module.is_cache_built:
        module.rope_init()
        module.to(device)
```

**Why**: `from_pretrained` creates model on meta device first; `Llama3ScaledRoPE.rope_init()` skips cache building on meta tensors, then never rebuilds after weights are loaded to real device.

**Patch 2 - HeartCodec loading fix** in `src/heartlib/pipelines/music_generation.py`:

Add `ignore_mismatched_sizes=True` to ALL `HeartCodec.from_pretrained()` calls (there are 2: the eager load in `__init__` and the lazy load in the `codec` property).

**Why**: VQ codebook `initted` buffers have shape `[1]` in checkpoint vs `[]` in model. Same data, just scalar vs 0-d tensor. Safe to ignore.

### 5. Download Model Checkpoints

**Windows (PowerShell):**
```powershell
cd heartlib
hf download HeartMuLa/HeartMuLaGen --local-dir .\ckpt
hf download HeartMuLa/HeartMuLa-oss-3B-happy-new-year --local-dir .\ckpt\HeartMuLa-oss-3B
hf download HeartMuLa/HeartCodec-oss-20260123 --local-dir .\ckpt\HeartCodec-oss
```

**Linux/macOS:**
```bash
cd heartlib  # project root
hf download --local-dir './ckpt' 'HeartMuLa/HeartMuLaGen'
hf download --local-dir './ckpt/HeartMuLa-oss-3B' 'HeartMuLa/HeartMuLa-oss-3B-happy-new-year'
hf download --local-dir './ckpt/HeartCodec-oss' 'HeartMuLa/HeartCodec-oss-20260123'
```

Install `hf` CLI via: `uv pip install huggingface-hub`
Login if required: `hf auth login` (token from https://huggingface.co/settings/tokens)

All 3 can be downloaded in parallel. Total size is several GB.

## GPU / CUDA

HeartMuLa uses CUDA by default (`--mula_device cuda --codec_device cuda`). No extra setup needed if the user has an NVIDIA GPU with PyTorch CUDA support installed.

- The installed `torch==2.4.1` includes CUDA 12.1 support out of the box
- `torchtune` may report version `0.4.0+cpu` — this is just package metadata, it still uses CUDA via PyTorch
- To verify GPU is being used, look for "CUDA memory" lines in the output (e.g. "CUDA memory before unloading: 6.20 GB")
- **No GPU?** You can run on CPU with `--mula_device cpu --codec_device cpu`, but expect generation to be **extremely slow** (potentially 30-60+ minutes for a single song vs ~4 minutes on GPU). CPU mode also requires significant RAM (~12GB+ free). If the user has no NVIDIA GPU, recommend using a cloud GPU service (Google Colab free tier with T4, Lambda Labs, etc.) or the online demo at https://heartmula.github.io/ instead.

## Usage

### Generating with GUI instead of CLI

If the user prefers a web interface over command-line, create a **Streamlit** wrapper that provides a form-based UI:

Key components:
1. **Presets dropdown** (e.g., "Rain Forest", "Sunset Beach", "Night Meditation")
2. **Text areas** for Intro, Verses, Chorus, Outro (auto-populated from preset)
3. **Tags multiselect/checkboxes** with sensible defaults for ambient music
4. **Duration slider** (1–4 minutes)
5. **Progress bar + live log** showing model loading / generation status
6. **Audio player + download button** for the generated MP3
7. **Gallery** of previously generated tracks

Template starter file: see `templates/streamlit_heartmula_app.py` in this skill.
```bash
cd heartlib
. .venv/bin/activate
python ./examples/run_music_generation.py \
  --model_path=./ckpt \
  --version="3B" \
  --lyrics="./assets/lyrics.txt" \
  --tags="./assets/tags.txt" \
  --save_path="./assets/output.mp3" \
  --lazy_load true
```

### Input Formatting

**Tags** (comma-separated, no spaces):
```
piano,happy,wedding,synthesizer,romantic
```
or
```
rock,energetic,guitar,drums,male-vocal
```

**Lyrics** (use bracketed structural tags):
```
[Intro]

[Verse]
Your lyrics here...

[Chorus]
Chorus lyrics...

[Bridge]
Bridge lyrics...

[Outro]
```

### Key Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `--max_audio_length_ms` | 240000 | Max length in ms (240s = 4 min) |
| `--topk` | 50 | Top-k sampling |
| `--temperature` | 1.0 | Sampling temperature |
| `--cfg_scale` | 1.5 | Classifier-free guidance scale |
| `--lazy_load` | false | Load/unload models on demand (saves VRAM) |
| `--mula_dtype` | bfloat16 | Dtype for HeartMuLa (bf16 recommended) |
| `--codec_dtype` | float32 | Dtype for HeartCodec (fp32 recommended for quality) |

### Performance
- RTF (Real-Time Factor) ≈ 1.0 — a 4-minute song takes ~4 minutes to generate
- Output: MP3, 48kHz stereo, 128kbps

## Pitfalls
1. **Do NOT use bf16 for HeartCodec** — degrades audio quality. Use fp32 (default).
2. **Tags may be ignored** — known issue (#90). Lyrics tend to dominate; experiment with tag ordering.
3. **Triton not available on macOS** — Linux/CUDA only for GPU acceleration.
4. **RTX 5080 incompatibility** reported in upstream issues.
5. **Patching: watch for `self._codec` vs `self.codec`** — the lazy-load property must assign to `self._codec` (the private backing field), not `self.codec` (the property setter), or it will recurse infinitely.
6. **Indentation: use spaces, not tabs** — `music_generation.py` uses spaces; inserting tabs (e.g. via Windows editors) causes `IndentationError` at runtime.
7. The dependency pin conflicts require the manual upgrades and patches described above.

## Ambient / Long-Duration Generation
Since HeartMuLa is limited to ~4 minutes per generation, use it as a **clip factory** for long ambient/meditation tracks:

1. **Generate multiple 4-minute clips** with matching prompts (e.g. "piano ambient relaxing meditation calm strings")
2. Maintain matching tags across clips for consistent instrumentation/mood.
3. **Concatenate with seamless crossfade** using ffmpeg:
   ```bash
   # Simple crossfade between two clips
   ffmpeg -i clip1.mp3 -i clip2.mp3 -filter_complex "acrossfade=d=10" output.mp3
   ```
4. **Loop-friendly:** For ambient, aim for low CFG scale (~1.2-1.5), temperature 1.0, and minimal lyrics (or none) to get non-intrusive texture.

## Support Files

- **`references/windows-install.md`** — Windows step-by-step setup (PowerShell, manual patches, demo inputs, troubleshooting). Created in session 2026-05-26 to capture full Windows host installation path.
- **`templates/streamlit_heartmula_app.py`** — Streamlit starter UI wrapping the CLI. Drop this into the `Music_creation` project directory and run `streamlit run app.py`. Provides presets, live log, progress bar, audio player, and download.
| Parameter | Recommended | Why |
|---|---|---|
| `--max_audio_length_ms` | 240000 | Maximum clip duration (4 min) |
| `--temperature` | 1.0 | Keeps smoothness; 1.2+ introduces variety but may get busy |
| `--cfg_scale` | 1.2-1.5 | Lower = more ambient drift, less aggressive adherence|
| `--topk` | 25-50 | Lower for more predictable soundscapes |
| `--lazy_load` | true | Essential if VRAM is tight (e.g. RTX 4060 Ti) |
| Tags | `piano,ambient,relaxing,nature,soft,meditation,calm,strings,drone` | Instrumentation/mood |
| Lyrics | Minimal, only `[Intro]` + few lines | Less lyrics = more ambient/less lyrical |

### Windows GPU Installation
For step-by-step installation on Windows (PowerShell, manual patches, demo inputs), see `references/windows-install.md`.

## Links
- Repo: https://github.com/HeartMuLa/heartlib
- Models: https://huggingface.co/HeartMuLa
- Paper: https://arxiv.org/abs/2601.10547
- License: Apache-2.0
