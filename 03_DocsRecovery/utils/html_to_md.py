"""HTML to markdown converter — limpa boilerplate e converte."""

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md
from datetime import datetime
import os


def html_to_markdown(html: str, source_url: str = "", layer: str = "") -> str:
    """
    Converte HTML para markdown limpo.
    Remove nav, header, footer, scripts, estilos.
    Adiciona metadados no topo.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remover tags irrelevantes
    for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Remover elementos comuns de navegação/footer
    for selector in ["[role=navigation]", "[role=banner]", "[role=contentinfo]",
                     ".sidebar", ".navbar", ".breadcrumbs", ".pagination",
                     ".table-of-contents", ".toc", ".edit-this-page",
                     ".theme-toggle", ".search-box", ".md-search"]:
        for el in soup.select(selector):
            el.decompose()

    # Tentar extrair título
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Procurar conteúdo principal
    content = None
    for selector in ["main", "article", "[role=main]", ".content", ".markdown-body",
                     ".documentation", ".doc-content", "#content", ".main-content"]:
        content = soup.select_one(selector)
        if content:
            break

    # Se não encontrou container específico, usar o body limpo
    if not content:
        content = soup.body or soup

    # Converter para markdown
    markdown_text = md(str(content), heading_style="ATX", strip=["img"])

    # Limpar linhas vazias excessivas
    lines = [line.rstrip() for line in markdown_text.split("\n")]
    cleaned = []
    empty_count = 0
    for line in lines:
        if line == "":
            empty_count += 1
            if empty_count <= 2:
                cleaned.append(line)
        else:
            empty_count = 0
            cleaned.append(line)

    markdown_text = "\n".join(cleaned).strip()

    # Adicionar metadados
    meta = f"""---
url: {source_url}
extracted: {datetime.now().isoformat()}
layer: {layer}
title: {title}
---

# {title or source_url}

"""

    return meta + markdown_text