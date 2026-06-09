from __future__ import annotations

import base64
import html
import uuid

from metaLoop.imageGeneration.jjscript_to_image import parse_jjscript, build_svg


def _to_svg(jjscript: str, title: str = "Graph", highlight_names: set[str] | None = None) -> str:
    text = jjscript.strip()
    for fence in ("```jjscript", "```python", "```"):
        text = text.replace(fence, "")
    text = text.strip()
    if not text:
        return ""
    try:
        classes, instances = parse_jjscript(text)
        svg = build_svg(
            classes,
            instances,
            title=title,
            highlight_classes=highlight_names,
        )
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        uid = uuid.uuid4().hex
        return f"""
<div class='svg-preview'>
  <div class='svg-preview-header'>
    <span>{html.escape(title)}</span>
    <span class='svg-preview-actions'>
      <a href='#svg-overlay-{uid}' class='svg-fullscreen-link'>View full screen</a>
      <a href='data:image/svg+xml;base64,{encoded}' target='_blank' class='svg-open-tab-link'>Open in new tab</a>
    </span>
  </div>
  <div class='svg-preview-inner'>{svg}</div>
</div>
<div id='svg-overlay-{uid}' class='svg-overlay'>
  <div class='svg-overlay-content'>
    <a class='svg-overlay-close' href='#'>×</a>
    <div class='svg-overlay-title'>{html.escape(title)}</div>
    <div class='svg-overlay-hint'>Scroll to zoom, drag to pan, or open in a new tab.</div>
    <div class='svg-overlay-inner'>{svg}</div>
  </div>
</div>
"""
    except Exception:
        return f"<pre style='white-space:pre-wrap'>{html.escape(text)}</pre>"
