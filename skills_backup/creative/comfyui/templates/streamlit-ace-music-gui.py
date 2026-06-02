import streamlit as st
import requests
import json
import time
import os
import subprocess
import random
from pathlib import Path
from datetime import datetime

COMFYUI_HOST = "192.168.0.187"
COMFYUI_PORT = 8188
COMFYUI_URL = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"

DEFAULT_WORKFLOW = {
    "3": {"inputs": {"seed": ["109", 0], "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0, "model": ["78", 0], "positive": ["94", 0], "negative": ["47", 0], "latent_image": ["98", 0]}, "class_type": "KSampler", "_meta": {"title": "KSampler"}},
    "18": {"inputs": {"samples": ["3", 0], "vae": ["106", 0]}, "class_type": "VAEDecodeAudio", "_meta": {"title": "VAE Decode Audio"}},
    "47": {"inputs": {"conditioning": ["94", 0]}, "class_type": "ConditioningZeroOut", "_meta": {"title": "ConditioningZeroOut"}},
    "78": {"inputs": {"shift": 3.0, "model": ["104", 0]}, "class_type": "ModelSamplingAuraFlow", "_meta": {"title": "ModelSamplingAuraFlow"}},
    "94": {"inputs": {"tags": "ambient instrumental, soft atmospheric pads, gentle rain, distant thunder, ocean waves, wind rustling through pine trees, nature soundscape, no vocals, no lyrics, seamless loop, slow tempo, 60 BPM", "lyrics": "[instrumental]", "seed": ["109", 0], "bpm": 60, "duration": 110.0, "timesignature": "4", "language": "en", "keyscale": "A minor", "generate_audio_codes": True, "cfg_scale": 2.0, "temperature": 0.85, "top_p": 0.9, "top_k": 0, "min_p": 0.0, "clip": ["105", 0]}, "class_type": "TextEncodeAceStepAudio1.5", "_meta": {"title": "TextEncodeAceStepAudio1.5"}},
    "98": {"inputs": {"seconds": 110.0, "batch_size": 1}, "class_type": "EmptyAceStep1.5LatentAudio", "_meta": {"title": "Empty Ace Step 1.5 Latent Audio"}},
    "104": {"inputs": {"unet_name": "acestep_v1.5_xl_turbo_bf16.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader", "_meta": {"title": "Load Diffusion Model"}},
    "105": {"inputs": {"clip_name1": "qwen_0.6b_ace15.safetensors", "clip_name2": "qwen_4b_ace15.safetensors", "type": "ace", "device": "default"}, "class_type": "DualCLIPLoader", "_meta": {"title": "DualCLIPLoader"}},
    "106": {"inputs": {"vae_name": "ace_1.5_vae.safetensors"}, "class_type": "VAELoader", "_meta": {"title": "Load VAE"}},
    "107": {"inputs": {"filename_prefix": "audio/ACE_Step1.5_gui", "quality": "V0", "audioUI": "", "audio": ["18", 0]}, "class_type": "SaveAudioMP3", "_meta": {"title": "Save Audio (MP3)"}},
    "109": {"inputs": {"value": 0}, "class_type": "PrimitiveInt", "_meta": {"title": "Int (Seed)"}}
}

OUTPUT_DIR = Path(r"D:\AI_Ecosystem\02_Engines\ComfyUI\ComfyUI\output\audio")


def build_workflow(tags, lyrics, bpm, duration, keyscale, seed=None):
    wf = json.loads(json.dumps(DEFAULT_WORKFLOW))
    if seed is None or seed == 0:
        seed = random.randint(1, 2**63)
    wf["94"]["inputs"]["tags"] = tags
    wf["94"]["inputs"]["lyrics"] = lyrics
    wf["94"]["inputs"]["bpm"] = int(bpm)
    wf["94"]["inputs"]["duration"] = float(duration)
    wf["94"]["inputs"]["keyscale"] = keyscale
    wf["109"]["inputs"]["value"] = seed
    wf["98"]["inputs"]["seconds"] = float(duration)
    wf["107"]["inputs"]["audioUI"] = ""
    wf["107"]["inputs"]["filename_prefix"] = "audio/ACE_Step1.5_gui"
    return wf, seed


def send_to_comfyui(wf, client_id=None):
    if client_id is None:
        client_id = f"music-gui-{int(time.time())}"
    payload = {"prompt": wf, "client_id": client_id}
    try:
        resp = requests.post(f"{COMFYUI_URL}/api/prompt", json=payload, timeout=30)
        if resp.status_code == 200:
            return True, resp.json()
        return False, {"error": f"Erro {resp.status_code}: {resp.text[:300]}"}
    except Exception as e:
        return False, {"error": str(e)}


st.set_page_config(page_title="Music Creator + Concatenator", layout="wide")
st.title("🎵 ACE Step v1.5 Music Creator + FFmpeg Concatenator")
st.caption("ComfyUI v1.5 XL Turbo — Instrumental Ambient Generator | Para o projeto RENDER WAVE")

with st.sidebar:
    st.header("⚙️ Configuração")
    host_input = st.text_input("Host ComfyUI", value=COMFYUI_HOST)
    port_input = st.number_input("Porta", value=COMFYUI_PORT, step=1)
    COMFYUI_URL = f"http://{host_input}:{int(port_input)}"
    st.markdown("**Pasta de output:**")
    st.code(str(OUTPUT_DIR), language="text")
    if st.button("🔄 Testar Ligação ComfyUI"):
        try:
            resp = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
            if resp.status_code == 200:
                d = resp.json()
                st.success("✅ ComfyUI online!")
                st.text(f"Versão: {d['system']['comfyui_version']}\nPyTorch: {d['system']['pytorch_version']}")
            else:
                st.error(f"❌ Erro {resp.status_code}")
        except Exception as e:
            st.error(f"❌ Não ligado: {e}")


tab_gen, tab_concat, tab_files, tab_about = st.tabs(["🎼 Gerar Clip", "🔗 Concatenar Clips", "📁 Ficheiros Gerados", "ℹ️ Sobre"])

with tab_gen:
    st.subheader("Parâmetros de Geração")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        duration = st.slider("Duração (s)", 30, 240, 110, 10)
    with col2:
        bpm = st.number_input("BPM", 30, 200, 60, 5)
    with col3:
        keyscale = st.selectbox("Tonalidade", ["C major", "C minor", "D major", "D minor", "E major", "E minor", "F major", "F minor", "G major", "G minor", "A major", "A minor", "B major", "B minor"], index=11)
    with col4:
        cfg_scale = st.slider("CFG Scale", 0.5, 10.0, 2.0, 0.5)
    
    tags = st.text_area("Tags", value="ambient instrumental, soft atmospheric pads, gentle rain on leaves, distant low thunder rumble, subtle ocean waves lapping shore, wind rustling through pine trees, nature soundscape, no vocals, no lyrics, relaxing meditation music, seamless loop, slow tempo, 60 BPM", height=80)
    lyrics = st.text_area("Lyrics", value="[instrumental]", height=60, help="DEIXE APENAS '[instrumental]' para evitar voz. Qualquer outro texto pode gerar voz.")
    if lyrics.strip() != "[instrumental]":
        st.warning("⚠️ ATENÇÃO: Para instrumental puro, deixa apenas '[instrumental]'.")
    seed_val = st.number_input("Seed (0 = aleatório)", 0, value=0, step=1)
    
    if st.button("🚀 ENVIAR PARA COMFYUI", type="primary", use_container_width=True):
        wf, used_seed = build_workflow(tags, lyrics.strip(), bpm, duration, keyscale, seed_val if seed_val > 0 else None)
        wf["94"]["inputs"]["cfg_scale"] = float(cfg_scale)
        with st.spinner("A enviar pedido para ComfyUI..."):
            success, result = send_to_comfyui(wf)
        if success:
            prompt_id = result.get("prompt_id", "?")
            st.success(f"✅ Pedido enviado! Prompt ID: `{prompt_id}` | Seed: {used_seed}")
        else:
            st.error(f"❌ Erro: {result.get('error', 'Erro desconhecido')}")

with tab_concat:
    st.subheader("🔗 Concatenar Clips com FFmpeg (em desenvolvimento)")
    st.info("Esta secção será implementada no próximo desenvolvimento.")

with tab_files:
    st.subheader("📁 Ficheiros MP3")
    if OUTPUT_DIR.exists():
        mp3s = sorted(OUTPUT_DIR.glob("*.mp3"), key=lambda x: x.stat().st_mtime, reverse=True)
        if mp3s:
            st.info(f"Total: **{len(mp3s)}** MP3s")
            for f in mp3s[:10]:
                st.markdown(f"**{f.name}** — {f.stat().st_size//1024:,} KB")
        else:
            st.warning("Pasta vazia.")
    else:
        st.warning(f"Pasta não encontrada: {OUTPUT_DIR}")

with tab_about:
    st.subheader("ℹ️ Sobre")
    st.markdown("Music Creator + Concatenator para o projeto RENDER WAVE. ACE Step v1.5 XL Turbo via ComfyUI API.")
    st.markdown("Regras: Lyrics = APENAS '[instrumental]' para evitar voz. Duration = 110s para consistência.")

st.divider()
st.caption(f"ComfyUI: {COMFYUI_URL} | Output: {OUTPUT_DIR}")
