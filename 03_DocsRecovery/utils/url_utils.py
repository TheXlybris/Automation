"""URL utilities: normalization, filtering, filename generation."""

from urllib.parse import urlparse, urljoin, urldefrag
import re
import os


def normalize_base_url(url: str) -> str:
    """Ensure URL has scheme, trailing slash for path root."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def is_same_site(url: str, base_url: str) -> bool:
    """Check if url belongs to the same domain as base_url."""
    base_host = urlparse(base_url).netloc
    url_host = urlparse(url).netloc
    return base_host == url_host


def is_subpath(url: str, base_url: str) -> bool:
    """Check if url is under the base_url path prefix."""
    base = urlparse(base_url)
    target = urlparse(url)
    if base.netloc != target.netloc:
        return False
    return target.path.startswith(base.path.rstrip("/"))


def url_to_filename(url: str, base_url: str = "") -> str:
    """Convert a URL to a safe filename."""
    parsed = urlparse(url)
    path = parsed.path

    # Strip base path prefix if given
    if base_url:
        base_path = urlparse(base_url).path.rstrip("/")
        if path.startswith(base_path):
            path = path[len(base_path):]

    # Remove leading/trailing slashes
    path = path.strip("/")

    # If empty, it's the root page
    if not path:
        return "index.md"

    # Replace slashes with underscores, remove extension
    path = re.sub(r"\.(html?|php|aspx?)$", "", path)
    path = path.replace("/", "_")

    # Add .md extension
    if not path.endswith(".md"):
        path += ".md"

    return path


def defrag(url: str) -> str:
    """Remove fragment from URL."""
    clean, _ = urldefrag(url)
    return clean


def resolve_url(url: str, base: str) -> str:
    """Resolve a relative URL against a base URL."""
    return urljoin(base, url)