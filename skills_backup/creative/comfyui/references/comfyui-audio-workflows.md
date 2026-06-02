# ComfyUI Audio Workflows (MusicGen, AudioCraft, AudioLDM)

## Known Working Custom Node: ComfyUI-MusicGen-HF

Repository: `https://github.com/ebrinz/ComfyUI-MusicGen-HF`

Install:
```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/ebrinz/ComfyUI-MusicGen-HF.git
cd ComfyUI-MusicGen-HF
pip install -r requirements.txt
```

Nodes provided:
- `HuggingFaceMusicGen` — main generation
- `SaveAudioStandalone` — export wav/flac/mp3/opus
- `LoadAudioStandalone` — load audio file
- `BPMDurationInput` — musical timing control
- `LoopingAudioPreview` — preview with looping

## HuggingFaceMusicGen Node Parameters

| Parameter | Type | Default | Range | Notes |
|-----------|------|---------|-------|-------|
| model_size | COMBO | "small" | small, medium, large | small = ~3GB, fastest |
| duration | FLOAT | 10.0 | 1.0–30.0 | seconds (max ~30 for small) |
| guidance_scale | FLOAT | 3.0 | 1.0–10.0 | 2.5–3.5 good for ambient |
| do_sample | BOOLEAN | true | | enable for variety |
| max_new_tokens | INT | 256 | 50–1503 | 512+ for longer tracks |
| seed | INT | 42 | 0–999999999 | -1 = random (via script) |
| prompt | STRING | multiline | | text description of music |
| temperature | FLOAT | 1.0 | 0.1–2.0 | 0.8–1.2 for ambient |
| duration_override | FLOAT | 0.0 | 0.0–30.0 | overrides duration from BPM node |
| conditioning_audio | AUDIO | optional | | audio-to-audio generation |

## SaveAudioStandalone Node Parameters

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| audio | AUDIO | required | input from MusicGen |
| filename_prefix | STRING | "musicgen_audio" | basename of output |
| format | COMBO | "wav" | wav, flac, mp3, opus |
| quality | COMBO | "128k" | 128k, 192k, 320k, V0 |

## MusicGen Key Limitation

**Maximum generation per run: ~30 seconds** (model-dependent). For 8-hour tracks:
1. Generate N loops (e.g. 10s × 2,880 = 8h)
2. Concatenate with crossfade via ffmpeg
3. Volume-normalize
4. Export to MP3 320k or Opus

## Example ffmpeg Crossfade for Loops

```bash
# Simple concat (no crossfade)
ffmpeg -f concat -safe 0 -i files.txt -acodec pcm_s16le output.wav

# Crossfade between 2 clips
ffmpeg -i clip1.wav -i clip2.wav \
  -filter_complex "[0][1]acrossfade=d=0.5[out]" \
  -map "[out]" output.wav

# Multiple clips with crossfade chain
ffmpeg -i c1.wav -i c2.wav -i c3.wav \
  -filter_complex "[0][1]acrossfade=d=0.5[a01];[a01][2]acrossfade=d=0.5[out]" \
  -map "[out]" output.wav
```
