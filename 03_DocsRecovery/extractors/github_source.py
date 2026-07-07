"""Camada 2: GitHub source — detecta repo público e clona a fonte markdown.

Procura no HTML da página por links "Edit on GitHub" ou
links para github.com. Se encontrar, clona o repo (shallow)
e procura a pasta de documentação.
"""

import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import subprocess
import os
import tempfile
from typing import Optional

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; docscraper/1.0)"
}


def detect_github_repo(base_url: str, timeout: int = 15) -> dict:
    """
    Detecta se o site tem repo GitHub público.
    Retorna dict com:
      - success: bool
      - repo_url: str se encontrou
      - error: str se não
    """
    try:
        resp = requests.get(base_url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}"}

        soup = BeautifulSoup(resp.text, "lxml")

        # Procurar links para github.com
        github_urls = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "github.com" in href:
                parsed = urlparse(href)
                if parsed.netloc == "github.com":
                    # Normalizar: extrair owner/repo
                    path_parts = parsed.path.strip("/").split("/")
                    if len(path_parts) >= 2:
                        repo_url = f"https://github.com/{path_parts[0]}/{path_parts[1]}"
                        github_urls.add(repo_url)

        if not github_urls:
            return {"success": False, "error": "No GitHub link found"}

        # Retornar o primeiro repo encontrado
        return {"success": True, "repo_url": github_urls.pop()}

    except requests.RequestException as e:
        return {"success": False, "error": str(e)}


def clone_and_extract(repo_url: str, output_dir: str, verbose: bool = False) -> dict:
    """
    Clona o repo (shallow) e extrai a pasta de documentação.
    Retorna dict com:
      - success: bool
      - docs_path: str se encontrou pasta de docs
      - files: List[str] com ficheiros markdown encontrados
      - error: str se falha
    """
    # Criar diretório temporário para o clone
    tmp_dir = tempfile.mkdtemp(prefix="docscraper_clone_")

    if verbose:
        print(f"  Cloning {repo_url} (shallow)...")

    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, tmp_dir],
            capture_output=True, text=True, timeout=120
        )

        if result.returncode != 0:
            return {"success": False, "error": f"git clone failed: {result.stderr}"}

        # Heurística: procurar pasta de docs
        doc_dirs = ["docs", "documentation", "content", "website/docs",
                    "site/docs", "src/docs", "doc"]

        docs_path = None
        for d in doc_dirs:
            full = os.path.join(tmp_dir, d)
            if os.path.isdir(full):
                docs_path = full
                break

        if not docs_path:
            # Procurar qualquer pasta com ficheiros .md
            for root, dirs, files in os.walk(tmp_dir):
                md_files = [f for f in files if f.endswith(".md")]
                if len(md_files) >= 3:  # pelo menos 3 ficheiros markdown
                    docs_path = root
                    break

        if not docs_path:
            return {"success": False, "error": "No documentation folder found in repo"}

        # Copiar ficheiros markdown para output_dir
        md_files = []
        for root, dirs, files in os.walk(docs_path):
            for f in files:
                if f.endswith(".md"):
                    src = os.path.join(root, f)
                    rel = os.path.relpath(src, docs_path)
                    dst = os.path.join(output_dir, "github_source", rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)

                    # Ler conteúdo
                    with open(src, "r", encoding="utf-8") as fh:
                        content = fh.read()

                    # Escrever no output
                    with open(dst, "w", encoding="utf-8") as fh:
                        fh.write(content)

                    md_files.append(dst)

        return {
            "success": True,
            "docs_path": docs_path,
            "files": md_files,
            "clone_dir": tmp_dir,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "git clone timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_github_source(base_url: str, output_dir: str, verbose: bool = False) -> dict:
    """
    Pipeline completo: detecta repo GitHub, clona e extrai docs.
    """
    detection = detect_github_repo(base_url)
    if not detection["success"]:
        return detection

    if verbose:
        print(f"  GitHub repo detected: {detection['repo_url']}")

    return clone_and_extract(detection["repo_url"], output_dir, verbose)