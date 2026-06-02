# FFmpeg Audio Post-Processing for ACE Step Ambient Loops

## Context
Companion to `references/ace-step-audio.md`. These commands solve the specific post-processing needs of the Render Wave ambient music pipeline: concatenating short clips into long loops, crossfading, normalizing, and removing silence.

## Prerequisites
FFmpeg must be installed. ComfyUI's SaveAudioMP3 node already uses FFmpeg internally (Lavf encoder), so it is typically present on Windows hosts where ComfyUI runs. For VM-side batch scripts, ensure `ffmpeg` is on PATH.

## 1. Remove Silence from Clip Start and End

ACE Step Turbo clips often have abysmal silence at beginning and end.

**Bidirectional trim (start + end):**
```bash
ffmpeg -i input.mp3 -af \
  "silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB,\
   areverse,\
   silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB,\
   areverse" \
  -b:a 320k output_trimmed.mp3
```

**One-direction only (beginning):**
```bash
ffmpeg -i input.mp3 -af \
  "silenceremove=start_periods=1:start_duration=1:start_threshold=-50dB" \
  -b:a 320k output.mp3
```

Parameters explained:
- `start_periods=1` — remove 1 silent period at start
- `start_duration=0.5` — minimum 0.5s of silence to trigger removal
- `start_threshold=-50dB` — audio below -50dB is considered silence
- `areverse` — reverses audio so we can trim the end the same way

## 2. Concatenate Multiple Clips

### Simple concat (no transitions)
Create `files.txt`:
```
file 'clip_001.mp3'
file 'clip_002.mp3'
file 'clip_003.mp3'
```

Run:
```bash
ffmpeg -f concat -safe 0 -i files.txt -c copy combined.mp3
```

### Concat with crossfade between clips
```bash
ffmpeg -i clip_001.mp3 -i clip_002.mp3 -i clip_003.mp3 \
  -filter_complex \
  "[0:a][1:a]acrossfade=d=3:c1=tri:c2=tri[a1]; \
   [a1][2:a]acrossfade=d=3:c1=tri:c2=tri[out]" \
  -map "[out]" -b:a 320k combined.mp3
```

- `d=3` — 3-second crossfade overlap
- `c1=tri:c2=tri` — triangular fade curve (smooth)

## 3. Build 8-Hour Loop from N Clips

**Full pipeline:**
```bash
# Step 1: Generate clips with ACE Step (~262 clips of 110s)
# Step 2: Create files.txt
for f in output/audio/*.mp3; do
  echo "file '$f'" >> files.txt
done

# Step 3: Concatenate + crossfade + normalize + trim to exactly 8h
ffmpeg -f concat -safe 0 -i files.txt \
  -af "acrossfade=d=3,\
       afade=t=in:st=0:d=3,\
       afade=t=out:st=28797:d=3,\
       loudnorm=I=-16:TP=-1.5:LRA=11" \
  -t 28800 \
  -b:a 320k \
  output_8h.mp3
```

Parameters:
- `acrossfade=d=3` — crossfade between each clip
- `afade=t=in:st=0:d=3` — fade in first 3 seconds of final track
- `afade=t=out:st=28797:d=3` — fade out last 3 seconds (8h = 28800s)
- `loudnorm=I=-16` — normalize to -16 LUFS (YouTube-friendly)
- `TP=-1.5` — true peak limit -1.5dB
- `LRA=11` — loudness range 11 LU (consistent level)
- `-t 28800` — hard limit to exactly 8 hours

## 4. Normalization Only (Single Track)

```bash
ffmpeg -i input.mp3 \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11" \
  -b:a 320k normalized.mp3
```

## 5. Two-Pass Loudnorm (More Accurate)

Pass 1 — analyze:
```bash
ffmpeg -i input.mp3 -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null -
```

Read the JSON output, then Pass 2 — apply with measured values:
```bash
ffmpeg -i input.mp3 \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=-23:measured_TP=-3:measured_LRA=15:measured_thresh=-34:offset=0.5" \
  -b:a 320k normalized.mp3
```

## 6. Speed Change Without Pitch Shift

For matching music tempo to desired BPM range:
```bash
ffmpeg -i input.mp3 -af "atempo=0.95" -b:a 320k slower.mp3
```
- `atempo=0.95` — 5% slower (preserves pitch)
- Range: 0.5 to 2.0 (chain multiple atempo filters for values outside this range)

## 7. Convert to WAV for Further Processing

```bash
ffmpeg -i input.mp3 -ar 48000 -ac 2 output.wav
```

## Open Source GUI Alternatives

| Tool | Purpose | License |
|------|---------|---------|
| **Audacity** | Multi-track editing, noise reduction, effects | GPL v2+ |
| **Ardour** | Full DAW, mixing, mastering, VST plugins | GPL v2+ (binary: pay-what-you-want) |
| **Tenacity** | Audacity fork without Muse Group telemetry | GPL v2+ |
| **SoX** | CLI swiss-army knife for audio | GPL v2+ |

**Recommendation:**
- **Batch automation** → FFmpeg (this document)
- **Manual fine-tuning** → Audacity
- **Professional mastering** → Ardour (if user wants to add VST effects, EQ, compression)
- **Quick edits** → SoX (simpler syntax than FFmpeg for some operations)

## Related

- [[ace-step-audio.md]] — ACE Step v1.5 generation parameters and pitfalls
- [[vbox-bridged-firewall-comfyui.md]] (virtualbox-guest-management skill) — Network path from VM to Windows ComfyUI
