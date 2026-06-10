import gradio as gr
import subprocess
import json
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIG
# =============================================================================
ROOT_MUSIC = Path(r"D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation\music_sounds")
ROOT_NATURE = Path(r"D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation\nature_sounds")
TEMP_DIR = Path(r"D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation\temp")
ROOT_OUTPUT = Path(r"D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation\output")
ROOT_LOOPS = Path(r"D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation\Loops")
MIX_ROOT = Path(r"D:\AI_Ecosystem\10_Projects\01_YTAutomation\Music_creation")
AUDIO_EXTS = (".wav", ".flac", ".mp3", ".aif", ".aiff", ".ogg", ".m4a")
MAX_MIX_TRACKS = 8

for d in [TEMP_DIR, ROOT_OUTPUT, ROOT_LOOPS]:
    d.mkdir(parents=True, exist_ok=True)

# Limpar ficheiros temporarios de sessoes anteriores no arranque
def cleanup_temp():
    if TEMP_DIR.exists():
        for f in TEMP_DIR.iterdir():
            try:
                if f.is_file():
                    f.unlink()
            except Exception:
                pass

cleanup_temp()

# =============================================================================
# HELPERS
# =============================================================================
def run_cmd(cmd_list):
    try:
        r = subprocess.run(cmd_list, capture_output=True, text=True, check=False)
        return (r.returncode == 0), r.stdout, r.stderr
    except Exception as e:
        return False, "", str(e)

def get_audio_info(filepath):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(filepath)
    ]
    ok, out, err = run_cmd(cmd)
    if ok:
        lines = out.strip().splitlines()
        try:
            dur = float(lines[0]) if lines else 0.0
            size = int(lines[1]) if len(lines) > 1 else 0
            return dur, size
        except (ValueError, IndexError):
            pass
    return 0.0, 0

# =============================================================================
# GUI v6 — Tab Pipeline + Tab Mixer + Tab Créditos
# =============================================================================
with gr.Blocks(title="THE RENDER WAVE — Pipeline & Mixer") as demo:
    gr.Markdown("# 🌊 THE RENDER WAVE — Pipeline & Mixer")
    gr.Markdown("Pipeline: samples 8h | Mixer: mistura multi-track com volumes, atrasos e fades independentes.")

    # -------------------------------------------------------------------------
    # Estados
    # -------------------------------------------------------------------------
    state_m_file = gr.State(value="")
    state_n_file = gr.State(value="")
    state_step1 = gr.State(value="")
    state_step2 = gr.State(value="")
    state_step3 = gr.State(value="")
    state_selected_name = gr.State(value="")
    state_mix_tracks = gr.State(value=[])
    state_cred_file = gr.State(value="")

    with gr.Tabs():
        # ====================================================================
        # TAB 1: PIPELINE
        # ====================================================================
        with gr.TabItem("Pipeline"):
            with gr.Row():
                # ----------------------------------------------------
                # COLUNA 1: NAVEGACAO
                # ----------------------------------------------------
                with gr.Column(scale=1):
                    gr.Markdown("### 📂 Navegacao")
                    with gr.Tabs():
                        with gr.TabItem("Music Samples"):
                            m_explorer = gr.FileExplorer(
                                root_dir=str(ROOT_MUSIC),
                                glob="**/*",
                                ignore_glob="*.txt,*.md,*.json,*.yaml,*.yml",
                                file_count="single",
                                label="Music Samples",
                                height=300
                            )
                            m_info = gr.Textbox(label="Info Seleccionado", interactive=False, lines=3)
                            m_play = gr.Button("▶ Play Sample", variant="primary")

                        with gr.TabItem("Nature Sounds"):
                            n_explorer = gr.FileExplorer(
                                root_dir=str(ROOT_NATURE),
                                glob="**/*",
                                ignore_glob="*.txt,*.md,*.json,*.yaml,*.yml",
                                file_count="single",
                                label="Nature Sounds",
                                height=300
                            )
                            n_info = gr.Textbox(label="Info Seleccionado", interactive=False, lines=3)
                            n_play = gr.Button("▶ Play Sample", variant="primary")

                # ----------------------------------------------------
                # COLUNA 2: PREVIEW + VERIFICACAO
                # ----------------------------------------------------
                with gr.Column(scale=1):
                    gr.Markdown("### 🎧 Preview & Verificacao")
                    selected_display = gr.Textbox(label="Ficheiro Seleccionado", interactive=False)
                    preview_player = gr.Audio(label="Player", type="filepath", interactive=False)
                    preview_status = gr.Textbox(label="Status", interactive=False, lines=2)

                    gr.Markdown("---")
                    gr.Markdown("**Preview por Passo**")
                    with gr.Row():
                        preview_orig_btn = gr.Button("▶ Original", size="sm")
                        preview_s1_btn = gr.Button("▶ Passo 1", size="sm")
                        preview_s2_btn = gr.Button("▶ Passo 2", size="sm")
                        preview_s3_btn = gr.Button("▶ Passo 3 (30s)", size="sm")

                    gr.Markdown("---")
                    gr.Markdown("**Verificacoes**")
                    verify_step1 = gr.Textbox(label="Verificacao Passo 1", interactive=False, lines=2)
                    verify_step2 = gr.Textbox(label="Verificacao Passo 2", interactive=False, lines=2)
                    verify_step3 = gr.Textbox(label="Verificacao Passo 3", interactive=False, lines=2)

                # ----------------------------------------------------
                # COLUNA 3: PIPELINE + EXPORT
                # ----------------------------------------------------
                with gr.Column(scale=1):
                    gr.Markdown("### 🔄 Pipeline 3 Passos")

                    gr.Markdown("**Passo 1: Remover Silencio**")
                    p1_btn = gr.Button("▶ Executar Passo 1")
                    p1_info = gr.Textbox(label="Resultado", interactive=False, lines=3)

                    gr.Markdown("**Passo 2: Loop Perfeito**")
                    with gr.Row():
                        crossfade_s = gr.Number(label="Crossfade (s)", value=0.5, minimum=0.1, maximum=10.0, step=0.1)
                    p2_btn = gr.Button("▶ Executar Passo 2")
                    p2_info = gr.Textbox(label="Resultado", interactive=False, lines=3)

                    gr.Markdown("**Passo 3: Estender a 8h**")
                    p3_btn = gr.Button("▶ Executar Passo 3")
                    p3_info = gr.Textbox(label="Resultado", interactive=False, lines=3)

                    gr.Markdown("---")
                    gr.Markdown("**Export Final (Fade In/Out)**")
                    with gr.Row():
                        fade_in = gr.Number(label="Fade In (s)", value=10, minimum=0, maximum=300)
                        fade_out = gr.Number(label="Fade Out (s)", value=10, minimum=0, maximum=300)
                    p4_btn = gr.Button("▶ Exportar MP3", variant="primary")
                    p4_info = gr.Textbox(label="Resultado Export", interactive=False, lines=3)

                    gr.Markdown("---")
                    gr.Markdown("**Catalogo & Reset**")
                    with gr.Row():
                        cat_btn = gr.Button("🔄 Atualizar Catalogo", size="sm")
                        reset_btn = gr.Button("🗑️ Reset", size="sm")
                    cat_info = gr.Textbox(label="Catalogo", interactive=False, lines=2)
                    reset_info = gr.Textbox(label="Reset", interactive=False, lines=2)

        # ====================================================================
        # TAB 2: MIXER
        # ====================================================================
        with gr.TabItem("Mixer"):
            with gr.Row():
                # ----------------------------------------------------
                # COLUNA 1: SELECAO
                # ----------------------------------------------------
                with gr.Column(scale=1):
                    gr.Markdown("### 📂 Seleccionar Samples")
                    mix_explorer = gr.FileExplorer(
                        root_dir=str(MIX_ROOT),
                        glob="**/*",
                        ignore_glob="*.txt,*.md,*.json,*.yaml,*.yml",
                        file_count="single",
                        label="Procurar Sample",
                        height=300
                    )
                    mix_info = gr.Textbox(label="Info", interactive=False, lines=2)
                    mix_play = gr.Button("▶ Preview", variant="secondary")
                    mix_add_btn = gr.Button("➕ Adicionar ao Mix")
                    mix_clear_btn = gr.Button("🗑️ Limpar Mix")

                # ----------------------------------------------------
                # COLUNA 2: PLAYLIST + CONTROLES
                # ----------------------------------------------------
                with gr.Column(scale=2):
                    gr.Markdown("### 🎛️ Tracks")
                    mix_status = gr.Textbox(label="Estado do Mix", value="Nenhuma track", interactive=False)

                    # 8 slots com fade in/out por track
                    mix_names = []
                    mix_vols = []
                    mix_delays = []
                    mix_fade_ins = []
                    mix_fade_outs = []
                    for i in range(MAX_MIX_TRACKS):
                        with gr.Row():
                            t = gr.Textbox(label=f"Track {i+1}", value="", interactive=False)
                            v = gr.Slider(label="Vol %", minimum=0, maximum=200, value=100, step=1)
                            d = gr.Number(label="Atraso (s)", minimum=0, maximum=28800, value=0, step=1)
                            fi = gr.Number(label="Fade In (s)", minimum=0, maximum=30, value=0, step=0.5)
                            fo = gr.Number(label="Fade Out (s)", minimum=0, maximum=30, value=0, step=0.5)
                            mix_names.append(t)
                            mix_vols.append(v)
                            mix_delays.append(d)
                            mix_fade_ins.append(fi)
                            mix_fade_outs.append(fo)

                    gr.Markdown("---")
                    gr.Markdown("**Master**")
                    with gr.Row():
                        mix_fade_in = gr.Number(label="Fade In (s)", value=10, minimum=0, maximum=300)
                        mix_fade_out = gr.Number(label="Fade Out (s)", value=10, minimum=0, maximum=300)
                    mix_export_btn = gr.Button("▶ Exportar Mix (MP3)", variant="primary")
                    mix_result = gr.Textbox(label="Resultado", interactive=False, lines=3)

        # ====================================================================
        # TAB 3: CREDITOS
        # ====================================================================
        with gr.TabItem("Créditos"):
            with gr.Row():
                # ----------------------------------------------------
                # COLUNA 1: FILEEXPLORER + INFO
                # ----------------------------------------------------
                with gr.Column(scale=1):
                    gr.Markdown("### 📂 Seleccionar Ficheiro")
                    cred_explorer = gr.FileExplorer(
                        root_dir=str(MIX_ROOT),
                        glob="**/*",
                        ignore_glob="*.txt,*.md,*.json,*.yaml,*.yml",
                        file_count="single",
                        label="Navegar Samples",
                        height=300
                    )
                    cred_info = gr.Textbox(label="Info", interactive=False, lines=3)
                    cred_play = gr.Button("▶ Preview", variant="secondary")

                # ----------------------------------------------------
                # COLUNA 2: FORMULARIO
                # ----------------------------------------------------
                with gr.Column(scale=1):
                    gr.Markdown("### ✏️ Dados do Crédito")
                    cred_author = gr.Textbox(label="Autor / Criador", placeholder="ex: RichardAtmo")
                    cred_source = gr.Dropdown(
                        choices=["Freesound", "BBC", "Bandcamp", "Zapsplat", "Pixabay", "Outro"],
                        label="Fonte", allow_custom_value=True
                    )
                    cred_license = gr.Dropdown(
                        choices=["CC0", "CC-BY", "CC-BY-NC", "Royalty-free", "Unknown"],
                        label="Licença"
                    )
                    cred_line = gr.Textbox(label="Linha de Créditos", placeholder="Cole aqui o texto do site", lines=3)
                    cred_url = gr.Textbox(label="URL (opcional)", placeholder="https://...")
                    cred_add_btn = gr.Button("💾 Guardar / Actualizar", variant="primary")
                    cred_status = gr.Textbox(label="Status", interactive=False, lines=2)

                # ----------------------------------------------------
                # COLUNA 3: TABELA
                # ----------------------------------------------------
                with gr.Column(scale=2):
                    gr.Markdown("### 📊 Créditos Registados")
                    cred_table = gr.Dataframe(
                        headers=["Ficheiro", "Autor", "Fonte", "Licença", "Créditos"],
                        label="Tabela de Créditos",
                        interactive=False,
                        wrap=True
                    )
                    cred_export_info = gr.Textbox(
                        label="JSON Path",
                        value=str(ROOT_OUTPUT.parent / "sound_credits.json"),
                        interactive=False
                    )

    # ==========================================================================
    # EVENTOS — NAVEGACAO (Tab Pipeline)
    # ==========================================================================
    def m_select_file(relpath):
        if not relpath:
            return "Nenhum sample selecionado", None, "", "", ""
        fpath = ROOT_MUSIC / relpath
        fname = Path(relpath).name
        if not fpath.exists():
            return f"ERRO: Ficheiro nao encontrado: {fpath}", None, "", "", ""
        dur, size = get_audio_info(fpath)
        return (
            f"🎵 {fname}\n"
            f"⏱️ {dur:.2f}s | {size/1024/1024:.1f}MB\n"
            f"Path: {fpath}",
            str(fpath), fname, f"Seleccionado: {fname}", ""
        )

    m_explorer.change(fn=m_select_file, inputs=m_explorer,
                      outputs=[m_info, state_m_file, state_selected_name, selected_display, state_n_file])

    def m_play_file(relpath):
        if not relpath:
            return None, "Nenhum sample selecionado"
        fpath = ROOT_MUSIC / relpath
        if not fpath.exists():
            return None, f"ERRO: {fpath}"
        return str(fpath), f"A tocar: {Path(relpath).name}"

    m_play.click(fn=m_play_file, inputs=m_explorer, outputs=[preview_player, preview_status])

    def n_select_file(relpath):
        if not relpath:
            return "Nenhum som selecionado", None, "", "", ""
        fpath = ROOT_NATURE / relpath
        fname = Path(relpath).name
        if not fpath.exists():
            return f"ERRO: Ficheiro nao encontrado: {fpath}", None, "", "", ""
        dur, size = get_audio_info(fpath)
        return (f"🌊 {fname}\n"
                f"⏱️ {dur:.2f}s | {size/1024/1024:.1f}MB\n"
                f"Path: {fpath}", str(fpath), fname, f"Seleccionado: {fname}", "")

    n_explorer.change(fn=n_select_file, inputs=n_explorer, outputs=[n_info, state_n_file, state_selected_name, selected_display, state_m_file])

    def n_play_file(relpath):
        if not relpath:
            return None, "Nenhum som selecionado"
        fpath = ROOT_NATURE / relpath
        if not fpath.exists():
            return None, f"ERRO: {fpath}"
        return str(fpath), f"A tocar: {Path(relpath).name}"

    n_play.click(fn=n_play_file, inputs=n_explorer, outputs=[preview_player, preview_status])

    # ==========================================================================
    # PREVIEW POR PASSO
    # ==========================================================================
    def preview_orig(m_path, n_path):
        sample_path = m_path if m_path else n_path
        if not sample_path or not Path(sample_path).exists():
            return None, "Nenhum sample selecionado"
        return str(sample_path), f"Original: {Path(sample_path).name}"

    preview_orig_btn.click(fn=preview_orig, inputs=[state_m_file, state_n_file], outputs=[preview_player, preview_status])

    def preview_s1(path):
        if not path or not Path(path).exists():
            return None, "Passo 1 ainda nao executado"
        return path, f"Passo 1: {Path(path).name}"

    preview_s1_btn.click(fn=preview_s1, inputs=[state_step1], outputs=[preview_player, preview_status])

    def preview_s2(path):
        if not path or not Path(path).exists():
            return None, "Passo 2 ainda nao executado"
        return path, f"Passo 2: {Path(path).name}"

    preview_s2_btn.click(fn=preview_s2, inputs=[state_step2], outputs=[preview_player, preview_status])

    def preview_s3(path):
        if not path or not Path(path).exists():
            return None, "Passo 3 ainda nao executado"
        excerpt = TEMP_DIR / f"preview_30s_{Path(path).stem}.wav"
        cmd = ["ffmpeg", "-y", "-i", path, "-t", "30", "-acodec", "pcm_s16le", "-ar", "44100", str(excerpt)]
        ok, _, err = run_cmd(cmd)
        if not ok:
            return None, f"ERRO: {err}"
        return str(excerpt), f"Passo 3 (30s): {Path(path).name}"

    preview_s3_btn.click(fn=preview_s3, inputs=[state_step3], outputs=[preview_player, preview_status])

    # ==========================================================================
    # PIPELINE: PASSOS 1-3
    # ==========================================================================
    def exec_step1(m_path, n_path, selected_name):
        sample_path = m_path if m_path else n_path
        if not sample_path or not Path(sample_path).exists():
            return "ERRO: Seleciona um sample primeiro", None, ""
        base = Path(selected_name).stem
        output = TEMP_DIR / f"step1_silence_{base}.wav"
        temp_mid = TEMP_DIR / f"step1a_{base}.wav"
        cmd1 = [
            "ffmpeg", "-y", "-i", str(sample_path),
            "-af", "silenceremove=start_periods=1:start_duration=1:start_threshold=-50dB",
            "-acodec", "pcm_s16le", "-ar", "44100", str(temp_mid)
        ]
        ok1, _, err1 = run_cmd(cmd1)
        if not ok1:
            return f"ERRO FFmpeg (inicio): {err1}", None, ""
        cmd2 = [
            "ffmpeg", "-y", "-i", str(temp_mid),
            "-af", "areverse,silenceremove=start_periods=1:start_duration=1:start_threshold=-50dB,areverse",
            "-acodec", "pcm_s16le", "-ar", "44100", str(output)
        ]
        ok2, _, err2 = run_cmd(cmd2)
        try:
            temp_mid.unlink()
        except Exception:
            pass
        if not ok2:
            return f"ERRO FFmpeg (fim): {err2}", None, ""
        dur, size = get_audio_info(output)
        dur_orig, _ = get_audio_info(Path(sample_path))
        diff = dur_orig - dur
        return (
            f"✅ Passo 1 OK\nDur: {dur:.2f}s ({diff:.2f}s removidos)",
            str(output), f"✅ OK: {diff:.2f}s"
        )

    p1_btn.click(fn=exec_step1, inputs=[state_m_file, state_n_file, state_selected_name],
                 outputs=[p1_info, state_step1, verify_step1])

    def exec_step2(step1_audio, selected_name, cf_s):
        if not step1_audio or not Path(step1_audio).exists():
            return "ERRO: Executa Passo 1 primeiro", None, ""
        base = Path(selected_name).stem
        output = TEMP_DIR / f"step2_loop_{base}.wav"
        dur_before, _ = get_audio_info(Path(step1_audio))
        if dur_before < 1.0:
            return "ERRO: Ficheiro muito curto", None, ""
        fade_dur = float(cf_s)
        fade_out_start = max(0, dur_before - fade_dur)
        filter_complex = (
            f"[0:a]afade=t=out:st={fade_out_start}:d={fade_dur}[a0];"
            f"[1:a]afade=t=in:st=0:d={fade_dur}[a1];"
            f"[a0][a1]acrossfade=d={fade_dur}:c1=tri:c2=tri[loop]"
        )
        cmd = [
            "ffmpeg", "-y", "-i", str(step1_audio), "-i", str(step1_audio),
            "-filter_complex", filter_complex, "-map", "[loop]",
            "-acodec", "pcm_s16le", "-ar", "44100", str(output)
        ]
        ok, out, err = run_cmd(cmd)
        if not ok:
            return f"ERRO FFmpeg: {err}", None, ""
        dur_loop, _ = get_audio_info(output)
        expected = dur_before * 2
        diff = abs(dur_loop - expected)
        tolerance = max(0.5, fade_dur * 2)
        if diff > tolerance:
            return (f"⚠️ Verificacao FALHOU\nDur: {dur_loop:.2f}s | Esperado: {expected:.2f}s", None, f"FALHOU: {dur_loop:.2f}s")
        return (f"✅ Passo 2 OK\nDur: {dur_loop:.2f}s | Crossfade: {fade_dur:.1f}s", str(output), f"✅ OK: {dur_loop:.2f}s")

    p2_btn.click(fn=exec_step2, inputs=[state_step1, state_selected_name, crossfade_s],
                 outputs=[p2_info, state_step2, verify_step2])

    def exec_step3(step2_audio, selected_name):
        if not step2_audio or not Path(step2_audio).exists():
            return "ERRO: Executa Passo 2 primeiro", None, ""
        base = Path(selected_name).stem
        output_mp3 = ROOT_LOOPS / f"step3_8h_{base}.mp3"
        step2_dur, _ = get_audio_info(Path(step2_audio))
        if step2_dur <= 0:
            return "ERRO: Nao consegui ler duracao do step2", None, ""
        repeats = int(28800 / step2_dur) + 1
        concat_file = TEMP_DIR / f"concat_{base}.txt"
        audio_path = Path(step2_audio).resolve().as_posix()
        with open(concat_file, "w", encoding="utf-8") as f:
            for _ in range(repeats):
                f.write(f"file '{audio_path}'\n")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100",
            str(output_mp3)
        ]
        ok, out, err = run_cmd(cmd)
        try:
            concat_file.unlink()
        except Exception:
            pass
        if not ok:
            return f"ERRO FFmpeg: {err}", None, ""
        dur, size = get_audio_info(output_mp3)
        if dur < 28800:
            return (f"⚠️ Abaixo de 8h\nDur: {dur:.0f}s", None, f"FALHOU: {dur:.0f}s")
        return (f"✅ Passo 3 OK\nDur: {dur:.0f}s ({dur/3600:.1f}h) | {size/1024/1024:.0f}MB", str(output_mp3), f"✅ OK: {dur:.0f}s")

    p3_btn.click(fn=exec_step3, inputs=[state_step2, state_selected_name],
                 outputs=[p3_info, state_step3, verify_step3])

    # ==========================================================================
    # PIPELINE: EXPORT FINAL
    # ==========================================================================
    def exec_export(step3_audio, selected_name, fade_in_s, fade_out_s):
        if not step3_audio or not Path(step3_audio).exists():
            return "ERRO: Passo 3 ainda nao executado", None, ""
        output_mp3 = ROOT_OUTPUT / f"{Path(selected_name).stem}_8h_ambient.mp3"
        fade_in_s = float(fade_in_s)
        fade_out_s = float(fade_out_s)
        dur, _ = get_audio_info(Path(step3_audio))
        fade_out_start = max(0, dur - fade_out_s)
        filters = f"afade=t=in:st=0:d={fade_in_s},afade=t=out:st={fade_out_start}:d={fade_out_s}"
        cmd = [
            "ffmpeg", "-y", "-i", str(step3_audio),
            "-af", filters,
            "-codec:a", "libmp3lame", "-b:a", "192k",
            str(output_mp3)
        ]
        ok, out, err = run_cmd(cmd)
        if not ok:
            return f"ERRO FFmpeg: {err}", None, ""
        dur_final, size_final = get_audio_info(output_mp3)
        return (f"✅ MP3 exportado!\nDur: {dur_final:.0f}s | {size_final/1024/1024:.0f}MB\n{output_mp3.name}",
                str(output_mp3), str(output_mp3))

    p4_btn.click(fn=exec_export, inputs=[state_step3, state_selected_name, fade_in, fade_out],
                 outputs=[p4_info, preview_player, selected_display])

    # ==========================================================================
    # PIPELINE: ATUALIZAR CATALOGO + RESET
    # ==========================================================================
    def exec_update_catalog():
        try:
            music = []
            for f in sorted(ROOT_MUSIC.rglob("*")):
                if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
                    dur, size = get_audio_info(f)
                    rel = str(f.relative_to(ROOT_MUSIC)).replace("\\", "/")
                    music.append({
                        "relative_path": rel,
                        "name": f.name,
                        "folder": str(f.parent.relative_to(ROOT_MUSIC)) if f.parent != ROOT_MUSIC else "",
                        "category": "music",
                        "format": f.suffix.lower(),
                        "duration_sec": round(dur, 2) if dur else None,
                        "size_mb": round(size / (1024*1024), 1) if size else None,
                    })
            nature = []
            for f in sorted(ROOT_NATURE.rglob("*")):
                if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
                    dur, size = get_audio_info(f)
                    rel = str(f.relative_to(ROOT_NATURE)).replace("\\", "/")
                    nature.append({
                        "relative_path": rel,
                        "name": f.name,
                        "folder": str(f.parent.relative_to(ROOT_NATURE)) if f.parent != ROOT_NATURE else "",
                        "category": "nature",
                        "format": f.suffix.lower(),
                        "duration_sec": round(dur, 2) if dur else None,
                        "size_mb": round(size / (1024*1024), 1) if size else None,
                    })
            catalog = {
                "generated": "2026-06-11",
                "total_music": len(music),
                "total_nature": len(nature),
                "total": len(music) + len(nature),
                "files": music + nature,
            }
            cat_path = ROOT_OUTPUT.parent / "catalog.json"
            with open(cat_path, "w", encoding="utf-8") as fh:
                json.dump(catalog, fh, indent=2, ensure_ascii=False)
            return f"✅ Catalogo atualizado\nMusic: {len(music)} | Nature: {len(nature)} | Total: {len(music)+len(nature)}"
        except Exception as e:
            return f"ERRO: {e}"

    cat_btn.click(fn=exec_update_catalog, outputs=[cat_info])

    def exec_reset():
        cleaned = 0
        if TEMP_DIR.exists():
            for f in TEMP_DIR.iterdir():
                try:
                    if f.is_file():
                        f.unlink()
                        cleaned += 1
                except Exception:
                    pass
        mix_names_out = [""] * MAX_MIX_TRACKS
        mix_vols_out = [100] * MAX_MIX_TRACKS
        mix_delays_out = [0] * MAX_MIX_TRACKS
        mix_fade_ins_out = [0] * MAX_MIX_TRACKS
        mix_fade_outs_out = [0] * MAX_MIX_TRACKS
        return (
            "", "", "", "", "", "", [],
            None, "Reset completo",
            "", "", "", "", "", "", "", "", "", "",
            f"✅ Reset completo — {cleaned} ficheiros apagados em temp/",
            "Nenhuma track",
            *mix_names_out,
            *mix_vols_out,
            *mix_delays_out,
            *mix_fade_ins_out,
            *mix_fade_outs_out,
            "",
        )

    reset_btn.click(
        fn=exec_reset,
        outputs=[
            state_m_file, state_n_file, state_step1, state_step2, state_step3,
            state_selected_name, state_mix_tracks,
            preview_player, preview_status,
            selected_display, verify_step1, verify_step2, verify_step3,
            p1_info, p2_info, p3_info, p4_info, cat_info, reset_info,
            mix_status,
        ] + mix_names + mix_vols + mix_delays + mix_fade_ins + mix_fade_outs + [mix_result]
    )

    # ==========================================================================
    # MIXER: FUNCOES
    # ==========================================================================
    def mix_select_file(relpath):
        if not relpath:
            return "Nenhum ficheiro selecionado", None
        fpath = MIX_ROOT / relpath
        fname = Path(relpath).name
        if not fpath.exists():
            return f"ERRO: Nao encontrado: {fpath}", None
        dur, size = get_audio_info(fpath)
        return f"⏱️ {dur:.2f}s | {size/1024/1024:.1f}MB\n{fpath}", str(fpath)

    mix_explorer.change(fn=mix_select_file, inputs=mix_explorer, outputs=[mix_info, state_m_file])

    def mix_do_preview(relpath):
        if not relpath:
            return None, "Nenhum ficheiro selecionado"
        fpath = MIX_ROOT / relpath
        if not fpath.exists():
            return None, f"ERRO: {fpath}"
        return str(fpath), f"Preview: {Path(relpath).name}"

    mix_play.click(fn=mix_do_preview, inputs=mix_explorer, outputs=[preview_player, preview_status])

    def _build_slot_outputs(tracks_list, status_msg):
        names_out = []
        vols_out = []
        delays_out = []
        fade_ins_out = []
        fade_outs_out = []
        for i in range(MAX_MIX_TRACKS):
            if i < len(tracks_list):
                t = tracks_list[i]
                names_out.append(t["name"])
                vols_out.append(t.get("volume", 100))
                delays_out.append(t.get("delay", 0))
                fade_ins_out.append(t.get("fade_in", 0))
                fade_outs_out.append(t.get("fade_out", 0))
            else:
                names_out.append("")
                vols_out.append(100)
                delays_out.append(0)
                fade_ins_out.append(0)
                fade_outs_out.append(0)
        return [tracks_list] + names_out + vols_out + delays_out + fade_ins_out + fade_outs_out + [status_msg]

    def mix_add(tracks_list, sel_path):
        if not sel_path or not Path(sel_path).exists():
            return _build_slot_outputs(tracks_list, "Nenhum ficheiro selecionado")
        if len(tracks_list) >= MAX_MIX_TRACKS:
            return _build_slot_outputs(tracks_list, f"Limite de {MAX_MIX_TRACKS} tracks atingido")
        new_track = {"path": sel_path, "name": Path(sel_path).name, "fade_in": 0, "fade_out": 0}
        tracks_list = list(tracks_list) + [new_track]
        return _build_slot_outputs(tracks_list, f"✅ Adicionado: {new_track['name']} ({len(tracks_list)}/{MAX_MIX_TRACKS})")

    mix_add_btn.click(
        fn=mix_add,
        inputs=[state_mix_tracks, state_m_file],
        outputs=[state_mix_tracks] + mix_names + mix_vols + mix_delays + mix_fade_ins + mix_fade_outs + [mix_status]
    )

    def mix_clear():
        return _build_slot_outputs([], "🗑️ Mix limpo")

    mix_clear_btn.click(fn=mix_clear, outputs=[state_mix_tracks] + mix_names + mix_vols + mix_delays + mix_fade_ins + mix_fade_outs + [mix_status])

    # ==========================================================================
    # MIXER: EXPORT
    # ==========================================================================
    def exec_mixer_export(tracks_list, *args):
        if not tracks_list:
            return "ERRO: Adiciona pelo menos uma track ao mix"

        n = len(tracks_list)
        vols = args[:MAX_MIX_TRACKS]
        delays = args[MAX_MIX_TRACKS:MAX_MIX_TRACKS * 2]
        fade_ins = args[MAX_MIX_TRACKS * 2:MAX_MIX_TRACKS * 3]
        fade_outs = args[MAX_MIX_TRACKS * 3:MAX_MIX_TRACKS * 4]
        master_fade_in = float(args[MAX_MIX_TRACKS * 4])
        master_fade_out = float(args[MAX_MIX_TRACKS * 4 + 1])

        output_mp3 = ROOT_OUTPUT / f"mix_{n}tracks.mp3"

        inputs = []
        filter_parts = []
        max_dur = 0.0
        for i in range(n):
            track = tracks_list[i]
            vol = vols[i] / 100.0
            delay_ms = int(delays[i] * 1000)
            track_fade_in = float(fade_ins[i])
            track_fade_out = float(fade_outs[i])
            track_dur, _ = get_audio_info(track["path"])
            total_dur = track_dur + delays[i]
            if total_dur > max_dur:
                max_dur = total_dur

            # Build per-track filters: fade_in + fade_out + adelay + volume
            track_filters = []
            if track_fade_in > 0:
                track_filters.append(f"afade=t=in:st=0:d={track_fade_in}")
            if track_fade_out > 0:
                fade_out_start = max(0, track_dur - track_fade_out)
                track_filters.append(f"afade=t=out:st={fade_out_start}:d={track_fade_out}")
            track_filters.append(f"adelay={delay_ms}|{delay_ms}")
            track_filters.append(f"volume={vol}")

            filter_parts.append(f"[{i}:a]{','.join(track_filters)}[v{i}]")
            inputs.extend(["-i", track["path"]])

        if n == 1:
            mix_chain = "[v0]acopy[final]"
        elif n == 2:
            mix_chain = "[v0][v1]amix=inputs=2:duration=longest[final]"
        else:
            steps = []
            for i in range(n - 1):
                if i == 0:
                    steps.append(f"[v0][v1]amix=inputs=2:duration=longest[m0]")
                else:
                    steps.append(f"[m{i-1}][v{i+1}]amix=inputs=2:duration=longest[m{i}]")
            steps[-1] = steps[-1].replace(f"[m{n-2}]", "[final]")
            mix_chain = ";".join(steps)

        # Master fade in/out
        fade_out_start = max(0, max_dur - master_fade_out)
        fade_filters = f"afade=t=in:st=0:d={master_fade_in},afade=t=out:st={fade_out_start}:d={master_fade_out}"
        filter_complex = ";".join(filter_parts + [mix_chain, f"[final]{fade_filters}[out]"])

        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-codec:a", "libmp3lame", "-b:a", "192k",
            str(output_mp3)
        ]
        ok, out, err = run_cmd(cmd)
        if not ok:
            return f"ERRO FFmpeg: {err}"

        dur_final, size_final = get_audio_info(output_mp3)
        return (f"✅ Mix exportado!\n"
                f"Tracks: {n} | Dur: {dur_final:.0f}s | {size_final/1024/1024:.0f}MB\n"
                f"Ficheiro: {output_mp3.name}")

    mix_export_btn.click(
        fn=exec_mixer_export,
        inputs=[state_mix_tracks] + mix_vols + mix_delays + mix_fade_ins + mix_fade_outs + [mix_fade_in, mix_fade_out],
        outputs=[mix_result]
    )

    # ==========================================================================
    # CREDITOS: FUNCOES
    # ==========================================================================
    def _load_credits():
        cred_path = ROOT_OUTPUT.parent / "sound_credits.json"
        if cred_path.exists():
            try:
                with open(cred_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    return data.get("credits", {})
            except Exception:
                pass
        return {}

    def _save_credits(credits_dict):
        cred_path = ROOT_OUTPUT.parent / "sound_credits.json"
        data = {
            "metadata": {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "total_entries": len(credits_dict)
            },
            "credits": credits_dict
        }
        with open(cred_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    def _build_cred_table(credits_dict):
        rows = []
        for fname, info in sorted(credits_dict.items()):
            rows.append([
                fname,
                info.get("author", ""),
                info.get("source", ""),
                info.get("license", ""),
                info.get("credit_line", "")
            ])
        return rows

    def cred_select_file(relpath):
        if not relpath:
            return "Nenhum ficheiro selecionado", None, ""
        fpath = MIX_ROOT / relpath
        fname = Path(relpath).name
        if not fpath.exists():
            return f"ERRO: Nao encontrado: {fpath}", None, ""
        dur, size = get_audio_info(fpath)
        return (
            f"🎵 {fname}\n⏱️ {dur:.2f}s | {size/1024/1024:.1f}MB",
            str(fpath),
            f"Seleccionado: {fname}"
        )

    cred_explorer.change(fn=cred_select_file, inputs=cred_explorer,
                         outputs=[cred_info, state_cred_file, selected_display])

    def cred_play_file(relpath):
        if not relpath:
            return None, "Nenhum ficheiro selecionado"
        fpath = MIX_ROOT / relpath
        if not fpath.exists():
            return None, f"ERRO: {fpath}"
        return str(fpath), f"A tocar: {Path(relpath).name}"

    cred_play.click(fn=cred_play_file, inputs=cred_explorer, outputs=[preview_player, preview_status])

    def cred_add_or_update(file_path, author, source, license_val, line, url):
        if not file_path:
            return "ERRO: Seleciona um ficheiro primeiro", _build_cred_table(_load_credits())
        if not author or not line:
            return "ERRO: Autor e Créditos são obrigatórios", _build_cred_table(_load_credits())
        credits = _load_credits()
        credits[Path(file_path).name] = {
            "author": author,
            "source": source or "Unknown",
            "license": license_val or "Unknown",
            "credit_line": line,
            "url": url or ""
        }
        _save_credits(credits)
        return f"✅ Guardado: {Path(file_path).name} ({len(credits)} total)", _build_cred_table(credits)

    cred_add_btn.click(
        fn=cred_add_or_update,
        inputs=[state_cred_file, cred_author, cred_source, cred_license, cred_line, cred_url],
        outputs=[cred_status, cred_table]
    )

    # Init: load table on startup
    def cred_init():
        return _build_cred_table(_load_credits())

    demo.load(fn=cred_init, outputs=[cred_table])

if __name__ == "__main__":
    demo.launch(
        theme=gr.themes.Soft(),
        server_name="127.0.0.1",
        server_port=7861,
        share=False,
        inbrowser=False,
        allowed_paths=[
            str(ROOT_MUSIC),
            str(ROOT_NATURE),
            str(TEMP_DIR),
            str(ROOT_OUTPUT),
            str(ROOT_LOOPS),
            str(MIX_ROOT),
        ],
    )
    print("Abre o browser em http://127.0.0.1:7861")
