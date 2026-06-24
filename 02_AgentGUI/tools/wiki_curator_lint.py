#!/usr/bin/env python3
"""
Wiki Curator — Automated lint & maintenance for all LLM Wiki projects.
Runs as background thread, emits progress via Socket.IO.
"""

import os, re, json, sys
from pathlib import Path
from datetime import datetime

WIKI_BASE = Path("/media/sf_AI_Ecosystem/12_LLM_Wiki")

class WikiCurator:
    def __init__(self, socketio=None, sid=None):
        self.socketio = socketio
        self.sid = sid
        self.results = []
        self.total_steps = 0
        self.current_step = 0

    def _emit(self, event, data):
        if self.socketio:
            if self.sid:
                self.socketio.emit(event, data, room=self.sid)
            else:
                self.socketio.emit(event, data)

    def _progress(self, message, pct):
        self._emit('wiki_curate_progress', {
            'step': self.current_step,
            'total': self.total_steps,
            'message': message,
            'percent': pct,
            'timestamp': datetime.now().isoformat()
        })

    def run(self):
        """Run full curation across all wiki projects."""
        projects = [p for p in WIKI_BASE.iterdir() if p.is_dir() and (p / 'Wiki').is_dir()]
        self.total_steps = len(projects) * 5 + 1  # 5 phases per project + summary
        self.current_step = 0

        self._progress("Starting wiki curation...", 0)

        for proj in projects:
            self._curate_project(proj)

        self.current_step = self.total_steps
        self._emit('wiki_curate_complete', {
            'results': self.results,
            'timestamp': datetime.now().isoformat()
        })

    def _curate_project(self, proj_path: Path):
        name = proj_path.name
        wiki_path = proj_path / 'Wiki'
        raw_path = proj_path / 'Raw'

        self.current_step += 1
        self._progress(f"[{name}] Scanning structure...", int(self.current_step / self.total_steps * 100))

        # Phase 1: Enumerate all pages
        pages = {}  # page_name -> filepath
        for root, dirs, files in os.walk(wiki_path):
            for f in files:
                if f.endswith('.md'):
                    rel = Path(root).relative_to(wiki_path)
                    page_name = str(rel / f[:-3])
                    if page_name.startswith('.'):
                        page_name = page_name[1:]
                    pages[page_name] = Path(root) / f

        # Phase 2: Read index
        self.current_step += 1
        self._progress(f"[{name}] Checking index...", int(self.current_step / self.total_steps * 100))

        index_path = wiki_path / 'index.md'
        index_content = ""
        if index_path.exists():
            index_content = index_path.read_text(encoding='utf-8')

        # Phase 3: Build link graph
        self.current_step += 1
        self._progress(f"[{name}] Analyzing links...", int(self.current_step / self.total_steps * 100))

        outbound = {}   # page -> [targets]
        inbound = {}    # target -> [sources]
        for page_name, filepath in pages.items():
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            links = re.findall(r'\[\[([^\]]+)\]\]', content)
            targets = []
            for link in links:
                target = link.split('|')[0].strip()
                targets.append(target)
                if target not in inbound:
                    inbound[target] = []
                inbound[target].append(page_name)
            outbound[page_name] = targets

        # Phase 4: Detect issues
        self.current_step += 1
        self._progress(f"[{name}] Detecting issues...", int(self.current_step / self.total_steps * 100))

        issues = {
            'orphans': [],
            'missing_in_index': [],
            'broken_links': [],
            'missing_dates': [],
            'oversized': [],
        }

        # Orphans = no inbound links (excluding index, log)
        for page_name in pages:
            if page_name in ('index', 'log', 'wiki-architecture'):
                continue
            if page_name not in inbound or len(inbound[page_name]) == 0:
                issues['orphans'].append(page_name)

        # Missing from index
        for page_name in pages:
            if page_name in ('index', 'log'):
                continue
            safe_name = page_name.replace('/', '-')
            if f'[[{page_name}]]' not in index_content and f'[[{safe_name}]]' not in index_content:
                issues['missing_in_index'].append(page_name)

        # Broken links (link points to non-existent page)
        for page_name, targets in outbound.items():
            for target in targets:
                if target not in pages:
                    issues['broken_links'].append((page_name, target))

        # Missing date in header
        for page_name, filepath in pages.items():
            if page_name in ('index', 'log'):
                continue
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            if not re.search(r'(updated|date).*(20\d{2}-\d{2}-\d{2}|20\d{2}/\d{2}/\d{2})', content, re.IGNORECASE):
                if not re.search(r'Last updated.*20\d{2}', content):
                    issues['missing_dates'].append(page_name)

        # Oversized pages (>200 lines)
        for page_name, filepath in pages.items():
            lines = filepath.read_text(encoding='utf-8', errors='ignore').splitlines()
            if len(lines) > 200:
                issues['oversized'].append((page_name, len(lines)))

        # Phase 5: Auto-fix
        self.current_step += 1
        self._progress(f"[{name}] Auto-fixing...", int(self.current_step / self.total_steps * 100))

        fixes = []

        # Fix 1: Add missing pages to index
        if issues['missing_in_index']:
            today = datetime.now().strftime('%Y-%m-%d')
            additions = []
            for page_name in issues['missing_in_index']:
                # Infer section from path
                section = "Concepts"
                if 'entities' in page_name.lower():
                    section = "Entities"
                elif 'comparison' in page_name.lower():
                    section = "Comparisons"
                elif 'log' in page_name.lower():
                    section = "Operations"
                additions.append(f"- [[{page_name}]] — *(auto-added {today})*")

            if index_path.exists():
                content = index_path.read_text(encoding='utf-8')
                # Find a section to append to
                lines = content.splitlines()
                # Append before the last section or at end
                content += "\n\n## Auto-curated\n" + "\n".join(additions) + "\n"
                index_path.write_text(content, encoding='utf-8')
                fixes.append(f"Added {len(additions)} pages to index.md")

        # Fix 2: Remove broken links (replace [[broken]] with `broken`)
        for source_page, target in issues['broken_links']:
            filepath = pages.get(source_page)
            if filepath:
                content = filepath.read_text(encoding='utf-8')
                content = re.sub(rf'\[\[{re.escape(target)}(\|[^\]]*)?\]\]', f'`{target}`', content)
                filepath.write_text(content, encoding='utf-8')
                fixes.append(f"Fixed broken link [[{target}]] in {source_page}")

        # Fix 3: Archive orphans (move to _archive/)
        if issues['orphans']:
            archive_dir = wiki_path / '_archive'
            archive_dir.mkdir(exist_ok=True)
            for page_name in issues['orphans']:
                filepath = pages.get(page_name)
                if filepath and filepath.exists():
                    dest = archive_dir / filepath.name
                    filepath.rename(dest)
                    fixes.append(f"Archived orphan page {page_name}")

        # Fix 4: Add date header to pages missing it
        for page_name in issues['missing_dates']:
            filepath = pages.get(page_name)
            if filepath:
                content = filepath.read_text(encoding='utf-8')
                today = datetime.now().strftime('%Y-%m-%d')
                # Insert after first heading
                lines = content.splitlines()
                if lines:
                    new_lines = []
                    inserted = False
                    for line in lines:
                        new_lines.append(line)
                        if not inserted and line.startswith('#'):
                            new_lines.append(f"\n> Last updated: {today}")
                            inserted = True
                    if not inserted:
                        new_lines.insert(0, f"> Last updated: {today}\n")
                    filepath.write_text('\n'.join(new_lines), encoding='utf-8')
                    fixes.append(f"Added date header to {page_name}")

        # Update log.md
        log_path = wiki_path / 'log.md'
        today = datetime.now().strftime('%Y-%m-%d')
        log_entry = f"\n## {today} (Auto-curation)\n"
        log_entry += f"- Scanned {len(pages)} pages\n"
        log_entry += f"- Found {sum(len(v) for v in issues.values() if isinstance(v, list))} issues\n"
        if fixes:
            log_entry += f"- Applied {len(fixes)} auto-fixes:\n"
            for f in fixes[:10]:
                log_entry += f"  - {f}\n"
        else:
            log_entry += "- No fixes needed (wiki clean)\n"

        if log_path.exists():
            log_content = log_path.read_text(encoding='utf-8')
            log_path.write_text(log_content + log_entry, encoding='utf-8')
        else:
            log_path.write_text(f"# Wiki Log\n\n{log_entry}", encoding='utf-8')

        # Store result
        self.results.append({
            'project': name,
            'pages': len(pages),
            'issues': {k: len(v) for k, v in issues.items()},
            'fixes': fixes,
            'orphans_archived': len(issues['orphans']),
        })


def run_curation(socketio=None, sid=None):
    """Entry point for threaded execution."""
    curator = WikiCurator(socketio=socketio, sid=sid)
    curator.run()


if __name__ == '__main__':
    # Standalone mode for testing
    run_curation()
    print(json.dumps({"results": WikiCurator().results}, indent=2))
