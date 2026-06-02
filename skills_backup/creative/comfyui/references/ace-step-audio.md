# ACE Step 1.5 Audio Generation in ComfyUI

Native text-to-audio model built into ComfyUI core (Comfy-Org). No custom nodes required.

## Models

| Model | Size | Folder | HF URL |
|-------|------|--------|--------|
| `acestep_v1.5_xl_turbo_bf16.safetensors` | ~5.7 GB | `models/diffusion_models/` | `Comfy-Org/ace_step_1.5_ComfyUI_files/.../diffusion_models/` |
| `acestep_v1.5_xl_base_bf16.safetensors` | ~5.7 GB | `models/diffusion_models/` | same repo |
| `acestep_v1.5_xl_sft_bf16.safetensors` | ~5.7 GB | `models/diffusion_models/` | same repo |
| `ace_1.5_vae.safetensors` | ~300 MB | `models/vae/` | same repo |
| `qwen_0.6b_ace15.safetensors` | ~1.2 GB | `models/text_encoders/` | same repo |
| `qwen_4b_ace15.safetensors` | ~8.5 GB | `models/text_encoders/` | same repo |

## Variants

| Variant | Steps | CFG | Speed | Use case |
|---------|-------|-----|-------|----------|
| **Turbo** | 8 | 1.0 | Fast (~1-2 min/clip) | Batch ambient generation |
| Base | 50 | 6.0 | Slow (~5-10 min) | Maximum quality |
| SFT | 50 | 7.0 | Slow | Tuned quality |

## Workflow Nodes

### TextEncodeAceStepAudio1.5
Main conditioning node. Parameters:

| Param | Type | Default | Range | Notes |
|-------|------|---------|-------|-------|
| `tags` | string | "" | Any text | Style/genre descriptors |
| `lyrics` | string | "" | Any text | `[instrumental]` for no vocals |
| `seed` | int | 0 | 0 - 2^64 | 0 = random |
| `bpm` | int | 120 | 10 - 300 | Slow = 45-65 for ambient |
| `duration` | float | 120.0 | 0.0 - 2000.0 | Seconds per generation |
| `timesignature` | combo | "4" | 2,3,4,6 | Keep "4" |
| `language` | combo | "en" | en,ja,zh,es,... | Prompt language |
| `keyscale` | combo | "C major" | Any root + major/minor | A minor = dark |
| `generate_audio_codes` | bool | true | true/false | Keep true for quality |
| `cfg_scale` | float | 2.0 | 0.0 - 100.0 | 1.5-2.0 for ambient |
| `temperature` | float | 0.85 | 0.0 - 2.0 | Lower = more predictable |
| `top_p` | float | 0.9 | 0.0 - 2000.0 | Keep 0.9 |
| `top_k` | int | 0 | 0 - 100 | Keep 0 |
| `min_p` | float | 0.0 | 0.0 - 1.0 | Keep 0 |

### EmptyAceStep1.5LatentAudio
Creates latent space for audio. Inputs:
- `seconds` — MUST match TextEncode `duration` (manually, no auto-link in simplified workflows)
- `batch_size` — 1 typical

### Other nodes in chain
- `UNETLoader` — loads diffusion model
- `VAELoader` — loads ace_1.5_vae
- `DualCLIPLoader` — loads both Qwen encoders (type=ace)
- `ModelSamplingAuraFlow` — shift multiplier (Turbo: 3.0)
- `ConditioningZeroOut` — negative conditioning (no user input needed)
- `KSampler` — Turbo: 8 steps, CFG 1.0, euler/simple
- `VAEDecodeAudio` — decodes to AUDIO
- `SaveAudioMP3` — exports MP3 320k

## Instrumental / No-Vocals Configuration

**Tags:** Must NOT contain "vocals", "singing", "rap", "voice", "lyrics", "choir". Use:
```
ambient instrumental, [scene descriptors], no vocals, no lyrics, seamless loop
```

**Lyrics:** Use ONLY:
```
[instrumental]
```
Do NOT use `[Verse]`, `[Chorus]`, `[Bridge]` — these trigger structural song generation with voice synthesis.

## Critical Pitfalls

### 1. Fade-out tendency at ~110s and longer durations
The ACE Step model has an internal tendency to fade out around 110 seconds. **However, longer durations (e.g. `duration=240.0` for 4 minutes) do generate successfully** — the fade is an audio characteristic within the clip, not a hard latent-space cutoff. For cleanest ambient loops, 110s clips concatenated via ffmpeg crossfade remain the recommended approach.

**Workarounds:**
- For cleanest loops: set `duration=110.0` in both TextEncode and EmptyLatent, then concatenate with ffmpeg crossfade
- For single long tracks: use `duration=240.0` or higher, then normalize levels in post-processing if the gradual fade is audible
- The fade cannot be fully prevented via prompts alone

### 1b. Duration changes restructure the audio (not just extend it)
Increasing `duration` from 110s to 240s does not simply append more seconds of the same style. The model generates a **different structural composition** — a 240s clip may lack percussion/groove elements that were present throughout a 110s clip with identical tags/seed/BPM/key. If a specific element (e.g., rhythmic percussion, melodic progression) is required for continuity across a batch, **shorter clips (110s) concatenated via ffmpeg crossfade are more reliable** than a single long generation.

**Rule:** For stylistic consistency in multi-clip batches, prefer `duration=110.0` with varied seeds over `duration=240.0`.

### 1c. Silence padding at start and end of clips
ACE Step Turbo output often contains **abysmal silence at the beginning and end** of generated clips. This is inherent model behavior, not a configuration error.

**Workaround:** Use FFmpeg `silenceremove` filter in post-processing:
```bash
ffmpeg -i in.mp3 -af "silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB,areverse" out.mp3
```
Or apply during the 8h concatenation pipeline.
### 1a. Bracketed scene markers in lyrics trigger vocals
Any text beyond the single line `[instrumental]` in the `lyrics` field — especially bracketed scene descriptors like `[rain on leaves]`, `[distant thunder]`, or `[wind chimes]` — activates the model's structural song-generation pathways. This can inject vocal passages, verse/chorus/bridge structures, or lyrical content even when tags explicitly say "no vocals, no lyrics".

**Rule for pure instrumental:** Use the `lyrics` field for semantic content only when you want sung/spoken words. For ambient instrumental, set `lyrics` to exactly:
```
[instrumental]
```
No extra lines, no bracketed annotations, no scene markers.

### 1b. Duration changes restructure the audio (not just extend it)
Increasing `duration` from 110s to 240s does not simply append more seconds of the same style. The model generates a **different structural composition** — a 240s clip may lack percussion/groove elements that were present throughout a 110s clip with identical tags/seed/BPM/key. If a specific element (e.g., rhythmic percussion, melodic progression) is required for continuity across a batch, **shorter clips (110s) concatenated via ffmpeg crossfade are more reliable** than a single long generation.

**Rule:** For stylistic consistency in multi-clip batches, prefer `duration=110.0` with varied seeds over `duration=240.0`.

### 1c. Silence padding at start and end of clips
ACE Step Turbo output often contains **abysmal silence at the beginning and end** of generated clips. This is inherent model behavior, not a configuration error.

**Workaround:** Use FFmpeg `silenceremove` filter in post-processing:
```bash
ffmpeg -i in.mp3 -af "silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB,areverse" out.mp3
```
Or apply during the 8h concatenation pipeline.
Qwen 0.6B (~1.2GB) AND Qwen 4B (~8.5GB) must both be present. The 4B encoder is required for quality — do not skip it.

## 8-Hour Loop Pipeline

1. Generate ~262 clips of 110s each with varied seeds
2. Export as WAV/MP3 from SaveAudioMP3 node
3. Concatenate with ffmpeg crossfade:
```bash
# Simple concat
ffmpeg -f concat -safe 0 -i files.txt -c copy raw.wav
# Normalize + fade in/out for final track
ffmpeg -i raw.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:st=0:d=3" -t 28800 -b:a 320k output_8h.mp3
```

## Seeded Continuation / Track Variation

To produce a continuation or sibling of an existing ACE Step track, keep all creative parameters identical (tags, lyrics, BPM, key, duration) and vary only the seed. This produces a new clip in the same style that can be crossfaded with the original.

**Recommended approach:**
1. Locate the `TextEncodeAceStepAudio1.5` node in the saved API workflow JSON
2. Copy `tags`, `lyrics`, `bpm`, `keyscale`, `duration` verbatim
3. Change `seed` in both `TextEncodeAceStepAudio1.5` and the connected `KSampler` / `PrimitiveInt` seed node
4. Change the `filename_prefix` in `SaveAudioMP3` to avoid overwriting

**Seed strategy:**
- Use the same seed for deterministic reproduction (identical track)
- Use `seed + 1` for a controlled variation (same conditioning, different sampling noise)
- Use a fresh random seed for maximum variation while keeping style locked

## Recovering Parameters from a Saved Workflow

If the user references an output file (e.g. `ACE_Step1.5_xl_turbo_00003_.mp3`) but does not provide the workflow, the parameter history is typically in one of these places:

| Source | Path | Format |
|--------|------|--------|
| API workflow JSON | `.../workflows/audio_ace_step1_5_xl_turbo.json` | JSON — read node `TextEncodeAceStepAudio1.5` inputs |
| Prompt log | `.../output/audio/prompts_audio.txt` | Plain text — manual log |
| ComfyUI metadata | Inside the MP3 itself (if saved with ID3) | Varies |

When reading the API JSON, the key fields are under node class `TextEncodeAceStepAudio1.5`:
- `tags` — comma-separated style descriptors
- `lyrics` — full lyric text or `[instrumental]`
- `bpm`, `duration`, `keyscale`, `timesignature`, `language`
- `cfg_scale`, `temperature`, `top_p`
- `seed` — may be a widget value or wired from a `PrimitiveInt` node

## Critical Pitfalls

### 6. VM-to-host API connectivity (VirtualBox / WSL2)
When Hermes runs in a Linux VM and ComfyUI runs on the Windows host, the REST API at `127.0.0.1:8188` is **not reachable** from the VM by default. Shared folders (`vboxsf`) give filesystem access but **not** network access to the host's loopback.

**Solutions (pick one):**
1. **Port forward in VirtualBox** — forward host `127.0.0.1:8188` → guest `10.0.2.2:8188` (NAT) or bridge the adapter so the host gets a LAN IP
2. **Use bridged networking** — assign the Windows host a LAN IP (e.g. `192.168.0.xxx`), then the VM can reach `http://192.168.0.xxx:8188`
3. **Generate JSON, hand off** — when API is unreachable, produce the modified API-format workflow JSON and ask the user to load it in ComfyUI → "Load" → run manually
4. **Run ComfyUI with `--listen 0.0.0.0`** — on the Windows host, launch with `python main.py --listen 0.0.0.0 --port 8188` so it binds to all interfaces

When option 3 is used, always provide the exact node values changed so the user can verify.

## Related

- ComfyUI docs: https://docs.comfy.org/tutorials/audio/ace-step/ace-step-v1
- Models repo: https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files
- [[ffmpeg-audio-postprocessing.md]] — FFmpeg commands for concatenation, crossfade, normalization, and silence removal for ACE Step ambient loops
- [[vbox-bridged-firewall-comfyui.md]] (virtualbox-guest-management skill) — VM-to-host ComfyUI REST API access via bridged adapter + Windows firewall