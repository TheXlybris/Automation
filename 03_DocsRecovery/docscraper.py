#!/usr/bin/env python3
"""docscraper — Ferramenta universal de extração de documentação de sites.

Pipeline de 5 camadas em cascata:
  0. llms.txt / llms-full  (atalho, um único download)
  1. sitemap.xml           (lista de URLs)
  2. link discovery        (crawling recursivo de links)
  3. GitHub source         (clonar repo com fonte markdown)
  4. wget mirror           (HTML estático)
  5. Playwright            (SPAs renderizados por JS)

Uso:
  python3 docscraper.py <url> [opções]
"""

import argparse
import os
import sys
import time
from datetime import datetime

# Adicionar diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractors.llms_txt import fetch_all_llms
from extractors.sitemap import fetch_sitemap
from extractors.link_discovery import discover_links
from extractors.github_source import fetch_github_source
from extractors.wget_mirror import wget_mirror, convert_mirror_to_md
from extractors.playwright_crawl import playwright_crawl
from utils.url_utils import normalize_base_url, url_to_filename
from utils.site_generator import generate_site


def write_index(output_dir: str, files: list, base_url: str, layer: str):
    """Escreve index.md com links para todas as páginas extraídas."""
    index_path = os.path.join(output_dir, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(f"# Documentation Index\n\n")
        f.write(f"Source: {base_url}\n")
        f.write(f"Extracted: {datetime.now().isoformat()}\n")
        f.write(f"Layer used: {layer}\n")
        f.write(f"Total pages: {len(files)}\n\n---\n\n")
        for file_path in sorted(files):
            rel = os.path.relpath(file_path, output_dir)
            name = os.path.basename(file_path).replace(".md", "")
            f.write(f"- [{name}]({rel})\n")


def run_cascade(base_url: str, output_dir: str, max_depth: int = 3,
                force_layer: str = None, list_urls: bool = False,
                keep_html: bool = False, verbose: bool = False,
                output_mode: str = "files"):
    """Executa o pipeline de camadas em cascata."""

    start_time = time.time()
    base_url = normalize_base_url(base_url)
    os.makedirs(output_dir, exist_ok=True)

    if verbose:
        print(f"Target: {base_url}")
        print(f"Output: {output_dir}")
        print()

    # ============================================================
    # CAMADA 0a: llms.txt / llms-full
    # ============================================================
    if force_layer in (None, "llms_txt"):
        if verbose:
            print("[Camada 0a] Trying llms.txt / llms-full...")

        result = fetch_all_llms(base_url)

        if result["success"]:
            if verbose:
                print(f"  SUCCESS! {result['type']} — {len(result['content'])} chars")

            if list_urls:
                print(f"llms.txt found at: {result['url']}")
                print(f"Content size: {len(result['content'])} chars")
                return

            # Salvar conteúdo
            out_file = os.path.join(output_dir, "llms-full.md")
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(result["content"])

            write_index(output_dir, [out_file], base_url, result["type"])

            elapsed = time.time() - start_time
            print(f"\n✓ Done in {elapsed:.1f}s")
            print(f"  Layer: {result['type']}")
            print(f"  File: {out_file}")
            print(f"  Size: {len(result['content'])} chars")
            return
        elif verbose:
            print(f"  Failed: {result.get('error', 'unknown')}")

    # ============================================================
    # CAMADA 0b: sitemap.xml
    # ============================================================
    urls = []
    if force_layer in (None, "sitemap"):
        if verbose:
            print("[Camada 0b] Trying sitemap.xml...")

        result = fetch_sitemap(base_url)

        if result["success"] and len(result["urls"]) > 1:
            # Filtrar: só URLs que são subpaths do base_url
            from utils.url_utils import is_subpath
            filtered = [u for u in result["urls"] if is_subpath(u, base_url)]
            if len(filtered) > 1:
                urls = filtered
                if verbose:
                    print(f"  SUCCESS! {len(urls)} URLs found in sitemap (filtered to base path)")
            else:
                if verbose:
                    print(f"  Sitemap has {len(result['urls'])} URLs but only {len(filtered)} match base path")
                    print(f"  Will try link discovery instead")
        elif verbose:
            err = result.get('error', f'{len(result.get("urls", []))} URLs')
            print(f"  Failed or too few URLs: {err}")

    # ============================================================
    # CAMADA 1: Link Discovery (se sitemap não teve todas as URLs)
    # ============================================================
    if not urls and force_layer in (None, "link_discovery", "links"):
        if verbose:
            print("[Camada 1] Discovering links via HTML crawling...")

        result = discover_links(base_url, max_depth=max_depth, verbose=verbose)

        if result["success"]:
            urls = result["urls"]
            if verbose:
                print(f"  SUCCESS! {len(urls)} URLs discovered")
        elif verbose:
            print(f"  Failed: {result.get('error', 'unknown')}")

    if list_urls and urls:
        print(f"URLs found ({len(urls)}):")
        for u in urls:
            print(f"  {u}")
        return

    # ============================================================
    # Se já temos URLs (sitemap ou link discovery), baixar via requests
    # e converter para markdown. Verificar se é SPA primeiro.
    # ============================================================
    if urls and not force_layer == "playwright":
        if verbose:
            print(f"[Download] Fetching {len(urls)} pages via requests...")

        from utils.html_to_md import html_to_markdown
        import requests as req_mod

        md_files = []
        spa_detected = False
        total_text = 0

        for i, url in enumerate(urls, 1):
            try:
                resp = req_mod.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; docscraper/1.0)"
                }, timeout=15)
                if resp.status_code == 200:
                    html = resp.text

                    # Guardar HTML original se pedido
                    if keep_html:
                        html_dir = os.path.join(output_dir, "html")
                        os.makedirs(html_dir, exist_ok=True)
                        html_name = url_to_filename(url, base_url).replace(".md", ".html")
                        html_path = os.path.join(output_dir, "html", html_name)
                        with open(html_path, "w", encoding="utf-8") as fhtml:
                            fhtml.write(html)

                    # Medir texto real
                    from bs4 import BeautifulSoup as bs
                    soup = bs(html, "lxml")
                    for tag in soup.find_all(["script", "style", "noscript"]):
                        tag.decompose()
                    text = soup.get_text(strip=True)
                    total_text += len(text)

                    md_content = html_to_markdown(html, source_url=url, layer="requests")
                    name = url_to_filename(url, base_url)
                    out_path = os.path.join(output_dir, "markdown", name)
                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(md_content)
                    md_files.append(out_path)
                    if verbose:
                        print(f"  [{i}/{len(urls)}] ✓ {url} ({len(text)} chars text)")
                time.sleep(0.5)
            except Exception as e:
                if verbose:
                    print(f"  [{i}/{len(urls)}] ✗ {url}: {e}")

        # Heurística SPA: se média de texto < 200 chars, tentar Playwright
        if md_files and total_text / len(md_files) < 200:
            if verbose:
                print(f"  SPA detected (avg {total_text // len(md_files)} chars/page). Trying Playwright...")
            spa_detected = True

        if md_files and not spa_detected:
            write_index(output_dir, md_files, base_url, "requests")
            elapsed = time.time() - start_time
            print(f"\n✓ Done in {elapsed:.1f}s")
            print(f"  Layer: requests (sitemap/link discovery)")
            print(f"  Pages: {len(md_files)}")
            return

        # Se SPA detectado, cair para Playwright com as URLs que já temos
        if spa_detected and force_layer is None:
            if verbose:
                print(f"  Falling through to Playwright with {len(urls)} URLs...")
            force_layer = None  # continuar para Playwright

    # ============================================================
    # CAMADA 2: GitHub Source (só se não temos URLs)
    # ============================================================
    if not urls and force_layer in (None, "github"):
        if verbose:
            print("[Camada 2] Trying GitHub source...")

        result = fetch_github_source(base_url, output_dir, verbose=verbose)

        if result["success"]:
            write_index(output_dir, result["files"], base_url, "github")
            elapsed = time.time() - start_time
            print(f"\n✓ Done in {elapsed:.1f}s")
            print(f"  Layer: GitHub source")
            print(f"  Files: {len(result['files'])}")
            return
        elif verbose:
            print(f"  Failed: {result.get('error', 'unknown')}")

    # ============================================================
    # CAMADA 3: wget mirror (só se não temos URLs)
    # ============================================================
    if not urls and force_layer in (None, "wget"):
        if verbose:
            print("[Camada 3] Trying wget mirror...")

        result = wget_mirror(base_url, output_dir, verbose=verbose)

        if result["success"]:
            if result["is_spa"]:
                if verbose:
                    print(f"  wget succeeded but content looks like SPA ({result['page_count']} pages, avg text too low)")
                    print(f"  Falling through to Playwright...")
            else:
                if verbose:
                    print(f"  SUCCESS! {result['page_count']} pages, {result['total_text']} chars of text")

                # Converter para markdown
                md_result = convert_mirror_to_md(
                    result["mirror_dir"], output_dir, base_url, verbose
                )

                write_index(output_dir, md_result["files"], base_url, "wget")
                elapsed = time.time() - start_time
                print(f"\n✓ Done in {elapsed:.1f}s")
                print(f"  Layer: wget mirror")
                print(f"  Pages: {result['page_count']}")
                print(f"  Markdown files: {md_result['count']}")
                return
        elif verbose:
            print(f"  Failed: {result.get('error', 'unknown')}")

    # ============================================================
    # CAMADA 4: Playwright (para SPAs ou quando tudo falha)
    # ============================================================
    if force_layer in (None, "playwright") or (not urls and force_layer is None):
        if verbose:
            print("[Camada 4] Trying Playwright headless...")

        # Se ainda não temos URLs, descobrir com link discovery
        if not urls:
            if verbose:
                print("  Discovering links first...")
            result = discover_links(base_url, max_depth=max_depth, verbose=verbose)
            if result["success"]:
                urls = result["urls"]
            else:
                # Último recurso: usar só a URL base
                urls = [base_url]

        if verbose:
            print(f"  Rendering {len(urls)} pages with Chromium...")

        result = playwright_crawl(urls, output_dir, verbose=verbose, keep_html=keep_html)

        if result["success"]:
            # Se modo site, gerar HTML unificado
            if output_mode == "site" and result.get("pages"):
                if verbose:
                    print(f"  Generating unified site HTML ({len(result['pages'])} pages)...")
                
                site_title = base_url.split("//")[1].split("/")[0] if "//" in base_url else "Documentation"
                site_path = os.path.join(output_dir, "site.html")
                generate_site(
                    pages=result["pages"],
                    base_url=base_url,
                    output_path=site_path,
                    title=site_title
                )
                
                # Também guardar markdown individual
                write_index(output_dir, result["files"], base_url, "playwright")
                elapsed = time.time() - start_time
                print(f"\n✓ Done in {elapsed:.1f}s")
                print(f"  Layer: Playwright")
                print(f"  Pages rendered: {result['count']}")
                print(f"  Site HTML: {site_path}")
                if result.get("errors"):
                    print(f"  Errors: {len(result['errors'])}")
                return
            
            write_index(output_dir, result["files"], base_url, "playwright")
            elapsed = time.time() - start_time
            print(f"\n✓ Done in {elapsed:.1f}s")
            print(f"  Layer: Playwright")
            print(f"  Pages rendered: {result['count']}")
            if result.get("errors"):
                print(f"  Errors: {len(result['errors'])}")
            return
        else:
            print(f"\n✗ All layers failed.")
            print(f"  Last error: {result.get('error', 'unknown')}")
            return


def main():
    parser = argparse.ArgumentParser(
        description="docscraper — Universal documentation extractor"
    )
    parser.add_argument("url", help="Base URL of the documentation site")
    parser.add_argument("-o", "--output", default="./output",
                        help="Output directory (default: ./output)")
    parser.add_argument("--layer", choices=["llms_txt", "sitemap", "link_discovery",
                                              "github", "wget", "playwright"],
                        help="Force a specific layer")
    parser.add_argument("--list-urls", action="store_true",
                        help="List discovered URLs without downloading")
    parser.add_argument("--max-depth", type=int, default=3,
                        help="Max crawl depth for link discovery (default: 3)")
    parser.add_argument("--keep-html", action="store_true",
                        help="Keep original HTML files alongside markdown")
    parser.add_argument("--output-mode", choices=["files", "site"], default="files",
                        help="Output mode: 'files' = individual markdown/html files, 'site' = single navigable HTML page")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()

    run_cascade(
        base_url=args.url,
        output_dir=args.output,
        max_depth=args.max_depth,
        force_layer=args.layer,
        list_urls=args.list_urls,
        keep_html=args.keep_html,
        verbose=args.verbose,
        output_mode=args.output_mode,
    )


if __name__ == "__main__":
    main()