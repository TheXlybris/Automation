"""Gerador de site HTML unificado — converte páginas extraídas num único
ficheiro HTML navegável, com sidebar à esquerda e conteúdo à direita.

Replica a experiência de um site de documentação real:
- Sidebar com árvore de navegação (baseada na estrutura de URLs)
- Área de conteúdo que muda ao clicar nos links da sidebar
- JavaScript para navegação sem reload (single-page app)
- CSS escuro e legível, inspirado em sites de docs modernos
"""

import os
import html
from datetime import datetime
from urllib.parse import urlparse, unquote


def _url_to_title(url: str, base_url: str = "") -> str:
    """Converte URL num título legível para a sidebar."""
    path = urlparse(url).path
    if base_url:
        base_path = urlparse(base_url).path
        if path.startswith(base_path):
            path = path[len(base_path):]
    path = path.strip("/")
    if not path:
        return "Index"
    # Remover extensões
    path = path.replace(".html", "").replace(".md", "").replace(".php", "")
    # Se for algo como "docs/getting-started" -> "Getting Started"
    parts = path.split("/")
    if len(parts) > 1:
        return parts[-1].replace("-", " ").replace("_", " ").title()
    return path.replace("-", " ").replace("_", " ").title()


def _build_nav_tree(pages: list, base_url: str = "") -> dict:
    """Constrói árvore de navegação a partir da lista de páginas.
    
    pages: lista de dicts com 'url', 'title', 'html_content', 'content'
    Retorna: árvore hierárquica de secções -> páginas
    """
    tree = {}
    
    for page in pages:
        url = page["url"]
        path = urlparse(url).path
        
        # Determinar secção (primeiro segmento do path após base)
        if base_url:
            base_path = urlparse(base_url).path
            if path.startswith(base_path):
                path = path[len(base_path):]
        path = path.strip("/")
        segments = path.split("/") if path else []
        
        # Secção = primeiro segmento, ou "Home" se vazio
        section = segments[0] if segments and segments[0] else "home"
        section_title = section.replace("-", " ").replace("_", " ").title()
        if section_title.lower() == "docs":
            section_title = "Documentation"
        
        if section_title not in tree:
            tree[section_title] = []
        
        tree[section_title].append({
            "url": url,
            "title": page.get("title") or _url_to_title(url, base_url),
            "path": path,
        })
    
    return tree


def _build_sidebar_html(nav_tree: dict, page_ids: dict) -> str:
    """Gera HTML da sidebar a partir da árvore de navegação."""
    items = []
    
    # Ordenar secções alfabeticamente, mas "home" primeiro
    sections = sorted(nav_tree.keys(), key=lambda k: (k.lower() != "home", k.lower()))
    
    for section in sections:
        pages = nav_tree[section]
        # Ordenar páginas dentro da secção
        pages_sorted = sorted(pages, key=lambda p: p["path"])
        
        section_id = html.escape(section.lower().replace(" ", "-"))
        items.append(f'<div class="nav-section">')
        items.append(f'  <div class="nav-section-title">{html.escape(section)}</div>')
        
        for page in pages_sorted:
            page_id = page_ids.get(page["url"])
            if page_id:
                items.append(
                    f'  <a href="#page-{page_id}" class="nav-link" data-page="{page_id}">'
                    f'{html.escape(page["title"])}</a>'
                )
        items.append(f'</div>')
    
    return "\n".join(items)


def _extract_main_content(raw_html: str) -> str:
    """Extrai o conteúdo principal de uma página HTML, removendo navegação e boilerplate."""
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(raw_html, "lxml")
    
    # Remover tags irrelevantes
    for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe", 
                               "nav", "footer", "header", "aside"]):
        tag.decompose()
    
    # Remover elementos de navegação comuns
    for selector in ["[role=navigation]", "[role=banner]", "[role=contentinfo]",
                     ".sidebar", ".navbar", ".breadcrumbs", ".pagination",
                     ".table-of-contents", ".toc", ".edit-this-page",
                     ".theme-toggle", ".search-box", ".md-search",
                     ".header", ".footer"]:
        for el in soup.select(selector):
            el.decompose()
    
    # Procurar conteúdo principal
    content = None
    for selector in ["main", "article", "[role=main]", ".content", ".markdown-body",
                     ".documentation", ".doc-content", "#content", ".main-content",
                     "#__docusaurus", ".theme-doc-markdown"]:
        content = soup.select_one(selector)
        if content:
            break
    
    if not content:
        content = soup.body or soup
    
    # Converter links internos para âncoras
    for a in content.find_all("a", href=True):
        href = a["href"]
        # Manter apenas links relativos
        if href.startswith("http"):
            continue
        # Converter para JavaScript de navegação
        a["onclick"] = f"navigateToPath('{href}')"
    
    return str(content)


def generate_site(pages: list, base_url: str, output_path: str,
                  title: str = "Documentation") -> str:
    """Gera um único ficheiro HTML navegável.
    
    pages: lista de dicts com:
        - url: URL original da página
        - title: título da página
        - html_content: HTML renderizado (pode ser string vazia)
        - content: HTML do conteúdo principal extraído (opcional)
    
    base_url: URL base do site
    output_path: caminho do ficheiro HTML de saída
    title: título do site
    
    Retorna: caminho do ficheiro gerado
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Processar páginas: extrair conteúdo principal
    processed_pages = []
    page_ids = {}
    
    for i, page in enumerate(pages):
        page_id = f"p{i}"
        url = page["url"]
        page_ids[url] = page_id
        
        # Se já tem conteúdo extraído, usar; senão extrair de html_content
        if page.get("content"):
            content_html = page["content"]
        elif page.get("html_content"):
            content_html = _extract_main_content(page["html_content"])
        else:
            content_html = "<p>(empty page)</p>"
        
        processed_pages.append({
            "id": page_id,
            "url": url,
            "title": page.get("title") or _url_to_title(url, base_url),
            "content_html": content_html,
        })
    
    # Construir árvore de navegação
    nav_tree = _build_nav_tree(pages, base_url)
    sidebar_html = _build_sidebar_html(nav_tree, page_ids)
    
    # Gerar páginas como divs escondidos
    pages_html = []
    for p in processed_pages:
        pages_html.append(
            f'<div id="page-{p["id"]}" class="page-content" style="display:none;">\n'
            f'  <h1>{html.escape(p["title"])}</h1>\n'
            f'  {p["content_html"]}\n'
            f'</div>'
        )
    
    # Mapeamento URL -> page_id para navegação interna
    url_map = {p["url"]: p["id"] for p in processed_pages}
    url_map_js = ",\n    ".join(
        f'"{url}": "{pid}"' for url, pid in url_map.items()
    )
    
    # HTML final
    site_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
        :root {{
            --bg: #1e1e2e;
            --bg-sidebar: #181825;
            --bg-content: #1e1e2e;
            --bg-card: #313244;
            --text: #cdd6f4;
            --text-dim: #a6adc8;
            --text-muted: #6c7086;
            --accent: #89b4fa;
            --accent-hover: #74c7ec;
            --border: #45475a;
            --success: #a6e3a1;
            --code-bg: #11111b;
            --code-text: #f5e0dc;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
            background: var(--bg);
            color: var(--text);
            display: flex;
            min-height: 100vh;
            font-size: 14px;
            line-height: 1.7;
        }}

        /* ── Sidebar ───────────────────────────────── */
        .sidebar {{
            width: 260px;
            min-width: 260px;
            background: var(--bg-sidebar);
            border-right: 1px solid var(--border);
            padding: 0;
            overflow-y: auto;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            z-index: 100;
        }}

        .sidebar-header {{
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
        }}

        .sidebar-header h1 {{
            font-size: 18px;
            color: var(--accent);
            font-weight: 700;
        }}

        .sidebar-header .source {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 4px;
            word-break: break-all;
        }}

        .nav-section {{ margin-bottom: 8px; }}

        .nav-section-title {{
            padding: 10px 20px 4px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
        }}

        .nav-link {{
            display: block;
            padding: 5px 20px 5px 28px;
            color: var(--text-dim);
            text-decoration: none;
            font-size: 13px;
            border-left: 2px solid transparent;
            transition: all 0.15s;
        }}

        .nav-link:hover {{
            color: var(--accent);
            background: rgba(137, 180, 250, 0.08);
        }}

        .nav-link.active {{
            color: var(--accent);
            border-left-color: var(--accent);
            background: rgba(137, 180, 250, 0.05);
            font-weight: 600;
        }}

        /* ── Content ───────────────────────────────── */
        .content-area {{
            margin-left: 260px;
            flex: 1;
            padding: 40px 48px;
            max-width: 100%;
            overflow-x: hidden;
        }}

        .page-content h1 {{
            font-size: 28px;
            color: var(--text);
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
        }}

        .page-content h2 {{
            font-size: 22px;
            color: var(--text);
            margin-top: 32px;
            margin-bottom: 12px;
        }}

        .page-content h3 {{
            font-size: 18px;
            color: var(--text);
            margin-top: 24px;
            margin-bottom: 8px;
        }}

        .page-content h4 {{
            font-size: 16px;
            color: var(--text-dim);
            margin-top: 20px;
            margin-bottom: 6px;
        }}

        .page-content p {{
            margin-bottom: 14px;
            color: var(--text);
        }}

        .page-content ul, .page-content ol {{
            margin-left: 24px;
            margin-bottom: 14px;
        }}

        .page-content li {{
            margin-bottom: 4px;
            color: var(--text);
        }}

        .page-content a {{
            color: var(--accent);
            text-decoration: none;
            cursor: pointer;
        }}

        .page-content a:hover {{
            color: var(--accent-hover);
            text-decoration: underline;
        }}

        .page-content code {{
            background: var(--code-bg);
            color: var(--code-text);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: "Fira Code", "Cascadia Code", Consolas, monospace;
            font-size: 13px;
        }}

        .page-content pre {{
            background: var(--code-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
            overflow-x: auto;
            margin-bottom: 16px;
        }}

        .page-content pre code {{
            background: none;
            padding: 0;
            font-size: 13px;
            line-height: 1.6;
        }}

        .page-content table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 16px;
        }}

        .page-content th, .page-content td {{
            border: 1px solid var(--border);
            padding: 8px 12px;
            text-align: left;
        }}

        .page-content th {{
            background: var(--bg-card);
            color: var(--text-dim);
            font-weight: 600;
        }}

        .page-content blockquote {{
            border-left: 3px solid var(--accent);
            padding-left: 16px;
            color: var(--text-dim);
            margin-bottom: 14px;
            font-style: italic;
        }}

        .page-content img {{
            max-width: 100%;
            border-radius: 8px;
        }}

        .page-content .info-box {{
            background: rgba(137, 180, 250, 0.1);
            border: 1px solid var(--accent);
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 14px;
        }}

        /* ── Search ───────────────────────────────── */
        .search-box {{
            margin: 12px 16px 8px;
        }}

        .search-box input {{
            width: 100%;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 8px 12px;
            color: var(--text);
            font-size: 13px;
            outline: none;
        }}

        .search-box input:focus {{
            border-color: var(--accent);
        }}

        .search-box input::placeholder {{
            color: var(--text-muted);
        }}

        /* ── Scrollbar ─────────────────────────────── */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg-sidebar); }}
        ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}

        /* ── Loading ───────────────────────────────── */
        .loading {{
            text-align: center;
            padding: 60px;
            color: var(--text-muted);
        }}

        /* ── Mobile ───────────────────────────────── */
        .menu-toggle {{
            display: none;
            position: fixed;
            top: 12px;
            left: 12px;
            z-index: 200;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 8px 12px;
            color: var(--text);
            cursor: pointer;
            font-size: 16px;
        }}

        @media (max-width: 768px) {{
            .sidebar {{ transform: translateX(-100%); transition: transform 0.3s; }}
            .sidebar.open {{ transform: translateX(0); }}
            .content-area {{ margin-left: 0; padding: 40px 20px; }}
            .menu-toggle {{ display: block; }}
        }}
    </style>
</head>
<body>
    <button class="menu-toggle" onclick="document.querySelector('.sidebar').classList.toggle('open')">☰</button>

    <div class="sidebar">
        <div class="sidebar-header">
            <h1>{html.escape(title)}</h1>
            <div class="source">Source: {html.escape(base_url)}</div>
            <div class="source">Extracted: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
            <div class="source">Pages: {len(processed_pages)}</div>
        </div>
        <div class="search-box">
            <input type="text" id="search" placeholder="Filter pages..." oninput="filterPages(this.value)">
        </div>
        {sidebar_html}
    </div>

    <div class="content-area" id="contentArea">
        <div class="loading" id="loadingMsg">Select a page from the sidebar...</div>
        {chr(10).join(pages_html)}
    </div>

    <script>
        const urlToPage = {{
    {url_map_js}
        }};

        let currentPage = null;

        function showPage(pageId) {{
            if (currentPage) {{
                const old = document.getElementById('page-' + currentPage);
                if (old) old.style.display = 'none';
            }}
            const el = document.getElementById('page-' + pageId);
            if (el) {{
                el.style.display = 'block';
                currentPage = pageId;
                // Actualizar link activo
                document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                const link = document.querySelector('.nav-link[data-page="' + pageId + '"]');
                if (link) {{
                    link.classList.add('active');
                    // Scroll sidebar to active link
                    link.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
                }}
                // Scroll content to top
                window.scrollTo(0, 0);
                // Esconder loading
                document.getElementById('loadingMsg').style.display = 'none';
            }}
        }}

        // Navegação por hash
        window.addEventListener('hashchange', function() {{
            const hash = window.location.hash;
            if (hash.startsWith('#page-')) {{
                showPage(hash.substring(6));
            }}
        }});

        // Navegação interna por path
        function navigateToPath(path) {{
            // Procurar página que corresponde ao path
            for (const [url, pageId] of Object.entries(urlToPage)) {{
                const urlPath = new URL(url).pathname;
                if (urlPath === path || urlPath.endsWith(path)) {{
                    window.location.hash = 'page-' + pageId;
                    return;
                }}
            }}
            // Se não encontrou, tentar como ID directo
            if (urlToPage[path]) {{
                window.location.hash = 'page-' + urlToPage[path];
            }}
        }}

        // Filtro de páginas
        function filterPages(query) {{
            query = query.toLowerCase();
            document.querySelectorAll('.nav-link').forEach(link => {{
                const text = link.textContent.toLowerCase();
                link.style.display = text.includes(query) ? '' : 'none';
            }});
            document.querySelectorAll('.nav-section-title').forEach(title => {{
                const section = title.parentElement;
                const hasVisible = section.querySelectorAll('.nav-link[style=""], .nav-link:not([style*="none"])').length > 0;
                section.style.display = hasVisible ? '' : 'none';
            }});
        }}

        // Mostrar primeira página ao carregar
        window.addEventListener('DOMContentLoaded', function() {{
            const hash = window.location.hash;
            if (hash.startsWith('#page-')) {{
                showPage(hash.substring(6));
            }} else {{
                // Mostrar primeira página
                const firstLink = document.querySelector('.nav-link');
                if (firstLink) {{
                    showPage(firstLink.dataset.page);
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(site_html)
    
    return output_path