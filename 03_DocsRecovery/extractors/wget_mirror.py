"""Camada 3: wget mirror — espelha o site recursivamente.

Usa wget para baixar todas as páginas do site. Depois converte
os ficheiros HTML para markdown. Se o HTML tiver pouco conteúdo
real (SPA), indica que é precisa a Camada 4 (Playwright).
"""

import subprocess
import os
import time
from typing import List
from bs4 import BeautifulSoup


def wget_mirror(base_url: str, output_dir: str, delay: float = 1.0,
                 verbose: bool = False) -> dict:
    """
    Espelha o site com wget. Retorna info sobre os ficheiros baixados.
    Retorna dict com:
      - success: bool
      - html_files: List[str] com paths para ficheiros HTML
      - total_text: int (total de texto real extraído)
      - is_spa: bool (True se HTML tem pouco conteúdo → precisa Playwright)
      - error: str se falha
    """
    mirror_dir = os.path.join(output_dir, "wget_mirror")
    os.makedirs(mirror_dir, exist_ok=True)

    cmd = [
        "wget",
        "--mirror",              # baixar recursivamente
        "--convert-links",        # converter links para local
        "--adjust-extension",     # adicionar .html se necessário
        "--page-requisites",      # baixar CSS, JS, imagens
        "--no-parent",            # não subir acima do path base
        "--wait", str(delay),     # delay entre requests
        "--random-wait",          # randomizar wait
        "--user-agent=Mozilla/5.0 (compatible; docscraper/1.0)",
        "--no-verbose",           # menos output
        "-P", mirror_dir,         # diretório de output
        base_url,
    ]

    if verbose:
        print(f"  Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )

        # wget pode retornar non-zero mesmo com sucesso parcial
        # Verificar ficheiros baixados
        html_files: List[str] = []
        total_text = 0

        for root, dirs, files in os.walk(mirror_dir):
            for f in files:
                if f.endswith((".html", ".htm")):
                    path = os.path.join(root, f)
                    html_files.append(path)

                    # Medir texto real
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                            html = fh.read()
                        soup = BeautifulSoup(html, "lxml")
                        for tag in soup.find_all(["script", "style", "noscript"]):
                            tag.decompose()
                        text = soup.get_text(strip=True)
                        total_text += len(text)
                    except Exception:
                        pass

        if not html_files:
            return {
                "success": False,
                "error": f"wget returned no HTML files. stderr: {result.stderr[:200]}",
                "mirror_dir": mirror_dir,
            }

        # Heurística SPA: se média de texto por página < 200 chars
        avg_text = total_text / len(html_files)
        is_spa = avg_text < 200

        return {
            "success": True,
            "html_files": html_files,
            "total_text": total_text,
            "is_spa": is_spa,
            "mirror_dir": mirror_dir,
            "page_count": len(html_files),
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "wget timed out (300s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def convert_mirror_to_md(mirror_dir: str, output_dir: str,
                         base_url: str = "", verbose: bool = False) -> dict:
    """
    Converte todos os ficheiros HTML do mirror para markdown.
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from utils.html_to_md import html_to_markdown
    from utils.url_utils import url_to_filename

    md_files: List[str] = []

    for root, dirs, files in os.walk(mirror_dir):
        for f in files:
            if f.endswith((".html", ".htm")):
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        html = fh.read()

                    md_content = html_to_markdown(html, source_url=path, layer="wget")

                    # Nome do ficheiro: path relativo no mirror
                    rel = os.path.relpath(path, mirror_dir)
                    name = rel.replace(os.sep, "_").replace(".html", ".md").replace(".htm", ".md")

                    out_path = os.path.join(output_dir, "markdown", name)
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)

                    with open(out_path, "w", encoding="utf-8") as fh:
                        fh.write(md_content)

                    md_files.append(out_path)

                    if verbose:
                        print(f"  Converted: {rel} -> {name}")

                except Exception as e:
                    if verbose:
                        print(f"  Error converting {path}: {e}")

    return {"success": True, "files": md_files, "count": len(md_files)}