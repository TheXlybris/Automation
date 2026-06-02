"""
Render Wave - Music Creator + Concatenator
============================================
GUI Streamlit para gerar musica via ComfyUI ACE Step v1.5 XL Turbo
e concatenar clips com ffmpeg.

Autor: Hermes Agent
Criado: 2026-06-02 (v2 - corrigido)

Uso:
    streamlit run music_creator_gui.py
"""

import streamlit as st
import requests
import json
import time
import os
import subprocess
import random
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

COMFYUI_URL = "http://192.168.0.187:8188"
AUDIO_DIR = Path(r"D:\AI_Ecosystem\02_Engines\ComfyUI\ComfyUI\output\audio")
IMAGE_DIR = Path(r"D:\AI_Ecosystem\02_Engines\ComfyUI\ComfyUI\output")

# ============================================================
# DEFAULTS
# ============================================================

DEFAULTS = {
    "tags": "ambient instrumental, soft atmospheric pads, gentle rain on leaves, distant low thunder rumble, subtle ocean waves, wind rustling through pine trees, nature soundscape, no vocals, no lyrics, relaxing meditation music, seamless loop, slow tempo",
    "lyrics": "[instrumental]",
    "bpm": 60,
    "duration": 110,
    "keyscale": "A minor",
    "cfg_scale": 2.0,
    "temperature": 0.85,
    "filename_prefix": "audio/ACE_Step1.5_gui",
}

KEY_SCALES = [
    "C major", "D major", "E major", "F major", "G major", "A major", "B major",
    "C minor", "D minor", "E minor", "F minor", "G minor", "A minor", "B minor",
]

PRESETS = {
    "Rain & Thunder": {
        "tags": "ambient instrumental, soft atmospheric pads, gentle rain on leaves, distant low thunder, nature soundscape, no vocals, no lyrics, relaxing meditation music, seamless loop",
        "keyscale": "A minor", "bpm": 60,
    },
    "Ocean Waves": {
        "tags": "ambient instrumental, ocean waves on shore, soft sea breeze, coastal atmosphere, no vocals, no lyrics, relaxing meditation music, seamless loop",
        "keyscale": "E major", "bpm": 55,
    },
    "Forest Wind": {
        "tags": "ambient instrumental, wind rustling through pine trees, forest ambience, birdsong distant, no vocals, no lyrics, relaxing meditation music, seamless loop",
        "keyscale": "C major", "bpm": 50,
    },
    "Night Stars": {
        "tags": "ambient instrumental, deep space pads, starry night, cosmos atmosphere, soft synth drones, no vocals, no lyrics, relaxing sleep music, seamless loop",
        "keyscale": "D minor", "bpm": 45,
    },
    "Heavy Rain Storm": {
        "tags": "ambient instrumental, heavy rain on rooftop, thunderstorm rumble, deep sub bass, atmospheric fog, no vocals, no lyrics, intense rain ambience",
        "keyscale": "G minor", "bpm": 55,
    },
    "Soft Morning": {
        "tags": "ambient instrumental, soft morning light, gentle birdsong, calm water ripples, warm analog pads, peaceful awakening, no vocals, no lyrics",
        "keyscale": "F major", "bpm": 65,
    },
    "Fireplace": {
        "tags": "ambient instrumental, warm fireplace crackle, cozy cabin, soft wooden creaks, warm amber feeling, no vocals, no lyrics, relaxing sleep music",
        "keyscale": "C major", "bpm": 50,
    },
    "Snowy Mountains": {
        "tags": "ambient instrumental, cold mountain wind, snow crunching underfoot, alpine silence, crystalline ice textures, no vocals, no lyrics",
        "keyscale": "A minor", "bpm": 40,
    },
}

# ============================================================
# SESSION STATE INIT
# ============================================================

def init_session():
    if "batch_queue" not in st.session_state:
        st.session_state.batch_queue = []
    if "job_history" not in st.session_state:
        st.session_state.job_history = []
    if "monitor_job" not in st.session_state:
        st.session_state.monitor_job = None
    if "batch_running" not in st.session_state:
        st.session_state.batch_running = False
    if "coherence_seed" not in st.session_state:
        st.session_state.coherence_seed = None
    if "coherence_mode" not in st.session_state:
        st.session_state.coherence_mode = False

init_session()

# ============================================================
# WORKFLOW
# ============================================================

def get_base_workflow():
    return {
        "3": {
            "inputs": {
                "seed": ["109", 0], "steps": 8, "cfg": 1.0,
                "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
                "model": ["78", 0], "positive": ["94", 0], "negative": ["47", 0],
                "latent_image": ["98", 0]
            },
            "class_type": "KSampler", "_meta": {"title": "KSampler"}
        },
        "18": {
            "inputs": {"samples": ["3", 0], "vae": ["106", 0]},
            "class_type": "VAEDecodeAudio", "_meta": {"title": "VAE Decode Audio"}
        },
        "47": {
            "inputs": {"conditioning": ["94", 0]},
            "class_type": "ConditioningZeroOut", "_meta": {"title": "ConditioningZeroOut"}
        },
        "78": {
            "inputs": {"shift": 3.0, "model": ["104", 0]},
            "class_type": "ModelSamplingAuraFlow", "_meta": {"title": "ModelSamplingAuraFlow"}
        },
        "94": {
            "inputs": {
                "tags": DEFAULTS["tags"], "lyrics": DEFAULTS["lyrics"],
                "seed": ["109", 0], "bpm": DEFAULTS["bpm"],
                "duration": float(DEFAULTS["duration"]), "timesignature": "4",
                "language": "en", "keyscale": DEFAULTS["keyscale"],
                "generate_audio_codes": True, "cfg_scale": DEFAULTS["cfg_scale"],
                "temperature": DEFAULTS["temperature"], "top_p": 0.9,
                "top_k": 0, "min_p": 0.0, "clip": ["105", 0]
            },
            "class_type": "TextEncodeAceStepAudio1.5", "_meta": {"title": "TextEncodeAceStepAudio1.5"}
        },
        "98": {
            "inputs": {"seconds": float(DEFAULTS["duration"]), "batch_size": 1},
            "class_type": "EmptyAceStep1.5LatentAudio", "_meta": {"title": "Empty Ace Step 1.5 Latent Audio"}
        },
        "104": {
            "inputs": {"unet_name": "acestep_v1.5_xl_turbo_bf16.safetensors", "weight_dtype": "default"},
            "class_type": "UNETLoader", "_meta": {"title": "Load Diffusion Model"}
        },
        "105": {
            "inputs": {
                "clip_name1": "qwen_0.6b_ace15.safetensors",
                "clip_name2": "qwen_4b_ace15.safetensors",
                "type": "ace", "device": "default"
            },
            "class_type": "DualCLIPLoader", "_meta": {"title": "DualCLIPLoader"}
        },
        "106": {
            "inputs": {"vae_name": "ace_1.5_vae.safetensors"},
            "class_type": "VAELoader", "_meta": {"title": "Load VAE"}
        },
        "107": {
            "inputs": {
                "filename_prefix": DEFAULTS["filename_prefix"],
                "quality": "V0", "audioUI": "", "audio": ["18", 0]
            },
            "class_type": "SaveAudioMP3", "_meta": {"title": "Save Audio (MP3)"}
        },
        "109": {
            "inputs": {"value": 0},
            "class_type": "PrimitiveInt", "_meta": {"title": "Int (Seed)"}
        }
    }

# ============================================================
# API
# ============================================================

def check_comfyui():
    try:
        resp = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
        return resp.status_code == 200
    except:
        return False

def get_system_info():
    try:
        resp = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            devs = data.get("devices", [{}])
            d = devs[0] if devs else {}
            return {
                "vram_total": d.get("vram_total", 0) // (1024**2),
                "vram_free": d.get("vram_free", 0) // (1024**2),
                "version": data.get("system", {}).get("comfyui_version", "?"),
            }
    except:
        pass
    return {"vram_total": 0, "vram_free": 0, "version": "?"}

def get_queue_info():
    try:
        resp = requests.get(f"{COMFYUI_URL}/queue", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "running": len(data.get("queue_running", [])),
                "pending": len(data.get("queue_pending", [])),
            }
    except:
        pass
    return {"running": -1, "pending": -1}

def send_workflow(tags, lyrics, bpm, duration, keyscale, cfg_scale, temperature, seed=None, prefix=None, client_id=None, jitter=0.0):
    wf = get_base_workflow()
    if seed is None or seed == 0:
        seed = random.randint(1, 2**63 - 1)
    
    wf["94"]["inputs"]["tags"] = tags
    wf["94"]["inputs"]["lyrics"] = lyrics
    wf["94"]["inputs"]["bpm"] = int(bpm)
    wf["94"]["inputs"]["duration"] = float(duration) + jitter
    wf["94"]["inputs"]["keyscale"] = keyscale
    wf["94"]["inputs"]["cfg_scale"] = float(cfg_scale)
    wf["94"]["inputs"]["temperature"] = float(temperature)
    wf["109"]["inputs"]["value"] = seed
    wf["98"]["inputs"]["seconds"] = float(duration) + jitter
    wf["107"]["inputs"]["filename_prefix"] = prefix if prefix else DEFAULTS["filename_prefix"]
    wf["107"]["inputs"]["audioUI"] = ""
    
    if client_id is None:
        client_id = f"gui-{int(time.time())}-{random.randint(1000,9999)}"
    payload = {"prompt": wf, "client_id": client_id}
    resp = requests.post(f"{COMFYUI_URL}/api/prompt", json=payload, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        return True, data.get("prompt_id"), seed
    return False, f"HTTP {resp.status_code}: {resp.text[:200]}", seed

def get_job_status(prompt_id):
    try:
        resp = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if prompt_id in data:
                job = data[prompt_id]
                return {
                    "found": True,
                    "completed": job.get("status", {}).get("completed", False),
                    "outputs": job.get("outputs", {}),
                }
    except Exception as e:
        return {"found": False, "error": str(e)}
    return {"found": False}

# ============================================================
# FFMPEG
# ============================================================

def concat_mp3s(files, output_path, crossfade=3):
    files = [str(f) for f in files]
    if not files:
        return False, "Nenhum ficheiro selecionado"
    if len(files) == 1:
        import shutil
        shutil.copy(files[0], str(output_path))
        return True, str(output_path)
    
    list_file = Path(output_path).parent / f"_concat_{int(time.time())}.txt"
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for mp3 in files:
                p = os.path.abspath(mp3).replace("\\", "/")
                f.write(f"file '{p}'\n")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-af", f"acrossfade=d={crossfade},loudnorm=I=-16:TP=-1.5:LRA=11",
            "-b:a", "320k", str(output_path)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.returncode == 0, (r.stderr[:500] if r.returncode != 0 else str(output_path))
    finally:
        if list_file.exists():
            list_file.unlink()

def list_mp3s():
    if not AUDIO_DIR.exists():
        return []
    files = list(AUDIO_DIR.glob("*.mp3"))
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files

def mp3_info(fp):
    try:
        p = Path(fp)
        sz = p.stat().st_size / (1024 * 1024)
        est = (p.stat().st_size * 8) / (250 * 1024)
        return {"size_mb": sz, "est_s": est}
    except:
        return {"size_mb": 0, "est_s": 0}

def remove_silence(input_path, output_path):
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", "silenceremove=start_periods=1:start_duration=0.1:start_threshold=-50dB:end_periods=1:end_duration=0.1:end_threshold=-50dB",
        "-b:a", "320k", str(output_path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, (r.stderr[:400] if r.returncode != 0 else str(output_path))

# ============================================================
# BATCH
# ============================================================

def add_to_queue(tags, lyrics, bpm, duration, keyscale, cfg, temp, count, seed_start):
    dur = max(duration, 90) if st.session_state.coherence_mode else duration
    for i in range(count):
        if st.session_state.coherence_mode and st.session_state.coherence_seed is not None:
            s = st.session_state.coherence_seed
        else:
            s = seed_start + i if seed_start > 0 else random.randint(1, 2**63 - 1)
        st.session_state.batch_queue.append({
            "id": f"batch_{len(st.session_state.batch_queue)}_{int(time.time()*1000) % 100000}",
            "tags": tags, "lyrics": lyrics, "bpm": bpm,
            "duration": dur, "keyscale": keyscale,
            "cfg_scale": cfg, "temperature": temp,
            "seed": s, "status": "pending", "prompt_id": None,
            "output_file": None,
        })


def set_coherence_seed_on_first_run(prompt_id):
    """No Coherence Mode, se a seed ainda nao foi definida, guarda a seed usada.
    Chamado quando o primeiro item do batch muda para 'running'."""
    if st.session_state.coherence_mode and st.session_state.coherence_seed is None:
        for item in st.session_state.batch_queue:
            if item["status"] == "running" and item.get("seed_used") is not None:
                st.session_state.coherence_seed = item["seed_used"]
                break

def process_one_batch():
    for idx, item in enumerate(st.session_state.batch_queue):
        if item["status"] == "pending":
            # Coherence Mode: se ja temos seed, usa-a; senao deixa aleatorio
            if st.session_state.coherence_mode and st.session_state.coherence_seed is not None:
                use_seed = st.session_state.coherence_seed
            else:
                use_seed = item["seed"]
            ok, pid, seed = send_workflow(
                item["tags"], item["lyrics"], item["bpm"],
                item["duration"], item["keyscale"],
                item["cfg_scale"], item["temperature"],
                seed=use_seed,
                prefix=f"{DEFAULTS['filename_prefix']}_item{item['id'][-5:]}",
                client_id=f"gui-batch-{item['id']}",
                jitter=round(idx * 0.01, 2)
            )
            if ok:
                item["status"] = "running"
                item["prompt_id"] = pid
                item["seed_used"] = seed
            else:
                item["status"] = "failed"
                item["error"] = str(pid)
            break
    else:
        st.session_state.batch_running = False

def refresh_batch():
    """Verifica estado dos jobs running e atualiza para completed/failed."""
    for item in st.session_state.batch_queue:
        if item["status"] == "running" and item.get("prompt_id"):
            stt = get_job_status(item["prompt_id"])
            if stt["found"]:
                if stt["completed"]:
                    if "107" in stt["outputs"] and stt["outputs"]["107"].get("audio"):
                        item["status"] = "completed"
                        item["output_file"] = stt["outputs"]["107"]["audio"][0]["filename"]
                    else:
                        item["status"] = "completed"
                        item["output_file"] = None


def clear_pending():
    """Remove todos os items com status 'pending' da queue."""
    st.session_state.batch_queue = [
        i for i in st.session_state.batch_queue if i["status"] != "pending"
    ]


def clear_all_queue():
    """Remove TODOS os items da queue (pending, running, completed, failed)."""
    st.session_state.batch_queue = []


def remove_queue_item(idx):
    """Remove item especifico por index. Apenas se for pending ou failed."""
    if 0 <= idx < len(st.session_state.batch_queue):
        if st.session_state.batch_queue[idx]["status"] in ("pending", "failed"):
            st.session_state.batch_queue.pop(idx)

# --- session state para presets ---
if "t1_tags" not in st.session_state:
    st.session_state.t1_tags = DEFAULTS["tags"]
    st.session_state.t1_bpm = DEFAULTS["bpm"]
    st.session_state.t1_key = DEFAULTS["keyscale"]
    st.session_state.t2_tags = DEFAULTS["tags"]
    st.session_state.t2_bpm = DEFAULTS["bpm"]
    st.session_state.t2_key = DEFAULTS["keyscale"]

def apply_preset_t1():
    p = st.session_state.get("t1_preset", "(Custom)")
    if p in PRESETS:
        st.session_state.t1_tags = PRESETS[p]["tags"]
        st.session_state.t1_bpm = PRESETS[p]["bpm"]
        st.session_state.t1_key = PRESETS[p]["keyscale"]

def apply_preset_t2():
    p = st.session_state.get("t2_preset", "(Custom)")
    if p in PRESETS:
        st.session_state.t2_tags = PRESETS[p]["tags"]
        st.session_state.t2_bpm = PRESETS[p]["bpm"]
        st.session_state.t2_key = PRESETS[p]["keyscale"]

# ============================================================
# STREAMLIT UI
# ============================================================

st.set_page_config(page_title="Render Wave - Music Creator", page_icon="🎵", layout="wide")
st.title("🎵 Render Wave - Music Creator")

# --- Barra estado ---
cols = st.columns([2, 1, 1, 1])
comfy_ok = check_comfyui()
info = get_system_info()
q = get_queue_info()
with cols[0]:
    if comfy_ok:
        st.success(f"ComfyUI v{info['version']} OK")
    else:
        st.error("ComfyUI offline")
with cols[1]:
    st.info(f"VRAM: {info['vram_free']}/{info['vram_total']} MB")
with cols[2]:
    st.info(f"Queue: {q['running']} running / {q['pending']} pending")
with cols[3]:
    st.info(f"MP3s: {len(list_mp3s())}")

st.divider()

# --- TABS ---
t1, t2, t3 = st.tabs(["Gerar Clip", "Batch / Agendar", "Concatenar & Ouvir"])

# ============================================================
# TAB 1: GERAR CLIP
# ============================================================
with t1:
    st.subheader("Gerar um clip individual")
    
    preset = st.selectbox("Preset", ["(Custom)"] + list(PRESETS.keys()),
                          key="t1_preset", on_change=apply_preset_t1)
    
    cur_tags = st.session_state.t1_tags
    cur_bpm = st.session_state.t1_bpm
    cur_key = st.session_state.t1_key
    
    c1, c2, c3 = st.columns(3)
    with c1:
        dur = st.number_input("Duracao (s)", 30, 300, DEFAULTS["duration"], 10, key="t1_dur")
    with c2:
        bpm = st.number_input("BPM", 30, 200, cur_bpm, 5, key="t1_bpm")
    with c3:
        key = st.selectbox("Key", KEY_SCALES,
                           index=KEY_SCALES.index(cur_key) if cur_key in KEY_SCALES else 0,
                           key="t1_key")
    
    tags = st.text_area("Tags", value=cur_tags, height=120, key="t1_tags")
    lyrics = st.text_area("Lyrics (manter [instrumental])", value=DEFAULTS["lyrics"], height=70, key="t1_lyrics")
    
    with st.expander("Avancado", expanded=False):
        a1, a2, a3 = st.columns(3)
        with a1:
            cfg = st.number_input("CFG Scale", 0.0, 100.0, DEFAULTS["cfg_scale"], 0.5, key="t1_cfg")
        with a2:
            temp = st.number_input("Temperature", 0.0, 2.0, DEFAULTS["temperature"], 0.05, key="t1_temp")
        with a3:
            seed = st.number_input("Seed (0=rand)", 0, 2147483647, 0, key="t1_seed")
        prefix = st.text_input("Filename prefix", value=DEFAULTS["filename_prefix"], key="t1_prefix")
    
    # Botoes
    bcols = st.columns([3, 1])
    with bcols[0]:
        if st.button("Enviar para ComfyUI", type="primary", use_container_width=True, key="t1_send"):
            if not comfy_ok:
                st.error("ComfyUI esta offline")
            else:
                with st.spinner("A enviar..."):
                    ok, pid, used_seed = send_workflow(
                        tags, lyrics, bpm, dur, key,
                        cfg, temp,
                        seed=seed if seed > 0 else None,
                        prefix=prefix
                    )
                if ok:
                    st.success(f"Enviado! Prompt ID: {pid}")
                    st.session_state.monitor_job = pid
                    st.session_state.job_history.append({
                        "prompt_id": pid, "seed": used_seed,
                        "tags": tags[:50], "time": datetime.now().strftime("%H:%M:%S"),
                        "status": "running"
                    })
                else:
                    st.error(f"Erro: {pid}")
    with bcols[1]:
        if st.button("Adicionar ao Batch", use_container_width=True, key="t1_queue"):
            add_to_queue(tags, lyrics, bpm, dur, key, cfg, temp, count=1, seed_start=seed)
            st.success(f"Adicionado! Queue: {len(st.session_state.batch_queue)}")
    
    # Monitor simplificado (sem time.sleep/rerun infinito)
    if st.session_state.monitor_job:
        st.divider()
        st.subheader("Estado do Job")
        pid = st.session_state.monitor_job
        stt = get_job_status(pid)
        if stt["found"]:
            if stt["completed"]:
                st.success("Completado!")
                if "107" in stt["outputs"]:
                    audios = stt["outputs"]["107"].get("audio", [])
                    if audios:
                        fname = audios[0]["filename"]
                        fpath = AUDIO_DIR / fname
                        st.info(f"Ficheiro: {fname}")
                        if fpath.exists():
                            st.audio(str(fpath))
                        else:
                            st.caption(f"Caminho: {fpath}")
                if st.button("Limpar monitor", key="t1_clear"):
                    st.session_state.monitor_job = None
            else:
                st.info("A processar... (clica 'Atualizar' abaixo)")
                col_ref, col_stop = st.columns(2)
                with col_ref:
                    if st.button("Atualizar estado", key="t1_refresh"):
                        st.rerun()
                with col_stop:
                    if st.button("Cancelar monitor", key="t1_stop"):
                        st.session_state.monitor_job = None
                        st.rerun()
        else:
            st.warning(f"Job {pid}: nao encontrado ainda. Verifica queue.")
            if st.button("Verificar novamente", key="t1_check"):
                st.rerun()

# ============================================================
# TAB 2: BATCH  (v3 - com auto-polling + controlo queue)
# ============================================================
with t2:
    st.subheader("Batch - Gerar multiplos clips")

    bpreset = st.selectbox("Preset", ["(Custom)"] + list(PRESETS.keys()),
                           key="t2_preset", on_change=apply_preset_t2)

    bt = st.session_state.t2_tags
    bb = st.session_state.t2_bpm
    bk = st.session_state.t2_key

    c1, c2, c3 = st.columns(3)
    with c1:
        bdur = st.number_input("Duracao (s)", 30, 300, DEFAULTS["duration"], 10, key="t2_dur")
    with c2:
        bbpm = st.number_input("BPM", 30, 200, bb, 5, key="t2_bpm")
    with c3:
        bkey = st.selectbox("Key", KEY_SCALES,
                            index=KEY_SCALES.index(bk) if bk in KEY_SCALES else 0,
                            key="t2_key")

    btags = st.text_area("Tags", value=bt, height=100, key="t2_tags")
    blyrics = st.text_area("Lyrics", value=DEFAULTS["lyrics"], height=60, key="t2_lyrics")

    r1, r2, r3, r4 = st.columns([2, 2, 2, 1])
    with r1:
        bcfg = st.number_input("CFG", 0.0, 100.0, DEFAULTS["cfg_scale"], 0.5, key="t2_cfg")
    with r2:
        btemp = st.number_input("Temp", 0.0, 2.0, DEFAULTS["temperature"], 0.05, key="t2_temp")
    with r3:
        bseed = st.number_input("Seed inicial", 0, 2147483647, 0, key="t2_seed")
    with r4:
        bcount = st.number_input("N clips", 1, 50, 3, key="t2_count")

    col_add, col_run = st.columns([2, 3])
    with col_add:
        if st.button("Adicionar ao Queue", type="primary", use_container_width=True, key="t2_add"):
            add_to_queue(btags, blyrics, bbpm, bdur, bkey, bcfg, btemp, bcount, bseed)
            st.success(f"{bcount} clips adicionados! Total: {len(st.session_state.batch_queue)}")
    with col_run:
        if st.button("Iniciar Batch", use_container_width=True, key="t2_run"):
            st.session_state.batch_running = True
            if st.session_state.coherence_mode:
                set_coherence_seed_on_first_run(None)  # seed sera definida no 1. envio
            process_one_batch()
            st.rerun()

    # --- Coherence Mode Toggle ---
    coh = st.toggle("Coherence Mode", value=st.session_state.coherence_mode, key="t2_coherence_toggle",
                     help="Todas as musicas do batch usam a mesma seed. Auto forca duracao ≥ 90s.")
    st.session_state.coherence_mode = coh

    if st.session_state.coherence_mode:
        if bdur < 90:
            st.warning(f"Modo Coherence ativo: duracao subida automaticamente de {bdur}s para 90s (menos de 90s nao e coerente).")
            # Note: Streamlit nao permite alterar widget values programaticamente, mas o send_workflow vai usar 90
        if st.session_state.coherence_seed is not None:
            st.info(f"Seed coerente activa: `{st.session_state.coherence_seed}` (todos os clips deste batch usam esta seed)")
        else:
            st.caption("Seed sera definida automaticamente apos a 1. faixa. Desactiva e reactiva para resetar.")
    elif st.session_state.coherence_seed is not None:
        # Modo desactivado, limpa seed
        st.session_state.coherence_seed = None

    # --- Botoes de controlo da queue ---
    if st.session_state.batch_queue:
        ctrl_cols = st.columns([2, 2, 2, 3])
        with ctrl_cols[0]:
            if st.button("Limpar Queue (todos)", key="t2_clear", use_container_width=True):
                st.session_state.batch_queue = []
                st.session_state.batch_running = False
                st.rerun()
        with ctrl_cols[1]:
            if st.button("Limpar concluidos", key="t2_clear_done", use_container_width=True):
                st.session_state.batch_queue = [
                    i for i in st.session_state.batch_queue if i["status"] != "completed"
                ]
                st.rerun()
        with ctrl_cols[2]:
            if st.button("Parar Batch", key="t2_stop", use_container_width=True):
                st.session_state.batch_running = False
                st.rerun()
        with ctrl_cols[3]:
            st.caption("O Batch processa 1 clip de cada vez e avanca automaticamente.")

    # --- Auto-polling: verifica estado de running e lanca proximo ---
    refresh_batch()

    pending  = [i for i in st.session_state.batch_queue if i["status"] == "pending"]
    running  = [i for i in st.session_state.batch_queue if i["status"] == "running"]
    completed= [i for i in st.session_state.batch_queue if i["status"] == "completed"]
    failed   = [i for i in st.session_state.batch_queue if i["status"] == "failed"]

    st.divider()
    st.subheader(f"Queue: {len(st.session_state.batch_queue)} items")
    st.caption(f"Running: {len(running)} | Pending: {len(pending)} | Completed: {len(completed)} | Failed: {len(failed)}")

    if st.session_state.batch_queue:
        for idx, it in enumerate(st.session_state.batch_queue[:20]):
            icon = {"pending": "O", "running": ">", "completed": "+", "failed": "X"}.get(it["status"], "?")
            qcols = st.columns([0.4, 0.5, 3, 1, 1, 1, 0.8])
            with qcols[0]:
                st.text(f"#{idx+1}")
            with qcols[1]:
                st.text(icon)
            with qcols[2]:
                st.text(it["tags"][:40])
            with qcols[3]:
                st.text(f"{it['duration']}s")
            with qcols[4]:
                st.text(f"s:{it['seed']}")
            with qcols[5]:
                st.text(it["status"])
            with qcols[6]:
                if it["status"] in ("pending", "failed"):
                    if st.button("X", key=f"t2_rm_{idx}_{it['id']}", help="Remover da queue"):
                        remove_queue_item(idx)
                        st.rerun()
                elif it["status"] == "completed" and it.get("output_file"):
                    st.text("OK")

    # --- Motor auto-progressivo ---
    if st.session_state.batch_running:
        if running:
            st.divider()
            st.info(f"A processar clip ({len(completed)+1}/{len(st.session_state.batch_queue)}) — aguardando ComfyUI...")
            ritem = running[0]
            # --- Coherence: captura seed da 1. faixa ---
            if st.session_state.coherence_mode and st.session_state.coherence_seed is None:
                if ritem.get("seed_used") is not None:
                    st.session_state.coherence_seed = ritem["seed_used"]
            stt = get_job_status(ritem.get("prompt_id", ""))
            if stt["found"] and stt["completed"]:
                # Ja completou — refresh_batch apanhou, agora avanca
                st.rerun()
            else:
                # Ainda running — auto-refreesh com sleep
                time.sleep(3)
                st.rerun()
        elif pending:
            st.divider()
            st.info(f"A avancar para o proximo ({len(completed)+1}/{len(st.session_state.batch_queue)})...")
            process_one_batch()
            time.sleep(1)
            st.rerun()
        else:
            st.divider()
            st.success(f"Batch terminado! {len(completed)} gerados, {len(failed)} falhas.")
            st.session_state.batch_running = False

# ============================================================
# TAB 3: CONCATENAR + PREVIEW
# ============================================================
with t3:
    st.subheader("Concatenar clips + Preview")
    
    mp3s = list_mp3s()
    
    if not mp3s:
        st.warning(f"Nenhum MP3 encontrado em:\n{AUDIO_DIR}")
        st.info("Gera clips primeiro nos tabs anteriores.")
    else:
        st.info(f"{len(mp3s)} MP3(s) disponiveis.")
        
        # --- Botao Apagar Tudo com confirmação ---
        with st.expander("🗑️ Gestao de ficheiros", expanded=False):
            st.caption("CUIDADO: esta operacao nao pode ser desfeita.")
            if st.checkbox("Confirmo que quero apagar TODOS os MP3s da pasta audio", key="t3_confirm_delete_all"):
                if st.button("APAGAR TUDO", type="primary", key="t3_del_all"):
                    deleted = 0
                    failed = 0
                    for mp3 in mp3s:
                        try:
                            mp3.unlink()
                            deleted += 1
                        except Exception:
                            failed += 1
                    st.success(f"Apagados: {deleted} | Falhas: {failed}")
                    time.sleep(1)
                    st.rerun()
        
        # Lista com preview
        for mp3 in mp3s[:30]:
            info = mp3_info(mp3)
            with st.container():
                f1, f2, f3, f4 = st.columns([3, 1, 1, 1])
                with f1:
                    st.text(f"{mp3.name}")
                with f2:
                    st.text(f"{info['size_mb']:.1f} MB")
                with f3:
                    st.text(f"~{info['est_s']:.0f}s")
                with f4:
                    if st.button("Del", key=f"del_{mp3.name}"):
                        try:
                            mp3.unlink()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro a apagar: {e}")
                
                with st.expander("Ouvir"):
                    try:
                        st.audio(str(mp3))
                    except Exception as e:
                        st.error(f"Erro a carregar audio: {e}")
                st.divider()
        
        # Concatenacao
        st.subheader("Concatenar seleccionados")
        names = [f.name for f in mp3s]
        sel = st.multiselect("Selecciona MP3s (ordem de uniao):", options=names, default=names[:2] if len(names) >= 2 else [], key="t3_sel")
        
        if sel:
            sel_paths = [AUDIO_DIR / n for n in sel]
            est_total = sum(mp3_info(p)["est_s"] for p in sel_paths)
            
            cc1, cc2 = st.columns(2)
            with cc1:
                xf = st.slider("Crossfade (s)", 1, 10, 3, key="t3_xf")
            with cc2:
                out_name = st.text_input("Nome output", value=f"concat_{int(time.time())}.mp3", key="t3_out")
            
            st.caption(f"Seleccionados: {len(sel)} | Estimado: ~{est_total/60:.1f} min ({est_total:.0f}s)")
            
            cbtn, sbtn = st.columns(2)
            with cbtn:
                if st.button("Concatenar com FFmpeg", type="primary", use_container_width=True, key="t3_concat"):
                    out = AUDIO_DIR / out_name
                    with st.spinner(f"A processar {len(sel)} clips..."):
                        ok, res = concat_mp3s(sel_paths, out, xf)
                    if ok:
                        st.success("Concatenado com sucesso!")
                        try:
                            st.audio(str(out))
                        except:
                            pass
                        st.info(f"Output: {out} ({Path(res).stat().st_size/(1024*1024):.1f} MB)")
                    else:
                        st.error(f"Erro FFmpeg: {res}")
            with sbtn:
                if sel and st.button("Remover silencio (1o)", use_container_width=True, key="t3_sil"):
                    inp = sel_paths[0]
                    out = AUDIO_DIR / f"nosil_{sel[0]}"
                    with st.spinner("A remover silencio..."):
                        ok, res = remove_silence(inp, out)
                    if ok:
                        st.success(f"Removido: {out.name}")
                        try:
                            st.audio(str(out))
                        except:
                            pass
                    else:
                        st.error(f"Erro: {res}")

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("Ajuda")
    
    st.subheader("Gerar Clip")
    st.markdown("""
1. Escolhe um **Preset** ou preenche manualmente
2. Mantem **Lyrics** = `[instrumental]`
3. Ajusta **Duration** + **BPM**
4. Clica **Enviar para ComfyUI**
5. ComfyUI processa ~1-2 min
""")
    
    st.subheader("Batch")
    st.markdown("""
- Adiciona N clips a queue
- Clica **Iniciar Batch**
- Processa 1 de cada vez
- Cada clip = seed diferente
""")
    
    st.subheader("Concatenar")
    st.markdown("""
- Escolhe MP3s
- Ajusta **Crossfade**
- Define nome output
- Ouve antes de juntar
""")
    
    st.subheader("Regras ACE Step")
    st.markdown("""
- Lyrics = apenas `[instrumental]`
- NAO usar: `[Verse]`, `[Chorus]`, `[rain]`
- Tags: `no vocals, no lyrics`
- Fade-out ~110s - usar crossfade
""")
    
    st.divider()
    st.caption(f"ComfyUI: {COMFYUI_URL}")
    st.caption(f"Audio: {AUDIO_DIR}")
    st.caption(f"Queue: {len(st.session_state.batch_queue)} | Jobs: {len(st.session_state.job_history)}")
