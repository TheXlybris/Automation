"""Camada 4: Playwright — renderiza SPAs com Chromium headless.

Para sites onde o HTML servido pelo servidor está vazio (SPA),
abre um Chromium real, espera o JavaScript renderizar, e extrai
o HTML final. Depois converte para markdown ou guarda HTML.

Otimizado com processamento paralelo (múltiplas tabs) e delays
reduzidos para melhor performance.
"""

import os
import sys
import time
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.url_utils import url_to_filename


def playwright_crawl(urls: List[str], output_dir: str, delay: float = 0.5,
                     verbose: bool = False, keep_html: bool = False,
                     parallel: int = 4) -> dict:
    """
    Visita cada URL com Playwright (Chromium headless), espera
    o JS renderizar, extrai HTML e converte para markdown.
    
    Usa múltiplas tabs em paralelo para melhor performance.

    Retorna dict com:
      - success: bool
      - files: List[str] com paths para ficheiros markdown
      - pages: List[dict] com url, title, html_content (para site generator)
      - errors: List[str] com URLs que falharam
      - error: str se falha total
    """
    from playwright.sync_api import sync_playwright

    md_dir = os.path.join(output_dir, "markdown")
    os.makedirs(md_dir, exist_ok=True)

    md_files: List[str] = []
    errors: List[str] = []
    pages_data: List[dict] = []  # Para site generator

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (compatible; docscraper/1.0)"
            )

            total = len(urls)
            completed = 0

            # Processar em batches de tamanho 'parallel'
            for batch_start in range(0, total, parallel):
                batch = urls[batch_start:batch_start + parallel]
                batch_pages = []

                for url in batch:
                    page = context.new_page()
                    batch_pages.append((url, page))

                for url, page in batch_pages:
                    try:
                        if verbose:
                            print(f"  [{completed + 1}/{total}] [playwright] {url}")

                        page.goto(url, wait_until="networkidle", timeout=30000)

                        # Espera reduzida (500ms em vez de 2s)
                        page.wait_for_timeout(500)

                        # Extrair HTML renderizado
                        html_content = page.content()

                        # Extrair título
                        title = ""
                        try:
                            title = page.title()
                        except Exception:
                            pass

                        # Guardar HTML original se pedido
                        if keep_html:
                            html_dir = os.path.join(output_dir, "html")
                            os.makedirs(html_dir, exist_ok=True)
                            html_name = url_to_filename(url).replace(".md", ".html")
                            html_path = os.path.join(html_dir, html_name)
                            with open(html_path, "w", encoding="utf-8") as fh:
                                fh.write(html_content)

                        # Guardar para site generator
                        pages_data.append({
                            "url": url,
                            "title": title,
                            "html_content": html_content,
                        })

                        # Converter para markdown
                        from utils.html_to_md import html_to_markdown
                        md_content = html_to_markdown(html_content, source_url=url, layer="playwright")

                        # Nome do ficheiro
                        name = url_to_filename(url)
                        out_path = os.path.join(md_dir, name)

                        with open(out_path, "w", encoding="utf-8") as fh:
                            fh.write(md_content)

                        md_files.append(out_path)
                        completed += 1

                    except Exception as e:
                        errors.append(f"{url}: {str(e)}")
                        completed += 1
                        if verbose:
                            print(f"  [{completed}/{total}] ERROR: {url}: {e}")

                # Fechar todas as páginas do batch
                for _, page in batch_pages:
                    try:
                        page.close()
                    except Exception:
                        pass

                # Delay reduzido entre batches
                if batch_start + parallel < total:
                    time.sleep(delay)

            context.close()
            browser.close()

    except Exception as e:
        return {"success": False, "error": f"Playwright failed: {e}"}

    if not md_files and not pages_data:
        return {"success": False, "error": "No pages rendered successfully", "errors": errors}

    return {
        "success": True,
        "files": md_files,
        "pages": pages_data,
        "count": len(md_files),
        "errors": errors,
    }