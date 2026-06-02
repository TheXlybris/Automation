# ACE Step v1.5 Model Downloads — Direct Links

Quick reference for downloading ACE Step v1.5 model files from HuggingFace.

## Split-File Layout (for `audio_ace_step1_5_xl_*.json` templates)

| File | Size | Destination | Direct Download URL |
|------|------|-------------|---------------------|
| `acestep_v1.5_xl_base_bf16.safetensors` | ~5.7 GB | `models/diffusion_models/` | https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_xl_base_bf16.safetensors |
| `acestep_v1.5_xl_turbo_bf16.safetensors` | ~5.7 GB | `models/diffusion_models/` | https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors |
| `acestep_v1.5_xl_sft_bf16.safetensors` | ~5.7 GB | `models/diffusion_models/` | https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_xl_sft_bf16.safetensors |
| `ace_1.5_vae.safetensors` | ~300 MB | `models/vae/` | https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors |
| `qwen_0.6b_ace15.safetensors` | ~1.2 GB | `models/text_encoders/` | https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_0.6b_ace15.safetensors |
| `qwen_4b_ace15.safetensors` | ~8.5 GB | `models/text_encoders/` | https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_4b_ace15.safetensors |

**Recommended subset for Turbo:** `turbo_bf16` + `ace_1.5_vae` + `qwen_0.6b_ace15` + `qwen_4b_ace15` = ~15.7 GB total.

## All-in-One Layout (for `audio_ace_step_1_t2a_*.json` v1 templates)

| File | Size | Destination | Direct Download URL |
|------|------|-------------|---------------------|
| `ace_step_v1_3.5b.safetensors` | ~3.5 GB | `models/checkpoints/` | https://huggingface.co/Comfy-Org/ACE-Step_ComfyUI_repackaged/resolve/main/all_in_one/ace_step_v1_3.5b.safetensors |

## Using `comfy-cli` to Download

```bash
comfy model download \
  --url "https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors" \
  --relative-path models/diffusion_models

comfy model download \
  --url "https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors" \
  --relative-path models/vae

comfy model download \
  --url "https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_0.6b_ace15.safetensors" \
  --relative-path models/text_encoders

comfy model download \
  --url "https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_4b_ace15.safetensors" \
  --relative-path models/text_encoders
```

## Verification

After download, confirm presence:
```bash
ls ComfyUI/models/diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors
ls ComfyUI/models/vae/ace_1.5_vae.safetensors
ls ComfyUI/models/text_encoders/qwen_0.6b_ace15.safetensors
ls ComfyUI/models/text_encoders/qwen_4b_ace15.safetensors
```
