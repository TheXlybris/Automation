# Pesquisa Img2Vid Fantasy/Animation -- Resultados (Maio 2026)

## Fonte
Relatorio produzido pelo subagent researcher (perfil `researcher`) numa sessao async via `delegate_task`. Tempo: 551 segundos. Modelo: kimi-k2.6.

## Resumo Executivo

**Nenhuma alternativa img2vid comprovadamente superior ao LTX 2B v0.9.5 para RTX 4060 Ti 16GB.**

Duas hipoteses testaveis emergiram para melhor adequacao a estilo fantasy/animation:

1. **HunyuanVideo 1.5 I2V (8B, FP8)** -- unico modelo recente (Maio 2025), suficientemente leve, com declaracao oficial de suporte a estilos anime/3D.
2. **Wan 2.2 TI2V 5B Hybrid** -- cabe em 8GB VRAM oficialmente, mas e hibrido (T2V+I2V), o que pode comprometer fidelidade a imagem de entrada.

## Problema Critico: LTX 2B tem bias para fotorealismo

Utilizador no Reddit (LTX-2 I2V):
> "When prompting for anime style, animation or illustration, the video ends up looking too realistic"

Isto coloca em risco a isencao de declaracao AI no YouTube (conteudo deve ser "claramente irrealista").

## Inventario Comparativo

| Modelo | Fantasia? | VRAM <=16GB? | Veredicto |
|---|---|---|---|
| **LTX 2B v0.9.5/0.9.6** | Fraca (bias realista) | Confirmado (~10-12GB) | Em uso atual. Melhor velocidade, pior adequacao estilo. |
| **HunyuanVideo 1.5 I2V (8B, FP8)** | Suporta anime/3D/fantasy (oficial) | Provavel a 480p/720p | **Melhor para testar** |
| **Wan 2.2 TI2V 5B Hybrid** | Nao verificado | 8GB (oficial) | Alternativa reserva |
| Wan 2.1 I2V 14B | -- | Confirmado OOM | Ja descartado |
| LTX 2.3 13B/22B | -- | Confirmado OOM | Ja descartado |
| FramePack, AnimateDiff Evolved | -- | Confirmado OOM | Ja descartado |

## Prioridade de Accao Recomendada

| Prioridade | Accao | Racional |
|---|---|---|
| P0 | Testar HunyuanVideo 1.5 I2V FP8 a 480p/720p | Unico modelo recente, suficientemente leve, suporte oficial multi-estilo. |
| P1 | Testar Wan 2.2 TI2V 5B Hybrid | Cabe em 8GB, mas hibrido. |
| P2 | Melhorar prompts LTX 2B com termos de estilo agressivos | Solucao curto-prazo sem downloads. |
| P3 | Verificar compatibilidade LoRAs LTX 2.3 em LTX 2B | Se funcionarem, mitigam bias realista. |

## Links Essenciais
- HunyuanVideo 1.5 I2V: https://huggingface.co/tencent/HunyuanVideo-I2V
- Wan 2.2 ComfyUI Docs: https://docs.comfy.org/tutorials/video/wan/wan2_2
- LTX Bias Reddit: https://www.reddit.com/r/StableDiffusion/comments/1qgzamd/ltx2_i2v_prompting_for_anime_or_illustration_style/
- LTX LoRAs Docs: https://docs.ltx.video/open-source-model/usage-guides/lo-ra

## Flags de Credibilidade
- Wiki local / testes empiricos do projecto: ALTA (primaria)
- Blog oficial ComfyUI: ALTA (primaria)
- Reddit threads anonimizados: MEDIA (relato de utilizador)
- Blogs de terceiros (Medium, sonusahani): MEDIA -- testado em setups nao especificados, nao no RTX 4060 Ti.
