# Estrutura do Workflow Text2Image_API.json

Ficheiro: `C:\\Users\\Fil_B\\Downloads\\Text2Image_API.json`
Exportado do ComfyUI em formato API (não editor).

## Node IDs e Campos

| Node | Class | Campos Injectáveis | Valor Padrão |
|------|-------|-------------------|--------------|
| 3 | KSampler | seed, steps, cfg, sampler_name, scheduler, denoise | seed=613..., steps=70, cfg=8 |
| 4 | CheckpointLoaderSimple | ckpt_name | leosamsHelloworldXL_helloworldXL70.safetensors |
| 5 | EmptyLatentImage | width, height, batch_size | width=752, height=1192, batch=3 |
| 6 | CLIPTextEncode | text (positivo) | "A cyberpunk city" |
| 7 | CLIPTextEncode | text (negativo) | "text, watermark" |
| 8 | VAEDecode | (sem injeção) | Ligações fixas |
| 9 | SaveImage | filename_prefix | "ComfyUI" (obrigatório!) |

## Ligações de Outputs → Inputs

```
4[0] model       → 3[model]
4[1] clip        → 6[clip], 7[clip]
4[2] vae         → 8[vae]
5[0] latent      → 3[latent_image]
6[0] conditioning → 3[positive]
7[0] conditioning → 3[negative]
3[0] samples     → 8[samples]
8[0] image       → 9[images]
```

## Notas Críticas

1. **Node IDs vêm do export** — se re-exportar, IDs podem mudar. Sempre validar.
2. **ckpt_name é case-sensitive** — incluir extensão `.safetensors`
3. **filename_prefix é obrigatório** — sem ele: erro 500
4. **Seed ≥ 0** — `-1` é rejeitado; converter para aleatório no Python

## Como Validar

```python
with open("Text2Image_API.json") as f:
    w = json.load(f)

# Verificar node IDs esperados
expected = ["3", "4", "5", "6", "7", "8", "9"]
for nid in expected:
    assert nid in w, f"Node {nid} em falta no workflow!"
    print(f"  {nid}: {w[nid]['class_type']}")
```
