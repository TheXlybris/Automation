# Prompt Translation: Image → Video (THE RENDER WAVE)

Engine implemented in `generate_video.py`. Two implementations exist:
- **Python** (`translate_image_to_video_prompt`): server-side, used when `--prompt` is passed
- **JavaScript** (client-side in `video_generator.html`): mirrors the same regex rules for live preview

## Regex Patterns (Python / JavaScript)

```python
STATIC_PHOTO_TERMS = [
    r"\d+mm lens",           # "35mm lens", "24mm lens"
    r"medium shot",
    r"close[\s-]?up",       # "close-up", "close up"
    r"wide shot",
    r"full shot",
    r"extreme close[\s-]?up",
    r"shallow depth of field",
    r"depth of field",
    r"sharp focus on",
    r"focus on",
    r"National Geographic",
    r"nature photography",
    r"photography",
    r"natural colors",
    r"detailed textures",
    r"textures of",
    r"raw photo",
    r"8k",
]
```

Same patterns in JavaScript (for UI preview):
```javascript
const STATIC_TERMS = [
    /\d+mm lens/gi, /medium shot/gi, /close[\s-]?up/gi, /wide shot/gi,
    /full shot/gi, /extreme close[\s-]?up/gi, /shallow depth of field/gi,
    /depth of field/gi, /sharp focus on/gi, /focus on/gi,
    /National Geographic/gi, /nature photography/gi, /photography/gi,
    /natural colors/gi, /detailed textures/gi, /textures of/gi,
    /raw photo/gi, /8k/gi
];
```

## Motion Suffix (appended after cleanup)

```
, consistent scene, stable composition, camera slowly pans to the right,
subtle ambient motion only, fixed viewpoint, seamless cyclic motion,
smooth continuous movement, infinite loop feel, ambient perpetual motion,
natural repeating rhythm, hypnotic gentle flow, meditative calm motion
```

## Cleanup Steps

1. Run each regex substitution (remove matches, case-insensitive)
2. Collapse double commas: `,,` → `,`
3. Collapse multiple whitespace: `\s+` → ` `
4. Strip leading/trailing commas and spaces

## Full Working Example

**Image prompt (input):**
```
masterpiece, best quality, photorealistic, 8k, highly detailed, raw photo,
a small picturesque waterfall cascading gently over mossy rocks into a
crystal-clear shallow pool, surrounded by lush green grass and vibrant
wildflowers like daisies, poppies and lavender, water droplets sparkling
in the air, soft golden hour sunlight filtering through nearby trees,
warm and serene atmosphere, 35mm lens, medium shot, shallow depth of
field on the foreground flowers, sharp focus on the waterfall,
National Geographic nature photography, natural colors,
detailed textures of rock and water
```

**Video prompt (output):**
```
masterpiece, best quality, photorealistic, highly detailed,
a small picturesque waterfall cascading gently over mossy rocks into a
crystal-clear shallow pool, surrounded by lush green grass and vibrant
wildflowers like daisies, poppies and lavender, water droplets sparkling
in the air, soft golden hour sunlight filtering through nearby trees,
warm and serene atmosphere,
consistent scene, stable composition, camera slowly pans to the right,
subtle ambient motion only, fixed viewpoint, seamless cyclic motion,
smooth continuous movement, infinite loop feel, ambient perpetual motion,
natural repeating rhythm, hypnotic gentle flow, meditative calm motion
```

## API Options

| Flag | Behavior |
|------|----------|
| (none) | Default: auto-translate image prompt to video prompt |
| `--no-translate` | Pass image prompt directly to video workflow |
| `--video-prompt "..."` | Override with custom video prompt (bypasses translation) |

## Pitfall: Manual prompt with photography terms

If `--video-prompt` is used, the user is responsible for removing photography terms. The script does NOT auto-translate manual video prompts. Only `--prompt` (the image prompt) gets translated.

## Pitfall: Empty prompt after stripping

If the image prompt consists ONLY of photography terms (e.g. just "35mm lens, medium shot, 8k"), the cleaned prompt becomes empty before the motion suffix is added. The result is a valid but meaningless video prompt consisting only of motion suffix. Always validate that the cleaned prompt has non-suffix content.
