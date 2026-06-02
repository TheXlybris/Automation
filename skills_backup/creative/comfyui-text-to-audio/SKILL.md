---
name: comfyui-text-to-audio
description: "Text-to-audio music generation with ComfyUI — ACE Step v1.5, MusicGen-HF, and batch-to-longform strategies (e.g. 8h ambient tracks). Complements the 'comfyui' skill with T2A-specific workflows, model locations, and automation patterns."
version: 1.0.0
author: xlybris-agent
license: MIT
platforms: [windows, linux]
compatibility: "Requires ComfyUI ≥0.3.34 (for ACE Step native nodes) or custom_nodes/ComfyUI-MusicGen-HF (legacy)."
prerequisites:
  commands: ["python3", "ffmpeg"]
metadata:
  hermes:
    tags:
      - comfyui
      - text-to-audio
      - music-generation
      - ambient
      - ace-step
      - batch-generation
    related_skills: [comfyui]
    category: creative
---

# ComfyUI Text-to-Audio

Generate music and ambient audio via ComfyUI using native diffusion models (ACE Step) or custom-node pipelines (MusicGen-HF). This skill covers model setup, workflow modification for instrumental/ambient prompts, and the batch-to-longform strategy needed for multi-hour tracks.

## When to Use

- User wants to generate music/ambient audio from text prompts in ComfyUI
- User needs instrumental (no vocals) or ambient soundscapes
- Target duration is longer than a single model generation (e.g. 8 hours)
- User is deciding between ACE Step (native) vs MusicGen-HF (custom node)
- User needs to batch-generate clips and concatenate them with ffmpeg

## Architecture: Two T2A Paths in ComfyUI

| Path | Model | Node Source | Max per Generation | Speed | Quality |
|------|-------|-------------|-------------------|-------|---------|
| **ACE Step v1.5** (recommended) | `acestep_v1.5_xl_*_bf16` | Native ComfyUI core (≥0.3.34) | ~120 seconds | Fast (turbo=8 steps) | Excellent |
| **MusicGen-HF** (legacy) | `facebook/musicgen-small` | Custom node `ComfyUI-MusicGen-HF` | ~10 seconds | Medium | Good |

**Default recommendation:** ACE Step v1.5 XL Turbo for any new project. It is native (no custom node install), generates longer clips per call, and runs faster.

## ACE Step v1.5 — Native ComfyUI T2A

### Built-in Templates

ComfyUI ships with built-in workflow templates under its python_embeded package:

```
python_embeded/Lib/site-packages/comfyui_workflow_templates_media_other/
  audio_ace_step1_5_xl_base.json     # 50 steps, CFG 6
  audio_ace_step1_5_xl_turbo.json    # 8 steps, CFG 1  ← RECOMMENDED
  audio_ace_step1_5_xl_sft.json      # 50 steps, CFG 7
```

These are in **Editor format** (`nodes[]` + `links[]`) — load them in the ComfyUI UI via `Workflow → Open`, then re-export to API format via `Workflow → Export (API)` for automation.

Also in the older template folder:
```
comfyui_workflow_templates_media_image/
  audio_ace_step_1_t2a_instrumentals.json  # v1, all-in-one 3.5B checkpoint
  audio_ace_step_1_t2a_song.json           # v1, with lyrics
```

### Models Required (Split-File Layout)

| File | Size | Destination Folder | HuggingFace URL |
|------|------|-------------------|-----------------|
| `acestep_v1.5_xl_turbo_bf16.safetensors` | ~5.7 GB | `models/diffusion_models/` | `Comfy-Org/ace_step_1.5_ComfyUI_files/split_files/diffusion_models/` |
| `acestep_v1.5_xl_base_bf16.safetensors` | ~5.7 GB | `models/diffusion_models/` | Same repo, `base` variant |
| `acestep_v1.5_xl_sft_bf16.safetensors` | ~5.7 GB | `models/diffusion_models/` | Same repo, `sft` variant |
| `ace_1.5_vae.safetensors` | ~300 MB | `models/vae/` | Same repo, `vae/` |
| `qwen_0.6b_ace15.safetensors` | ~1.2 GB | `models/text_encoders/` | Same repo, `text_encoders/` |
| `qwen_4b_ace15.safetensors` | ~8.5 GB | `models/text_encoders/` | Same repo, `text_encoders/` |

**Note:** The template `audio_ace_step1_5_xl_turbo.json` uses `ModelSamplingAuraFlow` with `multiplier=3` instead of `ModelSamplingSD3`.

### Workflow Nodes (ACE Step 1.5)

| Node | `class_type` | Purpose |
|------|-------------|---------|
| `UNETLoader` | Load diffusion model | `model` = `acestep_v1.5_xl_*_bf16.safetensors` |
| `VAELoader` | Load VAE | `vae_name` = `ace_1.5_vae.safetensors` |
| `DualCLIPLoader` | Load text encoders | `clip_name1` = `qwen_0.6b_ace15`, `clip_name2` = `qwen_4b_ace15`, `type` = `ace` |
| `EmptyAceStep1.5LatentAudio` | Create audio latent | `seconds` = duration, `batch_size` = 1 |
| `TextEncodeAceStepAudio1.5` | Encode prompt | `style_keywords`, `lyrics_or_structure`, `seed`, `duration`, `language`, `key`, `use_structure`, `cfg` |
| `KSampler` | Diffusion sampling | `steps`, `cfg`, `sampler_name`, `scheduler` |
| `VAEDecodeAudio` | Decode to audio | Outputs `AUDIO` |
| `SaveAudioMP3` | Export MP3 | `filename_prefix`, `format` |

### Prompting for Instrumental Ambient — CRITICAL RULES

ACE Step has two prompt inputs: **`tags`** (style/keywords) and **`lyrics`** (structure/lyrics).

**For instrumental ambient music:**

1. **Lyrics field MUST be ONLY `[instrumental]`** — nothing else.
2. **ALL scene descriptions go into `tags`** — instruments, atmosphere, nature, tempo, mood, etc.
3. **NEVER use structural markers in `lyrics`** — `[Verse]`, `[Chorus]`, `[Bridge]`, `[rain]`, `[thunder]`, or any bracketed text triggers unwanted vocal synthesis (the model tries to "sing" the line).
4. **`generate_audio_codes`**: set `True` even though lyrics = `[instrumental]` — this enables the model's musical interpretation of the tags.

#### Good Example
```yaml
tags: |
  ambient instrumental, soft atmospheric pads, gentle rain on leaves,
  distant low thunder rumble, wind rustling through pine trees,
  nature soundscape, no vocals, no lyrics, relaxing meditation music,
  seamless loop, slow tempo, 60 BPM
lyrics: "[instrumental]"
```

#### Bad Example — DO NOT DO THIS
```yaml
# WRONG: structural markers in lyrics trigger vocal synthesis
lyrics: |
  [intro — soft rain and distant thunder]
  [verse 1 — gentle ambient pads, low drone]
  [chorus — fuller texture, subtle wind chimes]
  [bridge — rain intensifies, thunder rolls closer]
  [outro — fade to silence]
# Result: last half of the clip will have unexpected "singing" / vocal artifacts

# WRONG: using tags only, no lyrics field
lyrics: ""  # Empty field may cause model confusion

# WRONG: bracketed sound labels in any field  
tags: "[rain on leaves], [distant thunder]"  # Same trigger issue
```

### Duration Behavior Notes

- **Shorter clips (110s)** tend to include more percussion/structure (drums, bassline).
- **Longer clips (240s+)** may lose percussion — pads/drones become dominant.
- For ambient loop consistency, standardize around **110s** as the base clip length, then concatenate.
- Practical max per generation: ~240–300 seconds. Beyond this model behavior degrades (OOM risk, slower sampling, loss of rhythmic coherence).

### Key Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Structural markers in `lyrics` | Unexpected singing/vocals in final 30% of clip | Remove ALL bracketed markers; use ONLY `[instrumental]` |
| Empty `lyrics` field | Nonsensical output or hallucinated vocals | Explicitly set `lyrics: "[instrumental]"` |
| Tags too short (no duration cues) | MIDI-like piano fallback | Include tempo keywords like `60 BPM`, `slow tempo`, and instrument keywords |
| ComfyUI deduplicates identical workflows | Batch items 2+ return `0.00s` with no audio | Vary a real workflow input (e.g., duration `+0.01s` per item). `client_id` and `filename_prefix` do NOT prevent deduplication. Fix validated in production (2026-06-02): 3 items with unique `client_id` and `prefix` still deduplicated. Adding `jitter=round(idx * 0.01, 2)` to `duration` and `seconds` nodes resolved it — all 3 executed in ~40s each. |
| Batch with same seed | Identical-sounding clips | Vary seed per clip: `seed = base + i` |
| Duration > 120s on turbo | Percussion dropout or slower sampling | Use 110s as standard; concatenate for longform |
| `audioUI` field conflicts | Duplicate filename or UI hang | Leave `audioUI` empty string `""` in API workflows |

### Tags Preset Examples for Ambient

| Preset Name | BPM | Key | Tags (excerpt) |
|---|---|---|---|
| Rain & Thunder | 60 | A minor | atmospheric pads, rain on leaves, distant thunder, nature soundscape |
| Ocean Waves | 55 | E major | ocean waves on shore, soft sea breeze, coastal atmosphere, no vocals |
| Forest Wind | 50 | C major | wind rustling through pine trees, forest ambience, distant birdsong |
| Night Stars | 45 | D minor | deep space pads, starry night, cosmos atmosphere, soft synth drones |
| Heavy Rain Storm | 55 | G minor | heavy rain on rooftop, thunderstorm rumble, deep sub bass drone |
| Soft Morning | 65 | F major | soft morning light, gentle birdsong, warm analog pads, peaceful awakening |
| Fireplace | 50 | C major | warm fireplace crackle, cozy cabin, soft wooden creaks, warm amber feeling |
| Snowy Mountains | 40 | A minor | cold mountain wind, snow crunching, alpine silence, crystalline ice textures |

## MusicGen-HF — Legacy Custom Node

See `comfyui` skill `references/audio-workflows.md` for full MusicGen-HF documentation. **Only use this if ACE Step is unavailable** (older ComfyUI version).

- Custom node: `ComfyUI-MusicGen-HF` by ebrinz
- Max stable duration: ~10 seconds per call
- Requires separate install into `custom_nodes/`

## Batch-to-Longform Strategy (8-Hour Tracks)

No T2A model can generate 8 hours in one call. The strategy is:

1. **Generate clips**: 120s each (ACE Step) or 10s each (MusicGen)
2. **Vary seeds**: `seed = base_seed + i` for clip `i` to ensure diversity
3. **Rotate prompts**: 3–5 scene prompts cycled across clips
4. **Concatenate with ffmpeg**:

```bash
# Simple concat (no crossfade)
for f in clip_*.mp3; do echo "file '$f'" >> files.txt; done
ffmpeg -f concat -safe 0 -i files.txt -c copy output_raw.mp3

# With crossfade (smooth transitions between clips)
ffmpeg -i clip1.mp3 -i clip2.mp3 -filter_complex \
  "[0:a][1:a]acrossfade=d=2:c1=tri:c2=tri" out.mp3

# Normalize loudness (EBU R128)
ffmpeg -i output_raw.mp3 -af loudnorm output_norm.mp3

# Final MP3 320k
ffmpeg -i output_norm.mp3 -b:a 320k output_8h.mp3
```

5. **Do NOT use ComfyUI loop nodes** (`LoopingAudioPreview`, `SmoothAudioQueue`) for this scale — they run inside ComfyUI and cannot iterate thousands of times.

## Automation Pattern

For unattended batch generation:

1. Export workflow to **API format** (`Workflow → Export (API)`)
2. Use `comfyui` skill's `run_workflow.py` or `run_batch.py` with `--args '{"seed": -1, "prompt": "..."}'`
3. Set `--timeout 1800` (audio workflows auto-detect extended timeout)
4. After all jobs complete, run ffmpeg concat script

## Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Templates in Editor format | "Cannot open workflow" in API scripts | Load in UI, re-export to API format |
| Missing split-file models | "Model not found" or blank output | Download to correct subfolder (`diffusion_models/`, `vae/`, `text_encoders/`) |
| Wrong VAE for audio | Audio decode produces noise/static | Use `ace_1.5_vae.safetensors`, not an image VAE |
| Turbo with wrong sampler | Distorted or silent output | Turbo requires `ModelSamplingAuraFlow` + 8 steps + euler/simple |
| Duration too long | OOM, crash, or extremely slow generation | Reduce `seconds` to ≤120 (ACE Step) or ≤10 (MusicGen) |
| Batch seed collision | Clips sound identical | Use `seed = base + i` or `--randomize-seed` |
| ComfyUI version too old | ACE Step nodes not found | Update ComfyUI to ≥0.3.34 |

### Support Files

- `references/ace-step-model-downloads.md` — Direct HF download links for all model files
- `references/streamlit-comfyui-gui.md` — Streamlit GUI patterns for ComfyUI API control: presets with `session_state`, auto-polling for batch jobs with `time.sleep(2)+st.rerun()`, queue management buttons

## Streamlit GUI Pattern for ComfyUI API Control

When building a GUI for ComfyUI, prefer Streamlit over CLI (user explicitly prefers GUI for creative tools). Key patterns are documented in `references/streamlit-comfyui-gui.md`.

### Critical Rules

**Presets MUST use `st.session_state` + `on_change`:**
Streamlit widgets read `value` only on first render. Presets cannot update fields by changing Python variables — the change must flow through `session_state`.

```python
def apply_preset():
    p = st.session_state.get("preset_key", "(Custom)")
    if p in PRESETS:
        st.session_state.tags = PRESETS[p]["tags"]

preset = st.selectbox("Preset", options, key="preset_key", on_change=apply_preset)
tags = st.text_area("Tags", value=st.session_state.tags, key="tags_key")
```

**Auto-polling for batch: use `time.sleep(2) + st.rerun()` with completion checks:**
For sequential batch processing, auto-polling is required. Use `time.sleep(2)` between polls to avoid browser-flooding loops. Check ComfyUI job status before rerunning.

```python
if batch_running:
    if running_item:
        status = get_job_status(running_item["prompt_id"])
        if status["completed"]:
            st.rerun()  # advance to next
        else:
            time.sleep(2)
            st.rerun()  # check again in 2s
    elif pending_items:
        process_next_item()  # sends next clip
        time.sleep(1)
        st.rerun()
    else:
        st.success("Done!")
        batch_running = False
```

**NEVER use `while True` or very short sleeps without status gates.** Without `sleep(≥2)`, the browser refreshes in a tight loop and the UI becomes unresponsive.

### Verification Checklist for Streamlit GUIs

- [ ] Presets update fields via `session_state` + `on_change`
- [ ] No polling loops with `time.sleep()` — manual refresh only
- [ ] Each tab has unique `key` prefixes (t1_, t2_, etc.)
- [ ] `.bat` launcher uses ASCII-safe characters (no accents)
- [ ] Audio player wrapped in `try/except` to avoid file-lock crashes

## Verification Checklist for ACE Step Setup

- [ ] ComfyUI version ≥0.3.34 (for native ACE Step nodes)
- [ ] All 4 model files present in correct `models/` subfolders
- [ ] Workflow exported to API format (not Editor format)
- [ ] `check_deps.py` reports `is_ready: true`
- [ ] Test run: 30s clip generates successfully in under 5 minutes (turbo)
- [ ] ffmpeg installed for post-processing concatenation
