# FramePack: OOM and Dimension Mismatch Errors

Sessão: 2026-05-09 / 2026-05-10
Contexto: THE RENDER WAVE — tentativa de usar FramePack I2V no ComfyUI com RTX 4060 Ti 16GB

---

## Erro 1: OOM (Out of Memory)

**Mensagem:**
```
torch.OutOfMemoryError: Allocation on device 0 would exceed allowed memory.
Currently allocated     : 22.43 GiB
Requested               : 4.07 GiB
Device limit            : 16.00 GiB
Free (according to CUDA): 0 bytes
```

**Causa real:** O `end_latent` (imagem final) estava desligado. Sem o end_latent, o FramePack gera frames "livres" e precisa de mais VRAM para calcular o caminho do motion. Com a resolução atual (latente 186×332 ≈ pixels ~1488×2656) + modelo 13B, 16GB não chega.

**Tentativas de fix que NÃO funcionaram:**
- Aumentar `gpu_memory_preservation` de 6.0 para 10.0 — ainda dá OOM
- Reduzir `latent_window_size` de 9 para 5 — ainda dá OOM
- Reduzir bucket para 768 — ainda dá OOM

**Conclusão:** FramePack 13B com end_latent desligado **não cabe em 16GB** na resolução padrão. Solução: ligar o end_latent (mesmo que seja a mesma imagem) ou usar resolução muito baixa.

---

## Erro 2: Tensor Size Mismatch

**Mensagem:**
```
RuntimeError: The size of tensor a (47) must match the size of tensor b (46)
```

**Causa:** Dimensões do latente (672×384 → 47×84) não são compatíveis com o patch size interno do modelo. O FramePack precisa de dimensões específicas.

**Tentativas de fix que NÃO funcionaram:**
- Mudar bucket para 768, 640 — ainda dá mismatch
- Remover ImageResize nodes — ainda dá mismatch

---

## Erro 3: Tensor Size Mismatch (variante)

**Mensagem:**
```
RuntimeError: Sizes of tensors must match except in dimension 2.
Expected size 69 but got size 72 for tensor number 1 in the list.
```

**Causa:** Mesmo problema de dimensões — 992×576 (resolução do bucket) produz latente com dimensões que não alinham com o modelo. O erro acontece no `torch.cat` dentro do FramePack quando concatena latents de secções diferentes.

---

## Erro 4: RoPE Embedding Mismatch

**Mensagem:**
```
RuntimeError: The size of tensor a (15890) must match the size of tensor b (15859)
```

**Causa:** Rotary Position Embedding (RoPE) no transformer de atenção. As dimensões dos embeddings rotativos não batem com as dimensões dos patches da imagem. Isto é um **bug conhecido** do `ComfyUI-FramePackWrapper` — issue #1 no GitHub.

**Causa subjacente:** A resolução da imagem de input não é compatível com o que o workflow espera. O workflow exemplo foi criado com uma resolução específica em mente (provavelmente 512×512).

---

## Lições aprendidas

1. **FramePack é work-in-progress.** O repositório está marcado como "WORK IN PROGRESS". Bugs de dimensão são esperados.
2. **O workflow exemplo `framepack_hv_example.json` pode estar desatualizado** ou hardcoded para uma resolução específica.
3. **Nunca assumir que um workflow descarregado funciona diretamente.** Verificar versão do custom node, versão do workflow, e compatibilidade de resoluções.
4. **Quando um workflow falha 3+ vezes com erros diferentes, ABANDONAR.** O utilizador tem razão em pedir para mudar de abordagem.
5. **Não sugerir mais "fixes" quando o utilizador diz "chega".** Mudar para alternativa fiável em vez de iterar no mesmo workflow problemático.
6. **Testar primeiro com a resolução mais baixa possível** (512×512) antes de tentar 1024+.
7. **O end_latent é obrigatório para VRAM < 16GB.** FramePack sem end_latent é modo "livre" que exige mais memória.

---

## Alternativas recomendadas após falha do FramePack

| Alternativa | Quando usar |
|-------------|-------------|
| **AnimateDiff Evolved** | Tem motion modules instalados, closed_loop nativo, RTX 4060 Ti aguenta bem |
| **SVD (Stable Video Diffusion)** | 1 modelo só (~4GB), ComfyUI nativo, simples mas limitado a ~4s |
| **FFmpeg Ken Burns** | Zero VRAM, zero modelos, instantâneo, mas sem AI motion |

Para THE RENDER WAVE, **AnimateDiff Evolved** é a alternativa mais fiável após a falha do FramePack.
