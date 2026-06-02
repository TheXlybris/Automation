#!/usr/bin/env python3
"""
ACE Step API Batch Generator + Concatenator
=============================================
Gera N clips de musica ambiente via ComfyUI API e concatena-os com ffmpeg.

Uso:
    python ace_step_batch.py --count 10 --preset rain --duration 110
    python ace_step_batch.py --preset ocean --count 5 --concat

Autor: Hermes Agent
"""

import argparse
import json
import time
import random
import subprocess
from pathlib import Path
import requests

COMFYUI_URL = "http://192.168.0.187:8188"
OUTPUT_DIR = Path(r"D:\AI_Ecosystem\02_Engines\ComfyUI\ComfyUI\output\audio")

WORKFLOW = json.loads(open("ace_step_api_workflow.json").read())

PRESETS = {
    "rain": {
        "tags": "ambient instrumental, soft atmospheric pads, gentle rain on leaves, distant low thunder rumble, nature soundscape, no vocals, no lyrics, relaxing meditation music, seamless loop, slow tempo, 60 BPM",
        "lyrics": "[instrumental]", "bpm": 60, "keyscale": "A minor"
    },
    "ocean": {
        "tags": "ambient instrumental, ocean waves on shore, soft sea breeze, coastal atmosphere, no vocals, no lyrics, relaxing meditation music, seamless loop",
        "lyrics": "[instrumental]", "bpm": 55, "keyscale": "E major"
    },
    "forest": {
        "tags": "ambient instrumental, wind rustling through pine trees, forest ambience, distant birdsong, nature soundscape, no vocals, no lyrics",
        "lyrics": "[instrumental]", "bpm": 50, "keyscale": "C major"
    },
}


def send_workflow(tags, lyrics, bpm, duration, keyscale, cfg, temp, seed, prefix):
    wf = json.loads(json.dumps(WORKFLOW))  # copy
    wf["94"]["inputs"]["tags"] = tags
    wf["94"]["inputs"]["lyrics"] = lyrics
    wf["94"]["inputs"]["bpm"] = int(bpm)
    wf["94"]["inputs"]["duration"] = float(duration)
    wf["94"]["inputs"]["keyscale"] = keyscale
    wf["94"]["inputs"]["cfg_scale"] = float(cfg)
    wf["94"]["inputs"]["temperature"] = float(temp)
    wf["94"]["inputs"]["seed"] = ["109", 0]
    wf["109"]["inputs"]["value"] = seed
    wf["98"]["inputs"]["seconds"] = float(duration)
    wf["107"]["inputs"]["filename_prefix"] = prefix
    wf["107"]["inputs"]["audioUI"] = ""

    payload = {"prompt": wf, "client_id": f"batch-{int(time.time())}"}
    resp = requests.post(f"{COMFYUI_URL}/api/prompt", json=payload, timeout=30)
    if resp.status_code == 200:
        return resp.json().get("prompt_id"), seed
    return None, seed


def poll_job(prompt_id, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if prompt_id in data and data[prompt_id].get("status", {}).get("completed"):
                    outputs = data[prompt_id].get("outputs", {})
                    if "107" in outputs and outputs["107"].get("audio"):
                        return outputs["107"]["audio"][0]["filename"]
        except:
            pass
        time.sleep(2)
    return None


def generate_clips(preset_name, count, duration, cfg, temp, seed_start, prefix):
    preset = PRESETS.get(preset_name, PRESETS["rain"])
    files = []
    for i in range(count):
        s = seed_start + i if seed_start else random.randint(1, 2**63)
        print(f"[{i+1}/{count}] Enviando clip com seed {s}...")
        pid, _ = send_workflow(
            preset["tags"], preset["lyrics"], preset["bpm"],
            duration, preset["keyscale"], cfg, temp, s, prefix
        )
        if pid:
            fname = poll_job(pid)
            if fname:
                print(f"    -> {fname}")
                files.append(fname)
            else:
                print(f"    -> TIMEOUT/FALHA")
        else:
            print(f"    -> ERRO ao enviar")
    return files


def concat_clips(files, output_name, crossfade=3):
    if not files:
        print("Nenhum ficheiro para concatenar.")
        return
    list_path = OUTPUT_DIR / f"_concat_list_{int(time.time())}.txt"
    with open(list_path, 'w') as f:
        for fname in files:
            p = str(OUTPUT_DIR / fname).replace("\\", "/")
            f.write(f"file '{p}'\n")

    out = OUTPUT_DIR / output_name
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-af", f"acrossfade=d={crossfade},loudnorm=I=-16:TP=-1.5:LRA=11",
        "-b:a", "320k", str(out)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    list_path.unlink(missing_ok=True)
    if result.returncode == 0:
        print(f"Concatenado: {out}")
    else:
        print(f"Erro FFmpeg: {result.stderr[:400]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", default="rain", choices=list(PRESETS.keys()))
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--duration", type=int, default=110)
    parser.add_argument("--cfg", type=float, default=2.0)
    parser.add_argument("--temp", type=float, default=0.85)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--prefix", default="audio/ACE_Step_batch")
    parser.add_argument("--concat", action="store_true", help="Concatenar apos gerar")
    parser.add_argument("--crossfade", type=int, default=3)
    parser.add_argument("--output", default="ambient_loop.mp3")
    args = parser.parse_args()

    print(f"Gerando {args.count} clip(s) com preset '{args.preset}' ({args.duration}s cada)...")
    fnames = generate_clips(args.preset, args.count, args.duration, args.cfg, args.temp, args.seed, args.prefix)

    if args.count == 1:
        print(f"Clip gerado: {fnames[0] if fnames else 'FALHA'}")
    else:
        print(f"\n{len(fnames)}/{args.count} clips gerados com sucesso.")
        if args.concat and fnames:
            print(f"A concatenar {len(fnames)} clips...")
            concat_clips(fnames, args.output, args.crossfade)
