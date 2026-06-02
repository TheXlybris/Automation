# ACE Step FFmpeg Post-Processing Commands

> Condensed recipe for ffmpeg commands used in THE RENDER WAVE ambient music pipeline.
> Source: session 2026-06-01 (Hermes + Filipe)
> Last updated: 2026-06-01

---

## 1. Remove Start/End Silence from Individual Clips

ACE Step Turbo generates clips with **silent padding at both ends**. Strip before concatenation:

```bash
# Two-pass silenceremove (trim head, reverse, trim tail, reverse back)
ffmpeg -i clip.mp3 -af \
  "silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB,\
   areverse,\
   silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB,\
   areverse" \
  clean_clip.mp3

# Batch version (PowerShell)
foreach ($f in Get-ChildItem *.mp3) {
    ffmpeg -i $f.Name -af "silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_duration=0.5:start_threshold=-50dB,areverse" ("clean_" + $f.Name)
}
```

## 2. Concatenate Multiple Clips (Simple)

```bash
# Create file list
echo "file 'clip1.mp3'" >  files.txt
echo "file 'clip2.mp3'" >> files.txt
# ... etc

# Concatenate without re-encoding
ffmpeg -f concat -safe 0 -i files.txt -c copy raw.mp3
```

## 3. Concatenate with Crossfade

```bash
# Two clips with 3s crossfade
ffmpeg -i clip1.mp3 -i clip2.mp3 -filter_complex \
  "acrossfade=d=3:curve1=tri:curve2=tri" \
  fused.mp3

# Full pipeline: concat list + crossfade + fade-in/out + normalization
ffmpeg -f concat -safe 0 -i files.txt \
  -af "acrossfade=d=3,afade=t=in:st=0:d=2,afade=t=out:st=28797:d=3,loudnorm=I=-16:TP=-1.5:LRA=11" \
  -t 28800 -b:a 320k output_8h.mp3
```

| Parameter | Meaning |
|-----------|---------|
| `acrossfade=d=3` | 3-second crossfade between clips |
| `curve1=tri` | Triangular fade curve (smooth) |
| `afade=t=in:st=0:d=2` | Fade in at start, 2 seconds |
| `afade=t=out:st=28797:d=3` | Fade out at 28797s (= 8h - 3s) |
| `loudnorm=I=-16:TP=-1.5:LRA=11` | YouTube loudness normalization |
| `-t 28800` | Hard limit to exactly 8 hours |
| `-b:a 320k` | MP3 bitrate 320 kbps |

## 4. Normalize Loudness (YouTube -14 LUFS target)

```bash
# Integrated loudness -16 LUFS, True Peak -1.5 dBTP, Loudness Range 11 LU
ffmpeg -i input.mp3 -af "loudnorm=I=-16:TP=-1.5:LRA=11" normalized.mp3

# Analyze without re-encoding
ffmpeg -i input.mp3 -af "loudnorm=print_format=json" -f null -
```

## 5. Full Pipeline Script (Bash)

```bash
#!/bin/bash
# generate_8h_loop.sh — assumes clips are in ./clips/

CLIPS_DIR="./clips"
OUTPUT="./output_8h.mp3"
LIST="./file_list.txt"

# Generate list
> "$LIST"
for f in "$CLIPS_DIR"/*.mp3; do
    echo "file '$f'" >> "$LIST"
done

# Build
ffmpeg -y -f concat -safe 0 -i "$LIST" \
    -af "acrossfade=d=3:curve1=tri:curve2=tri,\
         afade=t=in:st=0:d=2,\
         afade=t=out:st=28797:d=3,\
         loudnorm=I=-16:TP=-1.5:LRA=11" \
    -t 28800 -b:a 320k "$OUTPUT"

echo "Done: $OUTPUT"
```

## 6. PowerShell Equivalent (Windows)

```powershell
$clips = Get-ChildItem "D:\\AI_Ecosystem\\02_Engines\\ComfyUI\\ComfyUI\\output\\audio\\*.mp3" | Select-Object -ExpandProperty FullName

# Create temp list
$list = New-TemporaryFile
$clips | ForEach-Object { Add-Content $list "file '$_'" }

ffmpeg -f concat -safe 0 -i $list.FullName `
    -af "acrossfade=d=3,afade=t=in:st=0:d=2,afade=t=out:st=28797:d=3,loudnorm=I=-16:TP=-1.5:LRA=11" `
    -t 28800 -b:a 320k "D:\\AI_Ecosystem\\02_Engines\\ComfyUI\\ComfyUI\\output\\audio\\8h_loop.mp3"

Remove-Item $list
```

## Related

- Back to: `[[references/ace-step-audio.md]]`
- Workflow template: `[[templates/streamlit-ace-music-gui.py]]`
