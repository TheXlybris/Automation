"""Camada 0b: sitemap.xml — extrai todas as URLs do sitemap."""

import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import List


def fetch_sitemap(base_url: str, timeout: int = 15) -> dict:
    """
    Tenta obter e parsear sitemap.xml do site.
    Retorna dict com:
      - success: bool
      - urls: List[str] se success
      - error: str se falha
    """
    parsed = urlparse(base_url)
    base_path = parsed.path.rstrip("/")

    # Tentar vários locais possíveis para sitemap
    sitemap_urls = [
        f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
        f"{parsed.scheme}://{parsed.netloc}{base_path}/sitemap.xml" if base_path else None,
    ]
    sitemap_urls = [u for u in sitemap_urls if u]

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; docscraper/1.0)"
    }

    for sitemap_url in sitemap_urls:
        try:
            resp = requests.get(sitemap_url, headers=headers, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200 and resp.text.strip():
                urls = parse_sitemap_xml(resp.text, base_url)
                if urls:
                    return {
                        "success": True,
                        "urls": urls,
                        "source": resp.url,
                    }
        except requests.RequestException:
            continue

    return {
        "success": False,
        "error": "No sitemap.xml found",
        "urls": [],
    }


def parse_sitemap_xml(xml_text: str, base_url: str = "") -> List[str]:
    """
    Parse sitemap.xml. Suporta sitemap index (referencia outros sitemaps)
    e sitemap normal (lista de URLs).
    """
    soup = BeautifulSoup(xml_text, "xml")
    urls: List[str] = []

    # Verificar se é sitemap index (tem <sitemap> tags)
    sitemaps = soup.find_all("sitemap")
    if sitemaps:
        # É um sitemap index — seguir cada sub-sitemap
        headers = {"User-Agent": "Mozilla/5.0 (compatible; docscraper/1.0)"}
        for sm in sitemaps:
            loc = sm.find("loc")
            if loc and loc.text:
                try:
                    resp = requests.get(loc.text.strip(), headers=headers, timeout=30)
                    if resp.status_code == 200:
                        sub_urls = parse_sitemap_xml(resp.text, base_url)
                        urls.extend(sub_urls)
                except requests.RequestException:
                    continue
        return urls

    # Sitemap normal — extrair <loc> de cada <url>
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        if loc and loc.text:
            urls.append(loc.text.strip())

    # Filtrar para URLs sob o base_url se especificado
    if base_url:
        base_parsed = urlparse(base_url)
        base_path = base_parsed.path.rstrip("/")
        filtered = []
        for u in urls:
            u_parsed = urlparse(u)
            if u_parsed.netloc == base_parsed.netloc:
                if not base_path or u_parsed.path.startswith(base_path):
                    filtered.append(u)
        urls = filtered if filtered else urls

    # Deduplicar mantendo ordem
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    return unique