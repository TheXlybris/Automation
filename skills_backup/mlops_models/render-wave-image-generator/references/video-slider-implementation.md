# Video Generator UI — Slider Implementation (2026-05-12)

The duration slider replaced a `<select>` dropdown with fixed frame counts. The slider maps seconds to frames at 25fps.

## HTML

```html
<label for="lengthSlider">Duracao (segundos)</label>
<input id="lengthSlider" type="range" min="2" max="10" step="0.5" value="6" style="width:70%;">
<span id="lengthDisplay">6.0s</span>
<input type="hidden" id="length" value="150">
<div>~<span id="framesDisplay">150</span> frames @ 25fps</div>
```

## JavaScript

```javascript
const slider = document.getElementById('lengthSlider');
const display = document.getElementById('lengthDisplay');
const hidden = document.getElementById('length');
const framesDisplay = document.getElementById('framesDisplay');

function updateLength() {
    const seconds = parseFloat(slider.value);
    const frames = Math.round(seconds * 25);
    display.textContent = seconds.toFixed(1) + 's';
    hidden.value = frames;
    framesDisplay.textContent = frames;
}
slider.addEventListener('input', updateLength);
updateLength();
```

## Why 25fps?

LTX Video's `LTXVConditioning` node uses `frame_rate=25` by default. The `length` parameter in `LTXVImgToVideo` is **number of frames**, not seconds. Matching the slider math to the node's frame rate gives accurate duration.

## Server-side reading

The server reads `document.getElementById('length').value` (the hidden input), which contains the frame count. The slider is purely UX — the hidden field is what gets sent in the POST payload.

## Range

- Min: 2 seconds (50 frames) — shortest viable clip
- Max: 10 seconds (250 frames) — reasonable upper bound for LTX Video 2B on 16GB VRAM
- Step: 0.5 seconds (12-13 frames) — fine enough control without clutter
