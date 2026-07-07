"""Camada 1: Link discovery — descoberta recursiva de links internos.

Faz fetch da página base, extrai todos os links internos,
e segue recursivamente até max_depth. Útil quando o sitemap
não lista todas as subpáginas (comum em SPAs).
"""

import requests
from urllib.parse import urlparse, urljoin, urldefrag
from bs4 import BeautifulSoup
from typing import List, Set
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; docscraper/1.0)"
}


def discover_links(base_url: str, max_depth: int = 3, delay: float = 0.5,
                   verbose: bool = False) -> dict:
    """
    Descobre links internos recursivamente a partir de base_url.
    Retorna dict com:
      - success: bool
      - urls: List[str] se success
      - error: str se falha
    """
    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc
    base_path = base_parsed.path.rstrip("/")

    discovered: Set[str] = set()
    to_visit: List[tuple] = [(base_url, 0)]  # (url, depth)
    visited: Set[str] = set()

    while to_visit:
        url, depth = to_visit.pop(0)

        # Normalizar: remover fragmento
        url = urldefrag(url)[0]

        if url in visited:
            continue
        visited.add(url)

        if depth > max_depth:
            continue

        if verbose:
            print(f"  [depth {depth}] {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                continue

            discovered.add(resp.url)  # usar URL final após redirects

            if depth == max_depth:
                continue

            # Extrair links da página
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                # Ignorar anchors, mailto, javascript
                if href.startswith(("#", "mailto:", "javascript:", "tel:")):
                    continue
                # Resolver URL relativo
                full_url = urljoin(resp.url, href)
                # Remover fragmento
                full_url = urldefrag(full_url)[0]
                # Filtrar: mesmo domínio e subpath
                parsed = urlparse(full_url)
                if parsed.netloc != base_domain:
                    continue
                if base_path and not parsed.path.startswith(base_path):
                    continue
                # Adicionar à fila se não visitado
                if full_url not in visited and full_url not in discovered:
                    to_visit.append((full_url, depth + 1))

            time.sleep(delay)

        except requests.RequestException:
            continue

    # Ordenar URLs
    urls = sorted(discovered)

    if not urls:
        return {"success": False, "error": "No internal links found", "urls": []}

    return {"success": True, "urls": urls}