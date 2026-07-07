#!/usr/bin/env python3
"""docscraper_gui — Interface gráfica para a ferramenta docscraper.

Permite extrair documentação de qualquer site com um clique:
- Colar URL do site de docs
- Escolher pasta de output
- Selecionar camada específica ou automático
- Ver log em tempo real
- Barra de progresso
"""

import os
import sys
import threading
import time
import queue
import subprocess
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ── Constantes ──────────────────────────────────────────────
APP_TITLE = "docscraper — Universal Docs Extractor"
APP_VERSION = "1.0.0"
APP_DESC = (
    "Extrai TODA a documentação de qualquer site.\n"
    "5 camadas em cascata: llms.txt → sitemap → link discovery → GitHub → wget → Playwright.\n"
    "Local, gratuito, sem limites de API."
)

# Camadas disponíveis
LAYERS = [
    ("auto", "Automático (recomendado)"),
    ("llms_txt", "0 — llms.txt / llms-full"),
    ("sitemap", "0 — sitemap.xml"),
    ("link_discovery", "1 — Link discovery"),
    ("github", "2 — GitHub source"),
    ("wget", "3 — wget mirror"),
    ("playwright", "4 — Playwright (SPAs)"),
]

# Cores
BG = "#1e1e2e"
BG_PANEL = "#181825"
BG_ENTRY = "#313244"
FG = "#cdd6f4"
FG_DIM = "#a6adc8"
ACCENT = "#89b4fa"
ACCENT_HOVER = "#74c7ec"
SUCCESS = "#a6e3a1"
ERROR = "#f38ba8"
WARNING = "#f9e2af"
BORDER = "#45475a"


class DocScraperGUI:
    """Janela principal do GUI."""

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("780x680")
        self.root.minsize(680, 580)
        self.root.configure(bg=BG)

        # Estado
        self.is_running = False
        self.log_queue = queue.Queue()
        self.process = None

        # Tentar tema escuro
        self._setup_theme()

        # Construir UI
        self._build_header()
        self._build_input_panel()
        self._build_options_panel()
        self._build_log_panel()
        self._build_status_bar()

        # Poll log queue
        self.root.after(100, self._poll_log)

    # ── Tema ──────────────────────────────────────────────────
    def _setup_theme(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("TButton", background=BG_ENTRY, foreground=FG,
                        font=("Segoe UI", 10), borderwidth=0, padding=8)
        style.map("TButton",
                  background=[("active", ACCENT_HOVER)],
                  foreground=[("active", BG)])
        style.configure("TEntry", fieldbackground=BG_ENTRY, foreground=FG,
                        insertcolor=FG, borderwidth=0)
        style.configure("TCombobox", fieldbackground=BG_ENTRY, foreground=FG,
                        background=BG_ENTRY, borderwidth=0)
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG_ENTRY)],
                  foreground=[("readonly", FG)])
        style.configure("TCheckbutton", background=BG, foreground=FG)
        style.map("TCheckbutton",
                  background=[("active", BG)],
                  foreground=[("active", ACCENT)])
        style.configure("Horizontal.TProgressbar",
                         background=ACCENT, troughcolor=BG_ENTRY,
                         borderwidth=0, thickness=8)

    # ── Header ────────────────────────────────────────────────
    def _build_header(self):
        frame = tk.Frame(self.root, bg=BG_PANEL, height=70)
        frame.pack(fill="x", padx=0, pady=0)
        frame.pack_propagate(False)

        title = tk.Label(frame, text="docscraper", font=("Segoe UI", 18, "bold"),
                         bg=BG_PANEL, fg=ACCENT)
        title.pack(side="left", padx=16, pady=10)

        subtitle = tk.Label(frame, text=f"v{APP_VERSION}", font=("Segoe UI", 10),
                           bg=BG_PANEL, fg=FG_DIM)
        subtitle.pack(side="left", padx=0, pady=10)

        desc = tk.Label(frame, text=APP_DESC, font=("Segoe UI", 8),
                        bg=BG_PANEL, fg=FG_DIM, justify="left", anchor="w")
        desc.pack(side="left", padx=16, pady=10)

    # ── Painel de Input ───────────────────────────────────────
    def _build_input_panel(self):
        frame = tk.Frame(self.root, bg=BG, padx=16, pady=8)
        frame.pack(fill="x")

        # URL
        tk.Label(frame, text="URL do site de documentação:", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 2))

        url_frame = tk.Frame(frame, bg=BG)
        url_frame.pack(fill="x")

        self.url_var = tk.StringVar()
        url_entry = tk.Entry(url_frame, textvariable=self.url_var,
                             bg=BG_ENTRY, fg=FG, insertbackground=FG,
                             relief="flat", font=("Segoe UI", 11))
        url_entry.pack(side="left", fill="x", expand=True, ipady=4)

        # Dica
        tk.Label(frame, text="Ex: https://exemplo.com/docs/", bg=BG, fg=FG_DIM,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 8))

        # Output dir
        tk.Label(frame, text="Pasta de output:", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 2))

        out_frame = tk.Frame(frame, bg=BG)
        out_frame.pack(fill="x")

        self.out_var = tk.StringVar()
        out_entry = tk.Entry(out_frame, textvariable=self.out_var,
                             bg=BG_ENTRY, fg=FG, insertbackground=FG,
                             relief="flat", font=("Segoe UI", 11))
        out_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        browse_btn = tk.Button(out_frame, text="Procurar…", command=self._browse_output,
                               bg=BG_ENTRY, fg=FG, relief="flat", font=("Segoe UI", 10),
                               padx=12, pady=4, activebackground=ACCENT_HOVER,
                               activeforeground=BG)
        browse_btn.pack(side="right")

        # Default output
        default_out = os.path.join(os.path.expanduser("~"), "docscraper_output")
        self.out_var.set(default_out)

    # ── Painel de Opções ──────────────────────────────────────
    def _build_options_panel(self):
        frame = tk.Frame(self.root, bg=BG, padx=16, pady=4)
        frame.pack(fill="x")

        # Camada
        tk.Label(frame, text="Camada de extração:", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 2))

        self.layer_var = tk.StringVar(value="auto")
        layer_combo = ttk.Combobox(frame, textvariable=self.layer_var,
                                   values=[f"{k} — {v}" for k, v in LAYERS],
                                   state="readonly", width=50)
        layer_combo.pack(anchor="w")
        layer_combo.current(0)

        # Opções
        opts_frame = tk.Frame(frame, bg=BG)
        opts_frame.pack(fill="x", pady=(8, 4))

        self.verbose_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opts_frame, text="Verbose (log detalhado)",
                      variable=self.verbose_var, bg=BG, fg=FG,
                      selectcolor=BG_ENTRY, activebackground=BG,
                      activeforeground=ACCENT, font=("Segoe UI", 9)).pack(side="left", padx=(0, 16))

        self.keep_html_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opts_frame, text="Manter HTML original",
                      variable=self.keep_html_var, bg=BG, fg=FG,
                      selectcolor=BG_ENTRY, activebackground=BG,
                      activeforeground=ACCENT, font=("Segoe UI", 9)).pack(side="left", padx=(0, 16))

        # Max depth
        depth_frame = tk.Frame(frame, bg=BG)
        depth_frame.pack(side="left")
        tk.Label(depth_frame, text="Profundidade:", bg=BG, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side="left")
        self.depth_var = tk.StringVar(value="3")
        depth_spin = tk.Spinbox(depth_frame, from_=1, to=10, width=3,
                                textvariable=self.depth_var, bg=BG_ENTRY, fg=FG,
                                relief="flat", font=("Segoe UI", 9), justify="center")
        depth_spin.pack(side="left", padx=4)

        # Output mode
        mode_frame = tk.Frame(frame, bg=BG)
        mode_frame.pack(fill="x", pady=(8, 4))
        tk.Label(mode_frame, text="Modo de output:", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 2))

        self.output_mode_var = tk.StringVar(value="files")
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.output_mode_var,
                                   values=["files — Ficheiros individuais (.md/.html)",
                                           "site — Site HTML unificado (navegável)"],
                                   state="readonly", width=50)
        mode_combo.pack(anchor="w")
        mode_combo.current(0)

    # ── Botões de Ação ────────────────────────────────────────
    def _build_action_buttons(self):
        frame = tk.Frame(self.root, bg=BG, padx=16)
        frame.pack(fill="x", pady=(8, 4))

        self.run_btn = tk.Button(frame, text="▶  Extrair", command=self._start,
                                 bg=ACCENT, fg=BG, relief="flat",
                                 font=("Segoe UI", 11, "bold"), padx=24, pady=8,
                                 activebackground=ACCENT_HOVER, activeforeground=BG)
        self.run_btn.pack(side="left")

        self.stop_btn = tk.Button(frame, text="■  Parar", command=self._stop,
                                  bg=ERROR, fg=BG, relief="flat",
                                  font=("Segoe UI", 11, "bold"), padx=24, pady=8,
                                  activebackground="#e06c75", activeforeground=BG,
                                  state="disabled")
        self.stop_btn.pack(side="left", padx=8)

        self.clear_btn = tk.Button(frame, text="Limpar log", command=self._clear_log,
                                   bg=BG_ENTRY, fg=FG, relief="flat",
                                   font=("Segoe UI", 10), padx=12, pady=8,
                                   activebackground=ACCENT_HOVER, activeforeground=BG)
        self.clear_btn.pack(side="right")

    # ── Painel de Log ─────────────────────────────────────────
    def _build_log_panel(self):
        self._build_action_buttons()

        frame = tk.Frame(self.root, bg=BG, padx=16, pady=4)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Log de execução:", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 2))

        # Text widget com scrollbar
        log_frame = tk.Frame(frame, bg=BG_PANEL)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, bg=BG_PANEL, fg=FG_DIM,
                                insertbackground=FG, relief="flat",
                                font=("Consolas", 10), wrap="word",
                                state="disabled", height=12)
        self.log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview,
                                 bg=BG_ENTRY, troughcolor=BG_PANEL,
                                 relief="flat", width=10)
        scrollbar.pack(side="right", fill="y", pady=4)
        self.log_text.config(yscrollcommand=scrollbar.set)

        # Tags de cor para o log
        self.log_text.tag_config("success", foreground=SUCCESS)
        self.log_text.tag_config("error", foreground=ERROR)
        self.log_text.tag_config("warning", foreground=WARNING)
        self.log_text.tag_config("info", foreground=ACCENT)
        self.log_text.tag_config("dim", foreground=FG_DIM)

    # ── Barra de Status ───────────────────────────────────────
    def _build_status_bar(self):
        frame = tk.Frame(self.root, bg=BG_PANEL, height=32)
        frame.pack(fill="x", side="bottom")
        frame.pack_propagate(False)

        self.status_var = tk.StringVar(value="Pronto.")
        status_label = tk.Label(frame, textvariable=self.status_var,
                                bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI", 9),
                                anchor="w")
        status_label.pack(side="left", padx=12, pady=4)

        self.progress = ttk.Progressbar(frame, mode="determinate",
                                         length=200, maximum=100)
        self.progress.pack(side="right", padx=12, pady=8)
        self.progress.stop()

    # ── Ações ─────────────────────────────────────────────────
    def _browse_output(self):
        d = filedialog.askdirectory(title="Escolher pasta de output")
        if d:
            self.out_var.set(d)

    def _log(self, msg, tag="dim"):
        """Escreve no log com cor."""
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _set_running(self, running):
        self.is_running = running
        if running:
            self.run_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.progress["value"] = 0
            self.status_var.set("A extrair…")
        else:
            self.run_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            if self.progress["value"] > 0 and self.progress["value"] < 100:
                self.progress["value"] = 100
            if self.status_var.get().startswith("A extrair"):
                self.status_var.set("Pronto.")

    def _start(self):
        url = self.url_var.get().strip()
        out = self.out_var.get().strip()

        if not url:
            messagebox.showwarning("URL em falta", "Indica o URL do site de documentação.")
            return
        if not out:
            messagebox.showwarning("Pasta em falta", "Indica a pasta de output.")
            return

        # Garantir que pasta de output existe
        os.makedirs(out, exist_ok=True)

        # Limpar log
        self._clear_log()
        self._log(f"Iniciando extração de: {url}", "info")
        self._log(f"Output: {out}", "dim")
        self._log(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "dim")
        self._log("", "dim")

        # Parse layer
        layer_val = self.layer_var.get().split(" —")[0].strip()
        if layer_val == "auto":
            layer_val = None

        # Parse output mode
        output_mode = self.output_mode_var.get().split(" —")[0].strip()

        self._set_running(True)

        # Lançar thread
        t = threading.Thread(target=self._run_extraction,
                             args=(url, out, layer_val, output_mode), daemon=True)
        t.start()

    def _stop(self):
        if self.process:
            self._log("A parar…", "warning")
            self.process.terminate()
            self.status_var.set("Parado pelo utilizador.")
        self._set_running(False)

    def _run_extraction(self, url, out, layer, output_mode="files"):
        """Executa docscraper.py como subprocesso e captura output."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "docscraper.py")

        # Procurar venv em vários locais (pasta do projeto pode não suportar symlinks)
        venv_candidates = [
            os.path.join(script_dir, ".venv", "bin", "python"),
            os.path.join(os.path.expanduser("~"), "docscraper-venv", "bin", "python"),
            os.path.join(os.path.expanduser("~"), ".hermes", "scripts", "docscraper", ".venv", "bin", "python"),
        ]
        venv_python = sys.executable
        for candidate in venv_candidates:
            if os.path.exists(candidate):
                venv_python = candidate
                break

        cmd = [venv_python, script_path, url, "-o", out, "-v"]

        if layer:
            cmd.extend(["--layer", layer])
        cmd.extend(["--max-depth", str(self.depth_var.get())])
        if self.keep_html_var.get():
            cmd.append("--keep-html")
        if output_mode and output_mode != "files":
            cmd.extend(["--output-mode", output_mode])

        self._log(f"Comando: {' '.join(cmd)}", "dim")
        self._log("", "dim")

        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, universal_newlines=True
            )

            for line in self.process.stdout:
                line = line.rstrip()
                if not line:
                    continue

                # Colorir por conteúdo
                tag = "dim"
                if "✓" in line or "SUCCESS" in line:
                    tag = "success"
                elif "✗" in line or "ERROR" in line or "Failed" in line:
                    tag = "error"
                elif "WARNING" in line or "SPA" in line:
                    tag = "warning"
                elif line.startswith("[") or "Camada" in line:
                    tag = "info"

                self.log_queue.put((line, tag))

            self.process.wait()
            rc = self.process.returncode

            if rc == 0:
                self.log_queue.put(("", "dim"))
                self.log_queue.put("✓ Extração concluída com sucesso!", "success")
            else:
                self.log_queue.put(("", "dim"))
                self.log_queue.put(f"✗ Processo terminou com código {rc}", "error")

        except Exception as e:
            self.log_queue.put(("", "dim"))
            self.log_queue.put(f"✗ Erro: {e}", "error")

        finally:
            self.log_queue.put(("__DONE__", "dim"))

    def _poll_log(self):
        """Processa mensagens da queue de log."""
        import re
        while not self.log_queue.empty():
            msg, tag = self.log_queue.get()
            if msg == "__DONE__":
                self._set_running(False)
                self.status_var.set("Concluído.")
                continue

            # Detectar progresso [N/total] e actualizar barra
            match = re.search(r'\[(\d+)/(\d+)\]', msg)
            if match:
                current = int(match.group(1))
                total = int(match.group(2))
                if total > 0:
                    pct = int((current / total) * 100)
                    self.progress["value"] = pct
                    self.status_var.set(f"A extrair… {current}/{total} ({pct}%)")

            self._log(msg, tag)
        self.root.after(100, self._poll_log)


def main():
    root = tk.Tk()
    app = DocScraperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()