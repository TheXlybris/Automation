# Audio Generation Workflows in ComfyUI (AudioCraft / MusicGen)

Practical guide for generating music via ComfyUI when the agent runs on a VM and ComfyUI lives on a Windows host.

## Context

- Agent VM (Ubuntu, bridged to `192.168.0.188`) runs Hermes with no GPU.
- ComfyUI host (Windows with NVIDIA GPU) runs at `192.168.0.187:8188`.
- Windows firewall blocks port 8188 by default -- the VM cannot reach ComfyUI until the firewall opens.
- User keeps workflows in `D:\AI_Ecosystem\03_Workflows\API`.
- User keeps generated music in `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation`.

## Custom Node: ComfyUI-MusicGen-HF

Repository: `https://github.com/ebrinz/ComfyUI-MusicGen-HF`

### What it does
- Generates music from text prompts using Facebook's MusicGen (via Hugging Face)
- Model sizes: small (~3 GB), medium (~6 GB), large (~12 GB)
- Exports WAV, FLAC, MP3, Opus
- First run downloads `facebook/musicgen-small` (~3 GB)
- **Practical max duration per call: ~10 seconds** for `small`; ~30s theoretically, but >10s is progressively more unstable

### Nodes provided (CORRECT class_types)

| Node | `class_type` | Purpose |
|------|-------------|---------|
| HuggingFace MusicGen | `HuggingFaceMusicGen` | Main text-to-music generator |
| Save Audio Standalone | `SaveAudioStandalone` | Export generated audio to file |
| Load Audio | `LoadAudioStandalone` | Load audio for conditioning |
| BPM Duration Input | `BPMDurationInput` | Convert BPM+beats to seconds |
| Looping Audio Preview | `LoopingAudioPreview` | Preview with loop count |
| Smooth Audio Queue | `SmoothAudioQueue` | Crossfade chain |
| Professional Loop Transition | `ProfessionalLoopTransition` | Loop boundary smoother |
| Audio Output to Conditioning | `AudioOutputToConditioningQueue` | Feed output as conditioning |
| Conditioning Queue Manager | `ConditioningQueueManager` | Manage conditioning stack |

**CRITICAL:** `class_type` names ARE case-sensitive. `HuggingFaceMusicGen` and `SaveAudioStandalone` must be exact. Any misspelling (e.g. `MusicGenHF`) causes "Missing Node Types" error.

### Installation on Windows host (python_embeded of ComfyUI)

The custom node must be cloned into ComfyUI's `custom_nodes/` folder, and its Python dependencies installed into ComfyUI's **own** Python environment (not global Python, not system Python).

```cmd
cd D:\AI_Ecosystem\02_Engines\ComfyUI\ComfyUI\custom_nodes
git clone https://github.com/ebrinz/ComfyUI-MusicGen-HF.git
cd ComfyUI-MusicGen-HF

# IMPORTANT: Use ComfyUI's embedded Python, NOT global python
D:\AI_Ecosystem\02_Engines\ComfyUI\python_embeded\python.exe -m pip install -r requirements.txt
```

If ComfyUI runs with a system Python instead of `python_embeded`, then:
```bash
# Activate ComfyUI's venv first, then:
pip install -r requirements.txt
```

Dependencies from `requirements.txt`: `transformers>=4.30.0, accelerate>=0.20.0, scipy>=1.10.0, torch>=2.0.0, torchaudio>=2.0.0, av>=15.0.0`

### Missing Node Types even after install

If ComfyUI UI reports "Missing Node Types" and Install Missing Custom Nodes does NOT list MusicGen-HF, the **Python import is failing during startup** — the custom node folder exists but its dependencies can't import.

Diagnosis steps:
1. Check ComfyUI startup logs for Python `ImportError` or `ModuleNotFoundError`
2. Verify `torch`, `transformers`, `torchaudio`, `av`, `scipy`, `accelerate` are installed in the **same Python environment** that runs ComfyUI:
   ```cmd
   D:\AI_Ecosystem\02_Engines\ComfyUI\python_embeded\python.exe -c "import torch; import transformers; import torchaudio; print('OK')"
   ```
3. If any fails, reinstall them with pip inside that python_embeded

## Workflow JSON Structure

### API format (for scripts/curl)

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
      "prompt": "ambient thunderstorm, rain on leaves, distant rolling thunder, seamless loop",
      "temperature": 1.0,
      "duration_override": 0.0
    },
    "class_type": "HuggingFaceMusicGen"
  },
  "2": {
    "inputs": {
      "audio": ["1", 0],
      "filename_prefix": "thunderstorm_ambient",
      "format": "wav",
      "quality": "320k"
    },
    "class_type": "SaveAudioStandalone"
  }
}
```

**Parameter reference for `HuggingFaceMusicGen`:**

| Input | Type | Range / Values | Default | Notes |
|-------|------|---------------|---------|-------|
| `model_size` | string | "small", "medium", "large" | "small" | Small = ~3GB, fastest, max ~10s stable |
| `duration` | float | 1.0 – 120.0 | 10.0 | Duration in seconds. >10s progressively less stable for small |
| `guidance_scale` | float | 1.0 – 10.0 | 3.0 | Higher = more prompt adherence but less variation |
| `do_sample` | boolean | true/false | true | Enable sampling (must be true for music generation) |
| `max_new_tokens` | int | 64 – 2048 | 256 | Controls max generation length; 256 is fine for ~10s |
| `seed` | int | 0 – 2^32 | 0 | 0 = random. Use specific seed for reproducibility |
| `prompt` | string | Any text | "" | Text description of desired audio |
| `temperature` | float | 0.5 – 2.0 | 1.0 | Higher = more variation |
| `duration_override` | float | 0.0 – 120.0 | 0.0 | 0 = use `duration`. Non-zero overrides |
| `conditioning_audio` | audio | Optional | None | Audio to condition on (optional) |

### Editor format (for UI drag-and-drop)

When opening in ComfyUI's web UI, workflows must be in **Editor format** (`nodes[]` + `links[]` with `type` field per node). API format (`id: {inputs, class_type}`) does NOT open directly in the UI — it only works via `/api/prompt`.

To convert: Load API JSON in ComfyUI, then "Export (API)" will NOT give editor format. Instead, build the workflow graphically in the UI, then "Save" to get editor format `.json`.

**Rule:**
- Files in `03_Workflows\API\` → API format (for scripts, automation, direct POST)
- Files in UI → Editor format (nodes[] + links[] with type)
- Same functional workflow, different JSON shape

## 8-Hour Track Strategy

MusicGen Small is limited to ~10 seconds per stable generation. For 8 hours:

1. Generate 2,880 clips of 10 seconds each (varying seeds for diversity)
2. Use 3-5 different scene prompts rotated
3. Concatenate with ffmpeg crossfade (0.5s each):
   ```bash
   # Create file list
   for f in clip_*.wav; do echo "file '$f'" >> files.txt; done
   # Concatenate (simple, no crossfade)
   ffmpeg -f concat -safe 0 -i files.txt -c copy output_raw.wav
   # Normalize volume
   ffmpeg -i output_raw.wav -af loudnorm output_norm.wav
   # Convert to MP3 320k
   ffmpeg -i output_norm.wav -b:a 320k output_8h.mp3
   ```

4. For crossfade between clips:
   ```bash
   ffmpeg -i clip1.wav -i clip2.wav -filter_complex "[0:a][1:a]acrossfade=d=0.5:c1=tri:c2=tri" out.wav
   ```

**Do NOT rely on ComfyUI nodes** (`LoopingAudioPreview`, `SmoothAudioQueue`) for 8-hour generation — they run within ComfyUI and cannot scale to thousands of iterations. Export individual WAVs and post-process with ffmpeg.

## VM-to-Host Execution Pattern

When Windows firewall blocks port 8188, the agent has three fallback options:

### Option A: Open Windows Firewall (allows remote control)

PowerShell as Admin:
```powershell
netsh advfirewall firewall add rule name="ComfyUI" dir=in action=allow protocol=tcp localport=8188
```

Start ComfyUI with public listen:
```cmd
python main.py --listen 0.0.0.0 --port 8188
```

Then VM agent can POST workflows directly:
```bash
curl -X POST http://192.168.0.187:8188/api/prompt -H "Content-Type: application/json" -d @workflow.json
```

### Option B: Generate workflow JSON on VM, open manually on host

1. Agent creates the .json in VM via write_file
2. Copy via shared folder to `D:\AI_Ecosystem\03_Workflows\API\`
3. User opens in ComfyUI -> Workflow -> Open (API)
4. User clicks Queue Prompt
5. Output goes to ComfyUI's output folder

### Option C: Execute entirely on Windows via ComfyUI Manager's built-in nodes

Install ComfyUI-Manager and use its queue commands from within the UI. No VM scripting needed.

## Prompts for Ambient Scenes

| Scene | Prompt |
|-------|--------|
| Thunderstorm | ambient thunderstorm, distant rolling thunder, rain on leaves, atmospheric pads, seamless loop |
| Beach Waves | gentle beach waves, ocean surf, seagulls distance, wind chimes, tropical ambient, seamless loop |
| Forest Morning | peaceful forest, birds chirping, gentle breeze, soft piano, relaxing ambient | 
| Desert Night | desert night, wind through dunes, distant coyotes, warm ambient pads |
| Rain Café | cozy café, rain against window, soft jazz piano, fireplace crackling |

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Wrong class_type | "Missing Node Types" but install button empty | Use exact `HuggingFaceMusicGen` / `SaveAudioStandalone` (case-sensitive) |
| Dependencies missing in python_embeded | Node fails at import during ComfyUI startup; not listed in Manager | Install `torch`, `transformers`, `torchaudio`, `av`, `scipy`, `accelerate` into ComfyUI's python_embeded |
| Model download hangs | Node stalls, no output after 60s | Check internet; models are ~3GB, can take time on slow connections |
| Firewall blocks | Connection timed out from VM | Open port 8188 on Windows firewall; run ComfyUI with `--listen 0.0.0.0` |
| Duration too long | OOM, distorted audio, or extremely slow | Reduce duration to 10s (small model). Generate short clips and concatenate externally |
| API format in UI | "Cannot open workflow" or blank canvas | Save workflow from ComfyUI UI (Editor format, nodes[] + links[]) for UI use |
| Editor format via API | "class_type not found" or validation error | Use API format (id: {inputs, class_type}) for `/api/prompt` submissions |
| Missing conditioning_audio | Node has optional audio input; can be left empty | Simply omit the `conditioning_audio` key from inputs |

## Audio Output Analysis (ffprobe)

After generation, verify WAV integrity:
```bash
ffprobe -v quiet -print_format json -show_streams output.wav
# Expected: codec=pcm_s16le, sample_rate=32000 Hz, channels=2, duration=~10s

ffmpeg -i output.wav -af "volumedetect" -f null /dev/null 2>&1 | grep -E "mean_volume|max_volume"
# Expected mean_volume around -15 dB, max_volume around -3 dB
```

## Long-Duration Generation Script Pattern

For automation, use a Python script that:
1. Loops N times, each with `seed += 1`
2. Submits workflow to ComfyUI API
3. Waits for each prompt_id to complete
4. Downloads output WAV to local directory
5. After all loops finish, runs ffmpeg concat

See `render-wave-image-generator` skill `references/musicgen-integration.md` for a full reference implementation.
