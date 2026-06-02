# IPAdapter+ Breaking Changes — PrepImageForClipVision

## Contexto (2026-05-14)
Uma atualização do custom node `ComfyUI_IPAdapter_plus` (by cubiq) adicionou 3 inputs obrigatórios ao node `PrepImageForClipVision`:
- `crop_position` (string: "center", "top", "bottom", "left", "right")
- `sharpening` (float: 0.0–2.0)
- `interpolation` (string: "LANCZOS", "BICUBIC", "BILINEAR", "NEAREST")

## Sintoma
Workflows API exportados ANTES desta atualização param de funcionar. O ComfyUI rejeita o prompt com erro:
```
Failed to validate prompt for output 9:
* PrepImageForClipVision 11:
  - Required input is missing: crop_position
  - Required input is missing: sharpening
  - Required input is missing: interpolation
Output will be ignored
invalid prompt: {'type': 'prompt_outputs_failed_validation', ...}
```

O workflow gera a **primeira imagem** (cena master via Text2Image normal) mas **falha nas variantes** via IP-Adapter, porque o workflow IP-Adapter é que contém o `PrepImageForClipVision`.

## Fix
Editar o ficheiro workflow API JSON e adicionar os 3 inputs ao node:

```json
"11": {
  "inputs": {
    "image": ["10", 0],
    "crop_position": "center",
    "sharpening": 0.0,
    "interpolation": "LANCZOS"
  },
  "class_type": "PrepImageForClipVision",
  "_meta": {
    "title": "Prep Image For ClipVision"
  }
}
```

Valores recomendados para coerência visual (storyboard):
- `crop_position: "center"` — mantém a composição central da imagem de referência
- `sharpening: 0.0` — não aplica sharpening adicional (evita artefactos)
- `interpolation: "LANCZOS"` — melhor qualidade de redimensionamento

## Onde aplicar
- `D:/AI_Ecosystem/03_Workflows/API/Text2Image_IPAdapter_Coherent_API.json`
- Qualquer outro workflow API que use `PrepImageForClipVision`

## Pitfall: assumir que workflows existentes continuam a funcionar
Workflows API exportados do ComfyUI UI são JSON estáticos. Quando um custom node é atualizado, os workflows antigos **não se atualizam automaticamente**. É necessário:
1. Abrir o workflow no ComfyUI UI
2. Verificar se algum node mostra warning/erro
3. Reconfigurar o node com os novos inputs
4. Re-exportar para API format

Ou editar manualmente o JSON (como acima) se os valores default são aceitáveis.

## Deteção automática
Scripts que consomem workflows API deveriam validar o JSON antes de enviar:
```python
import json

with open(workflow_path) as f:
    wf = json.load(f)

for nid, node in wf.items():
    if node.get("class_type") == "PrepImageForClipVision":
        inputs = node.get("inputs", {})
        missing = []
        for required in ["crop_position", "sharpening", "interpolation"]:
            if required not in inputs:
                missing.append(required)
        if missing:
            print(f"[AVISO] Node {nid}: inputs em falta: {missing}")
            # Auto-fix com defaults
            inputs.setdefault("crop_position", "center")
            inputs.setdefault("sharpening", 0.0)
            inputs.setdefault("interpolation", "LANCZOS")
```

## Nota sobre updates de custom nodes
O utilizador atualiza custom nodes periodicamente via `git pull` no `custom_nodes/`. Este padrão de breaking changes é comum em ComfyUI — nodes ganham novos inputs com valores default no UI, mas workflows API exportados ANTES da update não têm esses valores.

**Regra:** Sempre que um workflow API antigo falha com "Required input is missing", verificar primeiro se o custom node foi atualizado recentemente.
