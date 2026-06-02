# ComfyUI Music Generation — Workflow Research Results

> Session: 2026-05-25 — user project: ambient relaxation content (8h music + reactive visualization)

## Search Strategy Used

Searched GitHub repositories for:
- `comfyui music generation workflow`
- `comfyui musicgen audiocraft`
- `comfyui custom nodes audio music`
- `audio reactive image stable diffusion comfyui`

Also attempted searches on OpenArt, comfyworkflows.com, DuckDuckGo — all blocked by CAPTCHA or deployment pauses. GitHub remained the only viable source during this session.

---

## Music Generation Repositories Found

### 1. ebrinz/ComfyUI-MusicGen-HF
- **Status**: Already known from `references/audio-workflows.md`
- **Model**: Facebook MusicGen (small/medium/large) via HuggingFace
- **Max stable duration**: ~10 seconds per clip
- **License**: MIT-style dependencies
- **Practical for 8h**: Requires external concatenation with ffmpeg (2,880 clips for 8h)
- **Installation**: Clone to `ComfyUI/custom_nodes/`, install deps into ComfyUI's `python_embeded`

### 2. adithis197/ComfyUI-Caption_to_audio
- **Stars**: 1
- **What it does**: Takes an image description (caption) and generates an appropriate music prompt, then generates audio via MusicGen
- **License**: Not explicitly stated
- **Practical for this user**: Could bridge the gap between "generate fantasy image" → "generate matching music prompt" → "generate music". But same 10s limitation applies.
- **URL**: https://github.com/adithis197/ComfyUI-Caption_to_audio

### 3. aiimagestudio/ComfyUI-AudioX
- **Stars**: 38
- **What it does**: ComfyUI custom nodes for AudioX (HKUSTAudio). Generates sound effects and background music from video or text prompts
- **License**: Open-source (see repo)
- **Practical for this user**: More SFX-oriented. Good for adding ambient elements (rain, thunder, bird sounds) but not full 8-hour ambient music tracks
- **URL**: https://github.com/aiimagestudio/ComfyUI-AudioX

### 4. polats/comfyui_heartmula
- **Stars**: 0
- **What it does**: Dockerized ComfyUI workflow wrapping HeartMuLa (3B parameter music generation model, Apache-2.0)
- **License**: Apache-2.0
- **Practical for this user**: HeartMuLa generates up to 4-minute tracks (much better than MusicGen's 10s), but this repo is Docker-only with no stars/community. Not practical for user's Windows workflow
- **URL**: https://github.com/polats/comfyui_heartmula
- **Alternative**: Run HeartMuLa directly on Windows (see `media/heartmula` skill), not via ComfyUI node

### 5. pmarmotte2/Comfyui-Song-Generation-Suite
- **Stars**: 0
- **What it does**: Generates complete structured songs (lyrics + music prompt) and converts to conditioning compatible with ACE 1.5 audio generation
- **License**: Not stated
- **Critical issue**: ACE 1.5 is a proprietary audio generation engine (closed-source). This node only prepares prompts for ACE, does not generate audio itself
- **Practical for this user**: NOT open-source. Requires ACE 1.5 subscription/backend
- **URL**: https://github.com/pmarmotte2/Comfyui-Song-Generation-Suite

---

## Audio-Reactive Visualization Repositories Found

### 1. Saganaki22/ComfyUI-dotWaveform
- **Stars**: 30
- **What it does**: Generates animated dotted waveform visualizations from audio input. Multiple styles (teardrop-shaped bars, dot patterns)
- **Limitation**: Pure audio visualizer (like Spotify's visualizer). Outputs waveform animation, NOT an overlay on a static image
- **Version**: v2.2.0 (last month at time of search)
- **URL**: https://github.com/Saganaki22/ComfyUI-dotWaveform

### 2. Sorcerio/MBM-Music-Visualizer
- **Stars**: 31
- **What it does**: "Image-generation-based music and audio visualizer integrated into ComfyUI as custom nodes"
- **Status**: Page failed to load during session (timeout). Needs validation
- **Potential**: Most promising candidate for image-reactive visualization. Must verify if it actually overlays effects onto user images or just generates new images
- **URL**: https://github.com/Sorcerio/MBM-Music-Visualizer

### 3. SanDiegoDude/ComfyUI-SaveAudioMP3
- **Stars**: 4
- **What it does**: Converts ComfyUI audio dict to MP3 file (export utility)
- **URL**: https://github.com/SanDiegoDude/ComfyUI-SaveAudioMP3

### 4. RyanHolanda/ComfyUI-AudioBridge
- **Stars**: 0
- **What it does**: Bridges ComfyUI native audio dict ↔ VHS audio types (type conversion)
- **URL**: https://github.com/RyanHolanda/ComfyUI-AudioBridge

### 5. 3rdaiohpinfully/HighffHighSt.Prductions-Custom-ComfyUI_Node
- **Stars**: 0
- **What it does**: "Music Reactive Frame By Frame Animated Music Videos" — claims to generate animated music videos
- **URL**: https://github.com/3rdaiohpinfully/HighffHighSt.Prductions-Custom-ComfyUI_Node

---

## Key Insight: No 8-Hour Native Solution

**No ComfyUI node or workflow found generates 8-hour ambient music natively.**

All solutions require one of these post-processing steps:
1. **MusicGen approach**: Generate thousands of 10s clips → concatenate with ffmpeg crossfade
2. **HeartMuLa approach**: Generate 4-minute tracks → concatenate (only 120 tracks for 8h, much more feasible)
3. **External tool**: Use dedicated ambient music generators (e.g., `moodist`, procedural audio engines) outside ComfyUI

For this user's project, the most practical path is:
- **Music**: HeartMuLa on Windows host (4-min chunks, concatenate with ffmpeg)
- **Image**: ComfyUI / Stable Diffusion (user's existing workflow)
- **Motion**: Python script or DaVinci Resolve compositing (rain, waves, lightning overlays on static image)
- **Reactive equalizer**: Python script (librosa/aubio audio analysis → PIL/OpenCV overlay on image → ffmpeg encode)

---

## Search Notes

- `comfyworkflows.com` — deployment paused (site offline during session)
- `openart.ai/workflows` — redirects to home, no direct workflow search accessible without login
- DuckDuckGo / Google search — blocked by CAPTCHA / bot detection on agent browser
- GitHub search remained functional throughout session
