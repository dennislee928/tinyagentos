"""Head injector — adds copilot.js + meta tags to proxied HTML.

Inserts:
- <script src="/__taos/copilot.js"></script>     — the in-page agent
- <meta name="taos-copilot-ws" content="...">    — websocket URL the
                                                    script connects to

Idempotent: re-injecting on already-injected output is a no-op.
"""
from __future__ import annotations

from lxml import html as lxml_html


_SCRIPT_SRC = "/__taos/copilot.js"
_WS_META_NAME = "taos-copilot-ws"


def inject_into_head(html_bytes: bytes, *, ws_url: str) -> bytes:
    """Insert the copilot.js script + WS meta into the document head.

    Idempotent: existing copilot script tags are left in place rather
    than duplicated.
    """
    if not html_bytes:
        return b""

    parser = lxml_html.HTMLParser(encoding="utf-8")
    try:
        tree = lxml_html.fromstring(html_bytes, parser=parser)
    except Exception:
        return html_bytes

    if tree is None:
        return html_bytes

    head = tree.find(".//head")
    if head is None:
        # Create a head and insert at the start of the document
        head = lxml_html.Element("head")
        tree.insert(0, head)

    # Idempotency check
    has_copilot = any(
        s.get("src") == _SCRIPT_SRC
        for s in head.iter("script")
    )
    if not has_copilot:
        script = lxml_html.Element("script")
        script.set("src", _SCRIPT_SRC)
        head.insert(0, script)

    # WS meta — overwrite existing rather than append
    existing_meta = None
    for meta in head.iter("meta"):
        if meta.get("name") == _WS_META_NAME:
            existing_meta = meta
            break

    if existing_meta is not None:
        existing_meta.set("content", ws_url)
    else:
        meta = lxml_html.Element("meta")
        meta.set("name", _WS_META_NAME)
        meta.set("content", ws_url)
        head.insert(0, meta)

    return lxml_html.tostring(tree, encoding="utf-8")
