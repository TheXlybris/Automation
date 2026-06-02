# FramePack Workflow Tuning: Resolução e Nodes

## Problema
O workflow exemplo `framepack_hv_example.json` gera por defeito em resoluções baixas (480×512 no teste real) devido a nodes `ImageResize+` que forçam 512×512.

## Causa
Nodes 59 e 50 (`ImageResize+`) no workflow exemplo redimensionam a imagem de input para 512×512 antes de passar ao VAEEncode. O node `FramePackFindNearestBucket` (node 51) usa valor base **640** que também não corresponde às resoluções desejadas (1024, 2048, 4096).

## Solução

### Para resolução 16:9 (1024×576, 2048×1152, 4096×2304):

**Passo 1 — Node 51: FramePackFindNearestBucket**
- Valor atual: **640**
- Alterar para a **largura desejada** (ex: **1024** ou **2048** ou **4096**)
- FramePack encontra automaticamente a resolução 16:9 mais próxima suportada pelo bucket sizing

**Passo 2 — Nodes 59 e 50: ImageResize+**
- **Opção A (recomendada):** Remover o link que passa por estes nodes. Ligar `LoadImage` diretamente ao `VAEEncode`.
- **Opção B:** Alterar os valores de 512/512 para a resolução desejada (ex: 1024/576, 2048/1152).
- **Opção C:** Bypass via rgthree-comfy (se instalado) ou desligar os nodes.

**Passo 3 — Verificar output**
```bash
ffprobe -v error -show_entries stream=width,height -of csv=s=x:p=0 output.mp4
# Deve dar: 1024x576 (ou a resolução definida)
```

## Estrutura do workflow (nodes relevantes)

```
[LoadImage] ──→ [ImageResize+] ──→ [VAEEncode] ──→ [FramePackSampler]
                   ↑                    ↑
              (nodes 59/50)        (start_latent)
                    
[FramePackFindNearestBucket] ──→ (resolução de referência)
```

## Resoluções FramePack suportadas
FramePack usa "bucket sizing" — lista discreta de resoluções pré-calculadas. O `FramePackFindNearestBucket` encontra a mais próxima da largura especificada. A lista exata depende da implementação, mas inclui tipicamente:
- 512×512, 640×480, 768×432, 896×504, 1024×576, 1152×648, 1280×720, 1536×864, 1920×1080, 2048×1152, 2560×1440, 3840×2160, 4096×2304

## Diagnóstico
Se `ffprobe` reportar width < 500 (ex: 480×512), os `ImageResize+` ainda estão ativos. Se reportar um valor próximo do bucket mas não exato, o `FramePackFindNearestBucket` ajustou automaticamente.
