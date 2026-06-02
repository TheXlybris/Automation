# ComfyUI-MusicGen Audio Generation Integration

## Purpose
Generate ambient/background music loops via MusicGen within ComfyUI, then concatenate into long (8-hour) tracks with ffmpeg crossfade. Music feeds audio-reactive visuals in TouchDesigner.

## Prerequisites
- ComfyUI running with `--listen 0.0.0.0 --port 8188`
- Windows firewall rule open on TCP 8188
- Custom node: `ComfyUI-MusicGen-HF` (clone + pip install into ComfyUI's Python, NOT global Python)
- ffmpeg installed for concatenation

## Custom Node Install (CRITICAL: python_embeded)

The custom node must be cloned into `ComfyUI/custom_nodes/`, and its dependencies installed into **ComfyUI's own Python environment** — never global system Python.

```cmd
cd D:\AI_Ecosystem\02_Engines\ComfyUI\ComfyUI\custom_nodes
git clone https://github.com/ebrinz/ComfyUI-MusicGen-HF.git

# Option A: ComfyUI portable (Windows) with python_embeded
cd ComfyUI-MusicGen-HF
D:\AI_Ecosystem\02_Engines\ComfyUI\python_embeded\python.exe -m pip install -r requirements.txt

# Option B: ComfyUI with system Python / venv
# First activate the venv, then:
pip install -r requirements.txt
```

Dependencies: `transformers>=4.30.0`, `accelerate>=0.20.0`, `scipy>=1.10.0`, `torch>=2.0.0`, `torchaudio>=2.0.0`, `av>=15.0.0`

### Missing Node Types diagnosis

If ComfyUI UI reports "Missing Node Types" and the "Install Missing Custom Nodes" button does NOT list `ComfyUI-MusicGen-HF`, the **Python import is failing during ComfyUI startup** — the folder exists but its dependencies can't be imported in the Python environment ComfyUI is running from.

Diagnosis:
1. Check ComfyUI console/logs for `ImportError` or `ModuleNotFoundError` during startup
2. Verify from the exact Python that runs ComfyUI:
   ```cmd
   D:\AI_Ecosystem\02_Engines\ComfyUI\python_embeded\python.exe -c "import torch; import transformers; import torchaudio; print('OK')"
   ```
3. Reinstall any missing package into the same Python

**Class types ARE case-sensitive:** `HuggingFaceMusicGen` and `SaveAudioStandalone` must be exact. Names like `MusicGenHF` or `SaveAudio` are wrong and cause "Missing Node Types".

## Workflow Structure (API JSON)

### Minimal single-track workflow

```json
{
  "1": {
    "inputs": {
      "model_size": "small",
      "duration": 10.0,
      "guidance_scale": 3.0,
      "do_sample": true,
      "max_new_tokens": 256,
      "seed": 42,
      "prompt": "ambient thunderstorm, rain on leaves, gentle rolling thunder, seamless loop",
      "temperature": 1.0,
      "duration_override": 0.0
    },
    "class_type": "HuggingFaceMusicGen"
  },
  "2": {
    "inputs": {
      "audio": ["1", 0],
      "filename_prefix": "track_ambient",
      "format": "wav",
      "quality": "320k"
    },
    "class_type": "SaveAudioStandalone"
  }
}
```

**NO Stable Diffusion nodes** (Checkpoint, KSampler, etc.) should be mixed in.

### Parameter reference for `HuggingFaceMusicGen`

| Input | Type | Range | Default | Notes |
|-------|------|-------|---------|-------|
| `model_size` | string | "small", "medium", "large" | "small" | Small = ~3GB, fastest, max ~10s stable |
| `duration` | float | 1.0–120.0 | 10.0 | >10s progressively less stable for small |
| `guidance_scale` | float | 1.0–10.0 | 3.0 | 2.5–3.5 is sweet spot for ambient |
| `do_sample` | boolean | true/false | true | Must be true for music generation |
| `max_new_tokens` | int | 64–2048 | 256 | 256 is stable for 10s; increase for longer |
| `seed` | int | 0–2^32 | 0 | 0 = random; use specific seeds for reproducibility |
| `prompt` | string | Any text | "" | Text description of desired audio |
| `temperature` | float | 0.5–2.0 | 1.0 | 0.8–1.2 recommended for ambient |
| `duration_override` | float | 0.0–120.0 | 0.0 | 0 = use `duration`; non-zero overrides |
| `conditioning_audio` | audio | Optional | None | Leave omitted for pure text-to-music |

### Editor format vs API format

- **API format** (`id: {inputs, class_type}`): for scripts, curl, direct `/api/prompt` submission
- **Editor format** (`nodes[]` + `links[]` with `type` field): for opening in ComfyUI's web UI

Store API-format workflows in `03_Workflows\API\`. Editor-format workflows must be built graphically in the UI and saved from there.

## 8-Hour Track Strategy

MusicGen Small is practically limited to ~10 seconds of stable generation per call. For 8 hours (28,800 seconds):

1. Generate 2,880 clips of 10 seconds each
2. Vary seeds (sequential or random) to avoid repetition
3. Rotate 3–5 prompts for variety (Thunderstorm → Beach → Forest → Desert → Rain Café)
4. Concatenate with ffmpeg:

```bash
# Simple concat (no crossfade)
for f in clip_*.wav; do echo "file '$f'" >> files.txt; done
ffmpeg -f concat -safe 0 -i files.txt -c copy output_raw.wav

# Normalize volume
ffmpeg -i output_raw.wav -af loudnorm output_norm.wav

# Convert to MP3 320k
ffmpeg -i output_norm.wav -b:a 320k output_8h.mp3
```

5. Optional crossfade between clips (computationally expensive for 2,880 clips):
   ```bash
   ffmpeg -i clip1.wav -i clip2.wav -filter_complex "[0:a][1:a]acrossfade=d=0.5:c1=tri:c2=tri" out.wav
   ```

## Audio Output Verification

After generation, verify WAV integrity with ffprobe:
```bash
ffprobe -v quiet -print_format json -show_streams output.wav
# Expected: codec=pcm_s16le, sample_rate=32000 Hz, channels=2, duration~9.94s

# Volume analysis
ffmpeg -i output.wav -af "volumedetect" -f null /dev/null 2>&1 | grep -E "mean_volume|max_volume"
# Expected: mean ~-15.5 dB, max ~-3.5 dB (no clipping)

# Silence detection
ffmpeg -i output.wav -af "silencedetect=noise=-50dB:d=0.1" -f null /dev/null 2>&1 | grep "silence_"
# Expected: none (continuous audio)
```

Verified outputs: WAV, 32000 Hz, 2 channels (stereo), PCM s16le, ~1024 kbps, duration ~9.94s for 10s requested. Volume: mean -15.5 to -15.8 dB, max -3.5 dB.

## Prompts for Ambient Scenes

| Scene | Prompt |
|-------|--------|
| Thunderstorm | ambient thunderstorm, distant rolling thunder, rain on leaves, atmospheric pads, seamless loop |
| Beach Waves | gentle beach waves, ocean surf, seagulls distance, wind chimes, tropical ambient, seamless loop |
| Forest Morning | peaceful forest, birds chirping, gentle breeze, soft piano, relaxing ambient |
| Desert Night | desert night, wind through dunes, distant coyotes, warm ambient pads |
| Rain Café | cozy café, rain against window, soft jazz piano, fireplace crackling |

## Pitfalls
- `max_new_tokens` > 512 with small model may crash or produce silence
- First run downloads ~3GB model from HuggingFace automatically
- `#` appended to end of `.env` values (e.g. `VAR=val#`) causes silent parser failure in gateway
- Conditioning audio input is optional; omit entirely for pure text-to-music
- ComfyUI-MusicGen-HF has NO SD nodes (Checkpoint, KSampler) — mixing them breaks the workflow
- Firewall must allow TCP 8188 for VM-to-host remote control
- ComfyUI must be started with `--listen 0.0.0.0` to accept connections from LAN

## Files
- Workflow JSON (API): `D:\AI_Ecosystem\03_Workflows\API\MusicGen_Ambient_Loops.json`
- Script: `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation\run_musicgen.py`
- Docs: `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation\README_MusicGen_Workflow.md`
- See `comfyui` skill `references/audio-workflows.md` for full parameter reference
