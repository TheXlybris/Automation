# Audio-Reactive Image Visualization in ComfyUI

> Session: 2026-05-25 — user project: ambient relaxation content (fantasy images + motion overlays + up-to-8h music + reactive equalizer)

## Field Status (2026)

Workflows that do **"static fantasy image reacting to music with integrated equalizer"** are extremely rare or non-existent as ready-made ComfyUI workflows. The community typically separates these concerns:

1. Image generation → ComfyUI / Stable Diffusion
2. Music generation → Suno / Udio / AudioCraft
3. Final video compositing → DaVinci Resolve / After Effects / Python scripts

## Known Nodes / Repositories Found

### Music Generation (AudioCraft / MusicGen / HeartMuLa)

| Repository | Stars | What it does | License | Limitation for this user |
|---|---|---|---|---|
| `ebrinz/ComfyUI-MusicGen-HF` | — | Text-to-music via Facebook MusicGen (HuggingFace) | MIT-style deps | Max ~10s stable per clip; needs concatenation for 8h |
| `adithis197/ComfyUI-Caption_to_audio` | 1 | Converts image caption to music prompt, then generates via MusicGen | Unknown | Same 10s limit; thin wrapper |
| `aiimagestudio/ComfyUI-AudioX` | 38 | Sound effects / background music from video or text (AudioX) | Open-source | More SFX-oriented; not ambient long-form music |
| `polats/comfyui_heartmula` | 0 | Dockerized HeartMuLa (3B param music generation) | Apache-2.0 | No active community; Docker-only |
| `pmarmotte2/Comfyui-Song-Generation-Suite` | 0 | SongGenerationSuite → ACE 1.5 conditioning | Unknown | Requires ACE 1.5 backend (not confirmed open-source) |

**Verdict**: No ComfyUI native node generates 8-hour ambient tracks. All require external concatenation (ffmpeg) or run outside ComfyUI.

### Audio Visualization / Reactive Nodes

| Repository | Stars | What it does | Limitation for this user |
|---|---|---|---|
| `Saganaki22/ComfyUI-dotWaveform` | 30 | Animated dotted waveform from audio (teardrop bars, dot patterns) | Pure waveform visualizer (like Spotify), not overlaid on a static image |
| `Sorcerio/MBM-Music-Visualizer` | 31 | Image-based music visualizer as ComfyUI custom nodes | Could not load during session — needs investigation |
| `SanDiegoDude/ComfyUI-SaveAudioMP3` | 4 | Converts ComfyUI audio dict to MP3 file | Just export, no visualization |
| `RyanHolanda/ComfyUI-AudioBridge` | 0 | Bridges ComfyUI native audio dict ↔ VHS audio types | Plumbing only |
| `3rdaiohpinfully/HighffHighSt.Prductions-Custom-ComfyUI_Node` | 0 | "Music Reactive Frame By Frame Animated Music Videos" | Needs investigation |

**Verdict**: No ready-made ComfyUI node overlays a reactive equalizer onto a static image while syncing to audio. Closest is MBM-Music-Visualizer but it needs validation.

### Music Visualizer (outside ComfyUI)
| Tool | Type | Notes |
|---|---|---|
| **DaVinci Resolve (free)** | Desktop NLE | Fusion page can link particles/audio analysis to image layers — professional control, manual |
| **Python + PIL/OpenCV + librosa/aubio** | Script | Full automation. Analyse audio → apply displacement/flash/particle effects → render frames → ffmpeg encode MP4 |
| **ComfyUI+VHS+dotWaveform** | Hybrid | Generate audio in ComfyUI, export, then use dotWaveform for waveform overlay (different layer, not image-reactive) |

## Recommended Hybrid Pipelines

| Approach | Tools | Best For |
|----------|-------|----------|
| **Python script** | PIL/OpenCV + audio analysis (librosa/aubio) | Full automation, 8h batch runs |
| **DaVinci Resolve** (free) | Fusion page with audio-linked particles | Manual but professional control |
| **ComfyUI+VHS+dotWaveform** | ComfyUI + VideoHelperSuite + dotWaveform nodes | If staying entirely inside ComfyUI |

## User Context

This user prefers **static AI-generated fantasy images with motion overlays** (waves, seagulls, lightning, rain) over generative video AI, due to consistency issues with full video generation. Music target: ambient relaxation tracks up to 8 hours. Visualizer should be an equalizer-style overlay that reacts to the music.

### Preferred Architecture (user-defined)
1. **Image generation** → ComfyUI / Stable Diffusion (static fantasy scenes)
2. **Motion overlay** → Controlled effects (waves, particles, weather) applied in post — NOT generative video models
3. **Music generation** → Open-source, 8-hour ambient tracks. No current ComfyUI node handles this natively; requires external concatenation
4. **Reactive visualization** → Image + audio analysis → equalizer-style overlays synced to music → composited into final MP4
