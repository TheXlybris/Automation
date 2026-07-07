"""Camada 0a: llms.txt + llms-full detection.

Tenta obter /llms.txt do site. Também procura no HTML da página
inicial por links para ficheiros llms*.txt (padrão usado por
sites de docs modernos como Nuxt Content).
"""

import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from typing import Optional


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; docscraper/1.0)"
}


def fetch_llms_txt(base_url: str, timeout: int = 15) -> dict:
    """
    Tenta obter /llms.txt do site.
    Retorna dict com:
      - success: bool
      - content: str (markdown cru) se success
      - url: str (URL usada)
      - error: str se falha
    """
    parsed = urlparse(base_url)
    llms_url = f"{parsed.scheme}://{parsed.netloc}/llms.txt"

    try:
        resp = requests.get(llms_url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200 and resp.text.strip():
            text = resp.text.strip()
            if len(text) > 50 and not text.startswith("<"):
                return {
                    "success": True,
                    "content": text,
                    "url": resp.url,
                    "type": "llms.txt",
                }
        return {
            "success": False,
            "error": f"HTTP {resp.status_code}" if resp.status_code != 200 else "Content too short or HTML",
            "url": llms_url,
        }
    except requests.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "url": llms_url,
        }


def fetch_llms_full(base_url: str, timeout: int = 30) -> dict:
    """
    Procura no HTML da página base por links para ficheiros llms*.txt.
    Baixa o maior ficheiro encontrado (provavelmente o llms-full).
    Retorna mesmo formato que fetch_llms_txt.
    """
    try:
        resp = requests.get(base_url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}"}

        soup = BeautifulSoup(resp.text, "lxml")

        # Procurar links para ficheiros llms*.txt
        llms_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if "llms" in href and href.endswith(".txt"):
                full_url = urljoin(base_url, a["href"])
                llms_links.append(full_url)

        if not llms_links:
            return {"success": False, "error": "No llms*.txt links found in HTML"}

        # Baixar cada ficheiro e ficar com o maior
        best = None
        for link in llms_links:
            try:
                r = requests.get(link, headers=HEADERS, timeout=60, allow_redirects=True)
                if r.status_code == 200 and r.text.strip():
                    size = len(r.text)
                    if best is None or size > best["size"]:
                        best = {
                            "success": True,
                            "content": r.text,
                            "url": r.url,
                            "size": size,
                            "type": "llms-full",
                        }
            except requests.RequestException:
                continue

        if best:
            best.pop("size", None)
            return best

        return {"success": False, "error": "All llms*.txt downloads failed"}

    except requests.RequestException as e:
        return {"success": False, "error": str(e)}


def fetch_all_llms(base_url: str, timeout: int = 15) -> dict:
    """
    Tenta llms.txt primeiro, depois llms-full.
    Retorna o que funcionar (preferindo llms-full se for maior).
    """
    # Tentar llms.txt primeiro
    result_txt = fetch_llms_txt(base_url, timeout)

    # Tentar llms-full (procurar no HTML)
    result_full = fetch_llms_full(base_url, timeout)

    # Se ambos funcionaram, ficar com o maior
    if result_txt["success"] and result_full["success"]:
        if len(result_full["content"]) > len(result_txt["content"]):
            return result_full
        return result_txt

    # Se só um funcionou, retornar esse
    if result_txt["success"]:
        return result_txt
    if result_full["success"]:
        return result_full

    # Nenhum funcionou
    return {
        "success": False,
        "error": f"llms.txt: {result_txt.get('error', 'fail')} | llms-full: {result_full.get('error', 'fail')}",
    }