"""
Import a static HTML page from a URL: fetch the page, extract body HTML, CSS, and JS,
so they can be stored and rendered as a dynamic CMS page.
"""
import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TopTeen-CMS-Import/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_url(url, timeout=DEFAULT_TIMEOUT):
    """Fetch URL and return (content, final_url) or (None, None) on failure."""
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return r.text, r.url
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None, None


def _resolve_url(base_url, href):
    if not href or href.strip().startswith(("#", "data:", "javascript:")):
        return None
    return urljoin(base_url, href.strip())


def _fetch_css_url(css_url, timeout=DEFAULT_TIMEOUT):
    try:
        r = requests.get(css_url, headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        logger.warning("Failed to fetch CSS %s: %s", css_url, e)
        return ""


def _fetch_js_url(js_url, timeout=DEFAULT_TIMEOUT):
    try:
        r = requests.get(js_url, headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        logger.warning("Failed to fetch JS %s: %s", js_url, e)
        return ""


def import_page_from_url(source_url, timeout=DEFAULT_TIMEOUT):
    """
    Fetch a URL and extract content for a generated CMS page.
    Returns dict: success, error, content_html, content_css, content_js, title.
    """
    result = {
        "success": False,
        "error": "",
        "content_html": "",
        "content_css": "",
        "content_js": "",
        "title": "",
    }
    html_text, final_url = _fetch_url(source_url, timeout=timeout)
    if not html_text:
        result["error"] = "Could not fetch URL (connection failed or non-200 response)."
        return result

    base_url = final_url or source_url
    soup = BeautifulSoup(html_text, "html.parser")

    title_tag = soup.find("title")
    result["title"] = (title_tag.get_text(strip=True) if title_tag else "") or "Imported Page"

    body = soup.find("body")
    if body:
        body_copy = BeautifulSoup(str(body), "html.parser")
        for tag in body_copy.find_all(["script", "style", "link"]):
            tag.decompose()
        content_html = body_copy.decode_contents()
    else:
        content_html = str(soup)
    result["content_html"] = content_html.strip()

    css_parts = []
    for style in soup.find_all("style"):
        if style.string:
            css_parts.append(style.string.strip())
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        resolved = _resolve_url(base_url, href) if href else None
        if resolved:
            content = _fetch_css_url(resolved, timeout=timeout)
            if content:
                css_parts.append(content)
    result["content_css"] = "\n\n".join(css_parts).strip()

    js_parts = []
    for script in soup.find_all("script"):
        src = script.get("src")
        if src:
            resolved = _resolve_url(base_url, src)
            if resolved:
                content = _fetch_js_url(resolved, timeout=timeout)
                if content:
                    js_parts.append(content)
        elif script.string:
            js_parts.append(script.string.strip())
    result["content_js"] = "\n\n".join(js_parts).strip()

    result["success"] = True
    return result
