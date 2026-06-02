# LTX 2B Fantasy/Animation img2vid Prompting

LTX 2B has a strong photorealism bias. To force fantasy/animation style in img2vid:

## Style Enforcement Block (always include in positive prompt)
`fantasy animation style, painterly, ethereal, magical, dreamlike atmosphere, clearly unrealistic, stylized, concept art animation, not photorealistic, not live footage`

## Temporal Keywords (critical with strength=0.1)
The model tends to turn brief phenomena into persistent streaks/cascades.

| Desired Effect | Prompt for it |
|---|---|
| Lightning flashes | `intermittent lightning flashes`, `brief jagged bolts striking randomly`, `lightning flickers once and vanishes`, `sky illuminates with brief flashes` |
| Water motion | `water surface rippling softly`, `gentle flowing water` |
| Magic energy | `magical glow pulsating gently`, `sparks drifting upward` |
| Atmospheric | `mist drifting slowly`, `fog rolling gently` |

## Motion to Avoid
Never use continuous-flow words for brief/discrete phenomena — the model turns them into persistent vertical streaks:
- ❌ `lightning falling`, `electric bolts raining down`, `energy cascading`
- ❌ `continuous glow`, `lingering lightning`, `persistent energy`

## Negative Prompt Additions
Append to standard negative:
`continuous streaks, falling lines, rain-like electricity, persistent glow lines, uniform vertical streaks, ordered pattern, lightning rain, energy drizzle, lingering lightning`

## Workflow Notes
- Strength=0.1 keeps the video very close to the input image; the prompt only guides motion + subtle style reinforcement.
- The input image (DreamShaperXL) already carries the style. The img2vid prompt should focus on MOTION, not override the visual style.
