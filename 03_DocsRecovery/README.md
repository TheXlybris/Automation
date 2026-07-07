# docscraper

Universal documentation extractor. Local, free, no API limits.

Extracts ALL documentation from any website using a 5-layer cascade pipeline:
llms.txt → sitemap → link discovery → GitHub → wget → Playwright.

## Features

- **5-layer cascade** — automatically picks the best extraction method per site
- **GUI (tkinter)** — dark theme, real-time log, progress bar, file dialog
- **Site HTML mode** — generates a single navigable HTML page with sidebar + content
- **Parallel Playwright** — renders 4 pages simultaneously for better performance
- **Keep HTML** — option to preserve original HTML alongside markdown
- **CLI + GUI** — use from terminal or desktop

## Quick Start

```bash
# GUI (recommended)
bash docscraper_gui.sh

# CLI
python3 docscraper.py https://example.com/docs/ -o ~/output/ -v

# Generate navigable site HTML
python3 docscraper.py https://example.com/docs/ -o ~/output/ --output-mode site --layer playwright
```

## Layers (cascade)

The tool tries each layer in order. Uses the first one that works:

0. **llms.txt / llms-full** — checks for `/llms.txt` or `llms*.txt` linked in HTML
1. **sitemap.xml** — extracts all URLs from sitemap, filters to base path
2. **link discovery** — recursive internal link crawling via HTML parsing
3. **GitHub source** — detects public repo with markdown source and clones
4. **wget mirror** — mirrors site recursively (static HTML)
5. **Playwright** — renders SPAs with headless Chromium (JavaScript)

## Output Modes

- **files** — individual `.md` files per page + `index.md`
- **site** — single `site.html` with sidebar navigation, dark theme, search filter

## CLI Options

```
python3 docscraper.py <url> [options]

  -o, --output DIR       Output directory (default: ./output)
  --layer LAYER          Force specific layer (llms_txt, sitemap, link_discovery, github, wget, playwright)
  --output-mode MODE     files | site (default: files)
  --max-depth N          Max crawl depth for link discovery (default: 3)
  --keep-html            Keep original HTML files
  --list-urls            List discovered URLs without downloading
  -v, --verbose          Verbose output
```

## Dependencies

```bash
# Python packages (auto-installed by launcher)
pip install requests beautifulsoup4 lxml markdownify playwright
playwright install chromium

# System (for GUI)
sudo apt install python3-tk python3-venv
```

## Project Structure

```
03_DocsRecovery/
├── docscraper.py            # CLI main (5-layer cascade pipeline)
├── docscraper_gui.py        # tkinter GUI (dark theme, progress bar)
├── docscraper_gui.sh        # GUI launcher (auto-creates venv + deps)
├── docscraper_web.py        # Web GUI alternative (localhost:8501)
├── docscraper.sh            # Web GUI launcher
├── docscraper.desktop       # Desktop entry for app menu
├── extractors/
│   ├── llms_txt.py          # Layer 0: llms.txt + llms-full detection
│   ├── sitemap.py           # Layer 0: sitemap.xml parser
│   ├── link_discovery.py    # Layer 1: recursive link discovery
│   ├── github_source.py     # Layer 2: GitHub repo clone
│   ├── wget_mirror.py       # Layer 3: wget mirror
│   └── playwright_crawl.py  # Layer 4: Playwright headless (parallel)
├── utils/
│   ├── html_to_md.py        # HTML → markdown conversion
│   ├── url_utils.py         # URL normalization and filtering
│   └── site_generator.py    # Unified site HTML generator (sidebar + nav)
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10+
- Linux (tested on Ubuntu 24.04 Server + XFCE4, Linux Mint 22)
- VirtualBox Guest Additions (for shared folder support in VMs)