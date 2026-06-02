import requests
import json
import os

# Configuração
c comfyui_url = "http://192.168.144.1:8188"
prompt = "Uma paisagem tranquila ao pôr do sol, nuvens cor-de-rosa, lago calmo com reflexos, folhas e flores esvoaçantes, estilo anime"
model = "leosamsHelloworldXL_helloworldXL70.safetensors"
width = 1024
height = 768
output_path = "/mnt/d/AI_Ecosystem/04_Data/images/"

def generate_image():
    api_url = f"{comfyui_url}/prompt"
    
    # Workflow completo — CORRIGIDO
    workflow = {
        "prompt": {
            "3": {
                "inputs": {
                    "text": prompt,
                    "clip": ["5", 1]  # CLIP do CheckpointLoaderSimple
                },
                "class_type": "CLIPTextEncode",
            },
            "4": {
                "inputs": {
                    "text": "low quality, blurry, ugly, deformed",
                    "clip": ["5", 1]  # CLIP do CheckpointLoaderSimple
                },
                "class_type": "CLIPTextEncode",
            },
            "5": {
                "inputs": {
                    "ckpt_name": model,  # Correção: campo correto!
                },
                "class_type": "CheckpointLoaderSimple",
            },
            "6": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1
                },
                "class_type": "EmptyLatentImage",
            },
            "7": {
                "inputs": {
                    "samples": ["9", 0],
                    "vae": ["5", 2]  # VAE do CheckpointLoaderSimple
                },
                "class_type": "VAEDecode",
            },
            "8": {
                "inputs": {
                    "images": [7, 0],
                    "filename_prefix": "test_output"  # CORREÇÃO: campo obrigatório!
                },
                "class_type": "SaveImage",
            },
            "9": {
                "inputs": {
                    "seed": 42,
                    "steps": 20,
                    "cfg": 8,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["5", 0],  # Model do CheckpointLoaderSimple
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                    "latent_image": ["6", 0]
                },
                "class_type": "KSampler",
            }
        }
    }
    
    try:
        response = requests.post(api_url, json=workflow)
        if response.status_code == 200:
            print("✅ Requisição enviada com sucesso!")
            
            # Procurar a imagem mais recente no diretório
            files = [
                f for f in os.listdir(output_path) 
                if os.path.isfile(os.path.join(output_path, f)) and f.endswith('.png')
            ]
            if files:
                latest = max(files, key=lambda x: os.path.getmtime(os.path.join(output_path, x)))
                print(f"🎉 Imagem gerada: {latest}")
                print(f"📁 Caminho completo: {os.path.join(output_path, latest)}")
            else:
                print("❌ Nenhuma imagem encontrada. Verifique os logs do ComfyUI.")
        else:
            print(f"❌ Erro na API: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Falha ao enviar requisição: {e}")

generate_image()