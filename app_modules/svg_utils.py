from __future__ import annotations

import html

from metaLoop.imageGeneration.jjscript_to_image import parse_jjscript, build_svg


def _to_svg(jjscript: str, title: str = "Graph") -> str:
    text = jjscript.strip()
    for fence in ("```jjscript", "```python", "```"):
        text = text.replace(fence, "")
    text = text.strip()
    if not text:
        return ""
    try:
        classes, instances = parse_jjscript(text)
        return build_svg(classes, instances, title=title)
    except Exception:
        return f"<pre style='white-space:pre-wrap'>{html.escape(text)}</pre>"
