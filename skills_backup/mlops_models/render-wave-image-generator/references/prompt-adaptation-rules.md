# Prompt Adaptation Rules: Image → Video Motion

Sessão: 2026-05-09
Contexto: THE RENDER WAVE — transformar prompts de imagem estática em prompts de movimento para AnimateDiff img2vid.

## Problema

AnimateDiff txt2vid gera cada frame a partir de `EmptyLatentImage` (ruído puro). O modelo não consegue manter um sujeito complexo (gato, ponte, rochas) consistente durante 160 frames. O resultado é **temporal drift**: o gato desaparece, a ponte deforma, a cena "derrete".

AnimateDiff img2vid usa uma imagem base como âncora. O sujeito e a cena permanecem fixos; só o movimento (água, folhas, luz) é adicionado.

## Regra Fundamental

O prompt de **imagem** descreve a **cena**.  
O prompt de **vídeo** descreve o **movimento dentro da cena**.

## Passo a Passo de Transformação

### 1. Extrair elementos estáticos (MANter)

Tudo que não se move:
- Localização, setting, geografia
- Atmosfera, mood, iluminação geral
- Paleta de cores dominante
- Objetos grandes e fixos (montanhas, edifícios, árvores maduras)
- Composição geral (wide shot, close-up)

### 2. Remover termos de foto/câmara (DESCARTAR)

| Termo | Porquê remover |
|-------|---------------|
| photorealistic | Imagem já é realista; no vídeo soa a meta-pedido |
| 8k, highly detailed | Não descreve movimento; aumenta expectativa de sharpness que AnimateDiff não mantém |
| raw photo | Termo de processamento de imagem, não temporal |
| 24mm wide-angle lens, 50mm, f/1.8 | Especificação óptica estática; irrelevante para vídeo |
| deep depth of field, shallow depth of field | Conceito de foto; no vídeo o DOF é implícito na imagem base |
| National Geographic photography | Marca/editorial, não conteúdo |
| sharp focus throughout | Expectativa estática; vídeo tem motion blur natural |
| ultra-detailed | Pode forçar o modelo a "congelar" frames em vez de animar |
| best quality | Genérico, não adiciona informação de movimento |

### 3. Adicionar vocabulário de movimento por elemento

Para cada elemento da cena, descrever o movimento NATURAL e SUBTIL:

| Elemento | Vocabulário de movimento |
|----------|-------------------------|
| Água (rio, lago, oceano) | gentle ripples, concentric waves expanding softly, smooth water shimmer, subtle flow, surface glistening with soft reflections |
| Vegetação (relva, flores, árvores) | swaying softly in a light breeze, gentle rustling, subtle wind movement, individual blades swaying with micro-movements |
| Céu, nuvens | slowly drifting across the sky, morphing gradually, lazy floating, soft cloud movement |
| Luz, sol, lanternas, velas | warm flicker, golden shimmer, subtle pulsing glow, light dancing gently |
| Pétalas, folhas, penas | drifting lazily through the air, floating gently, scattered by soft wind, slow descent |
| Fogo, chamas | dancing flames, warm flicker, subtle undulation |
| Cabelo, tecidos, bandeiras | flowing softly, billowing gently in wind, subtle wave motion |
| Fumo, névoa, nevoeiro | slowly swirling, drifting lazily, ambient haze movement, gentle dispersion |
| Partículas, pólen, luzinhas | floating particles, gentle drift, subtle sparkle |

### 4. Adicionar termos de loop e continuidade temporal (SEMPRE no final)

Estes termos dizem ao AnimateDiff que o movimento deve ser cíclico e suave:

```
seamless infinite loop, smooth temporal continuity, gentle perpetual motion,
ambient movement only, no abrupt changes, seamless cyclic movement,
tranquil hypnotic atmosphere, slow cinematic motion
```

### 5. Prompt negativo reforçado para vídeo

Além dos negativos de qualidade habituais, adicionar:

```
static image, frozen frame, no motion, still picture, sudden movement,
jitter, flickering, jerky motion, blinking, morphing, warping,
inconsistent motion, double exposure, ghosting, crossfade, stutter
```

## Exemplo Completo

### Input (prompt de imagem)
```
masterpiece, best quality, photorealistic, 8k, highly detailed, raw photo,
a breathtaking landscape of a crystal-clear flowing river winding through
a vast lush green meadow, colorful wildflowers scattered in the grass,
gentle ripples reflecting the bright blue sky with soft white clouds,
distant rolling hills on the horizon, warm golden hour sunlight casting
long soft shadows, serene and peaceful atmosphere, ultra-detailed grass
blades and water textures, 24mm wide-angle lens, deep depth of field,
National Geographic photography, vibrant natural colors, sharp focus throughout
```

### Output (prompt de vídeo)
```
a breathtaking landscape of a crystal-clear river winding through a vast
lush green meadow, colorful wildflowers scattered in the grass gently
swaying in a soft breeze, gentle ripples expanding smoothly across the
water surface reflecting the bright blue sky, soft white clouds slowly
drifting and morphing in the sky, distant rolling hills on the horizon,
warm golden hour sunlight casting long soft shadows that subtly shift,
ultra-detailed grass blades swaying softly with individual micro-movements,
serene and peaceful atmosphere, gentle wind rustling through the meadow,
smooth water shimmer, vibrant natural colors, seamless infinite loop,
smooth temporal continuity, gentle perpetual motion, ambient movement only,
no abrupt changes, seamless cyclic movement, tranquil hypnotic atmosphere,
slow cinematic motion
```

## Regras de Ouro

1. **NUNCA inventar novos elementos** — só animar o que já existe na imagem
2. **NUNCA remover elementos da cena** — manter todos os objetos, só adicionar movimento
3. **NUNCA adicionar ações de humanos/animais** se não estavam no prompt original (ex: não adicionar "cat drinking" se o gato não estava na imagem)
4. **Movimento SUBTIL e NATURAL** — AnimateDiff funciona melhor com motion ambiental; ações rápidas causam jitter
5. **Evitar "fast", "rapid", "sudden"** — these cause temporal instability
6. **Manter a estrutura:** 1 frase de contexto → descrição elemento a elemento → termos de loop

## Negativo: o que acontece sem adaptação

Se usar o prompt de imagem diretamente no vídeo:
- Termos como "photorealistic" e "8k" não ajudam o motion module
- O modelo gasta capacidade a tentar manter sharpness em vez de gerar movimento suave
- A ausência de termos de loop faz o vídeo ter cortes ou transições bruscas
- O resultado é um vídeo que parece uma slideshow de imagens ligeiramente diferentes

## Referência

- Ficheiro: `D:\AI_Ecosystem\08_Config\prompt-adapters\image_to_video_system.md`
- Workflow: `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Video_creation\Videoloop_img2vid.json`
- Script: `D:\AI_Ecosystem\10_Projects\01_YTAutomation\Video_creation\generate_video.py`
