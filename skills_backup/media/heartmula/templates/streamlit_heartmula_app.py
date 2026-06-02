"""
Streamlit app wrapper for HeartMuLa CLI.

Usage:
    uv pip install streamlit
    streamlit run streamlit_heartmula_app.py

Then open http://localhost:8501 in the browser.
"""

import streamlit as st
from pathlib import Path
from datetime import datetime

import subprocess as sp

# ------------------------------------------------------------------
# CONFIGURE — point to the actual HeartMuLa installation on Windows.
# Common paths: D:\AI_Ecosystem\09_Tools\heartlib  (adjust as needed)
# ------------------------------------------------------------------
HEARTLIB = Path(r"D:\AI_Ecosystem\09_Tools\heartlib")
VENV_PY = HEARTLIB / ".venv" / "Scripts" / "python.exe"
SCRIPT = HEARTLIB / "examples" / "run_music_generation.py"
CKPT = HEARTLIB / "ckpt"
OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

st.set_page_config(page_title="HeartMuLa", page_icon="🎵", layout="centered")


def call_heartmula(**kw):
    """Subprocess wrapper around the CLI."""
    lyrics_content = f"""[Intro]
{kw['intro']}

[Verse]
{kw['verses']}

[Chorus]
{kw['chorus']}

[Outro]
{kw['outros']}
"""
    rid = datetime.now().strftime("%Y%m%d_%H%M%S")
    lpath = OUT / f"{rid}_lyrics.txt"
    tpath = OUT / f"{rid}_tags.txt"
    mpath = OUT / f"{rid}.mp3"
    lpath.write_text(lyrics_content, encoding="utf-8")
    tpath.write_text(",".join(kw['tags']), encoding="utf-8")

    cmd = [
        str(VENV_PY), str(SCRIPT),
        f'--model_path={CKPT}', '--version=3B',
        f'--lyrics={lpath}', f'--tags={tpath}', f'--save_path={mpath}',
        f'--max_audio_length_ms={kw["duration_min"]*60*1000}',
        '--lazy_load', 'true',
        '--mula_device', 'cuda', '--codec_device', 'cuda',
    ]
    proc = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT,
                    text=True, cwd=str(HEARTLIB))
    logs = []
    for line in proc.stdout:
        logs.append(line.rstrip())
        yield line.rstrip()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("\n".join(logs[-20:]))
    yield mpath


def simple_preset(name):
    presets = {
        "Chuva na Floresta": {
            "intro": "Som suave de chuva a cair nas folhas",
            "verses": "Gotas escorrem pelo musgo verde, uma floresta antiga serena",
            "chorus": "A chuva canta a melodia da natureza, um hino eterno de paz",
            "outros": "Silencio gradual, apenas gotas distantes",
            "tags": ["rain", "nature", "piano", "ambient", "soft", "calm"],
        },
        "Praia ao Por-do-sol": {
            "intro": "Ondas suaves a quebrar na areia dourada",
            "verses": "Gaivotas pairam no ceu, o sol despede-se do mar",
            "chorus": "Breezes salgadas sussurram segredos de paz",
            "outros": "A mare baixa suavemente, silencio",
            "tags": ["ambient", "nature", "soft", "strings", "calm"],
        },
        "Meditacao Noturna": {
            "intro": "Escuridao envolvendo silenciosamente",
            "verses": "Estrelas emergem uma a uma, universo de quietude",
            "chorus": "O cosmos respira em ritmo lento, cancao de eternidade",
            "outros": "Silencio absoluto, apenas ser",
            "tags": ["meditation", "ambient", "soft", "synthesizer", "calm"],
        },
    }
    return presets.get(name, {"intro": "", "verses": "", "chorus": "", "outros": "", "tags": []})

# ------------------------------------------------------------------
with st.sidebar:
    st.title("🎵 HeartMuLa")
    preset = st.selectbox("Preset", ["(manual)", *simple_preset("").keys()])
    st.markdown("---")
    st.subheader("Tags")
    tag_opts = ["ambient", "calm", "drums", "guitar", "meditation",
                "nature", "orchestral", "piano", "rain", "relaxing",
                "soft", "strings", "synthesizer"]
    defaults = {"ambient", "soft", "calm"}
    sel_tags = [t for t in tag_opts if st.checkbox(t, value=(t in defaults))]

p = simple_preset(preset) if preset != "(manual)" else {}
st.title("Compositor de Musica Ambiente")

with st.form("gen"):
    c1, c2 = st.columns(2)
    with c1:
        intro = st.text_area("Intro", value=p.get("intro", ""), height=80)
        chorus = st.text_area("Chorus", value=p.get("chorus", ""), height=80)
    with c2:
        verses = st.text_area("Versos", value=p.get("verses", ""), height=80)
        outros = st.text_area("Outro", value=p.get("outros", ""), height=80)

    tags = st.multiselect("Tags", tag_opts, default=p.get("tags", sel_tags))
    duration = st.slider("Duracao (min)", 1, 4, 2)
    submitted = st.form_submit_button("🚀 Gerar Musica")

if submitted:
    if not tags:
        st.warning("Seleciona pelo menos uma tag.")
    else:
        progress = st.progress(0, text="A inicializar...")
        log_box = st.empty()
        logs = []

        gen = call_heartmula(intro=intro, verses=verses, chorus=chorus,
                            outros=outros, tags=tags, duration_min=duration)
        result = None
        for msg in gen:
            logs.append(msg)
            log_box.code("\n".join(logs[-25:]))
            low = msg.lower()
            if "load" in low or "download" in low:
                progress.progress(10, text="A carregar modelos...")
            elif "generat" in low or "sampl" in low:
                progress.progress(60, text="A gerar audio (~4 min)...")
            elif "save" in low or "done" in low:
                progress.progress(95, text="A guardar...")
            elif isinstance(msg, Path):
                result = msg

        if result and result.exists():
            progress.progress(100, text="Concluido!")
            st.success(f"Gerado: {result.name}")
            st.audio(str(result))
            with open(result, "rb") as f:
                st.download_button("Download MP3", f.read(), result.name, "audio/mpeg")
        else:
            progress.progress(100, text="Erro")
            log_box.code("\n".join(logs))
