#!/usr/bin/env python3
"""
Self-contained JJscript -> graph image converter.

Supported JJscript subset (class-oriented):

    # comments are ignored
    Disease:
      name: String
      symptoms -> Symptom [*]
      diagnosedBy -> DiagnosticProcedure

    Symptom:
      name: String

    end:

Rules:
- "ClassName:" starts a class block.
- "field: Type" defines an attribute.
- "relation -> Target" defines an edge.
- Optional multiplicity syntax is preserved in labels, e.g. [*], [0..1], [1].
- "end:" is optional and ignored.

Output:
- .svg is always supported (pure stdlib).
- .png is supported if Pillow is installed (preferred) or if cairosvg is installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import argparse
import html
import math
import re
import sys
from typing import Dict, List, Optional, Tuple


@dataclass
class Relation:
    name: str
    target: str
    multiplicity: str = ""


@dataclass
class ClassNode:
    name: str
    attributes: List[Tuple[str, str]] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)


CLASS_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
ATTR_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^\n#]+?)\s*$")
REL_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*->\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\[[^\]]+\])?\s*$"
)
CREATE_CLASS_RE = re.compile(r"^\s*create\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", re.IGNORECASE)
CREATE_ABSTRACT_CLASS_RE = re.compile(
    r"^\s*create\s+abstract\s+class\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+([A-Za-z_][A-Za-z0-9_]*))?\s*$",
    re.IGNORECASE,
)
CREATE_CLASS_EXTENDS_RE = re.compile(
    r"^\s*create\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\s+extends\s+([A-Za-z_][A-Za-z0-9_]*)\s*$",
    re.IGNORECASE,
)
CREATE_ATTR_RE = re.compile(
    r"^\s*create\s+attribute\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([A-Za-z_][A-Za-z0-9_]*)\s+type\s+([^\n#]+?)\s*$",
    re.IGNORECASE,
)
CREATE_REF_RE = re.compile(
    r"^\s*create\s+(?:reference|containment)\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([A-Za-z_][A-Za-z0-9_]*)\s+type\s+([A-Za-z_][A-Za-z0-9_]*)\s*(\[[^\]]+\])?\s*$",
    re.IGNORECASE,
)
CREATE_INSTANCE_RE = re.compile(
    r"^\s*create\s+instance\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([A-Za-z_][A-Za-z0-9_]*)\s*$",
    re.IGNORECASE,
)


def _strip_comment(line: str) -> str:
    idx = line.find("#")
    return line if idx < 0 else line[:idx]


def parse_jjscript(text: str) -> Dict[str, ClassNode]:
    """Parse JJscript text into a class graph dictionary."""
    classes: Dict[str, ClassNode] = {}
    current: Optional[ClassNode] = None

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw_line).strip()
        if not line:
            continue

        if line.lower() == "end:":
            current = None
            continue

        # Ignore dangling/incomplete commands such as a lone "create" line.
        if line.lower() == "create":
            continue

        create_class_match = CREATE_CLASS_EXTENDS_RE.match(line) or CREATE_CLASS_RE.match(line)
        if create_class_match:
            class_name = create_class_match.group(1)
            current = classes.get(class_name)
            if current is None:
                current = ClassNode(name=class_name)
                classes[class_name] = current
            if create_class_match.lastindex and create_class_match.lastindex >= 2 and create_class_match.group(2):
                parent = create_class_match.group(2)
                if parent not in classes:
                    classes[parent] = ClassNode(name=parent)
                current.relations.append(Relation(name="extends", target=parent))
            continue

        create_abstract_match = CREATE_ABSTRACT_CLASS_RE.match(line)
        if create_abstract_match:
            class_name = create_abstract_match.group(1)
            current = classes.get(class_name)
            if current is None:
                current = ClassNode(name=class_name)
                classes[class_name] = current
            if create_abstract_match.group(2):
                parent = create_abstract_match.group(2)
                if parent not in classes:
                    classes[parent] = ClassNode(name=parent)
                current.relations.append(Relation(name="extends", target=parent))
            continue

        create_attr_match = CREATE_ATTR_RE.match(line)
        if create_attr_match:
            attr_name, owner_name, attr_type = create_attr_match.groups()
            owner = classes.get(owner_name)
            if owner is None:
                owner = ClassNode(name=owner_name)
                classes[owner_name] = owner
            owner.attributes.append((attr_name, attr_type.strip()))
            current = owner
            continue

        create_ref_match = CREATE_REF_RE.match(line)
        if create_ref_match:
            rel_name, owner_name, target_name, mult = create_ref_match.groups()
            owner = classes.get(owner_name)
            if owner is None:
                owner = ClassNode(name=owner_name)
                classes[owner_name] = owner
            owner.relations.append(
                Relation(name=rel_name, target=target_name, multiplicity=(mult or ""))
            )
            if target_name not in classes:
                classes[target_name] = ClassNode(name=target_name)
            current = owner
            continue

        create_instance_match = CREATE_INSTANCE_RE.match(line)
        if create_instance_match:
            inst_name = create_instance_match.group(1)
            owner_name = create_instance_match.group(2)
            owner = classes.get(owner_name)
            if owner is None:
                owner = ClassNode(name=owner_name)
                classes[owner_name] = owner
            current = owner
            continue

        class_match = CLASS_RE.match(line)
        if class_match:
            class_name = class_match.group(1)
            current = classes.get(class_name)
            if current is None:
                current = ClassNode(name=class_name)
                classes[class_name] = current
            continue

        if current is None:
            continue  # skip unrecognized lines outside a class block

        rel_match = REL_RE.match(line)
        if rel_match:
            rel_name, target, mult = rel_match.groups()
            current.relations.append(Relation(name=rel_name, target=target, multiplicity=(mult or "")))
            if target not in classes:
                classes[target] = ClassNode(name=target)
            continue

        attr_match = ATTR_RE.match(line)
        if attr_match:
            attr_name, attr_type = attr_match.groups()
            current.attributes.append((attr_name, attr_type.strip()))
            continue

        # Skip unrecognized lines gracefully

    if not classes:
        raise ValueError("No classes parsed from JJscript input.")

    return classes


def _compute_node_sizes(classes: Dict[str, ClassNode]) -> Dict[str, Tuple[int, int]]:
    sizes: Dict[str, Tuple[int, int]] = {}
    for name, node in classes.items():
        max_line = len(name)
        for a, t in node.attributes:
            max_line = max(max_line, len(f"{a}: {t}"))
        width = max(180, 12 * max_line + 36)
        lines = 1 + len(node.attributes)
        height = 48 + max(0, lines - 1) * 24
        sizes[name] = (width, height)
    return sizes


def _compute_circle_layout(classes: Dict[str, ClassNode]) -> Dict[str, Tuple[float, float]]:
    names = sorted(classes.keys())
    n = len(names)
    if n == 1:
        return {names[0]: (0.0, 0.0)}

    radius = max(220.0, 90.0 * n)
    positions: Dict[str, Tuple[float, float]] = {}

    for i, name in enumerate(names):
        angle = (2.0 * math.pi * i / n) - (math.pi / 2.0)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        positions[name] = (x, y)

    return positions


def _line_box_intersection(
    cx: float, cy: float, tx: float, ty: float, w: float, h: float
) -> Tuple[float, float]:
    """Intersection between center->target ray and axis-aligned rectangle border."""
    dx = tx - cx
    dy = ty - cy
    if dx == 0 and dy == 0:
        return cx, cy

    hw = w / 2.0
    hh = h / 2.0

    scale_x = abs(hw / dx) if dx != 0 else float("inf")
    scale_y = abs(hh / dy) if dy != 0 else float("inf")
    scale = min(scale_x, scale_y)

    return cx + dx * scale, cy + dy * scale


def _bundle_key(source: str, target: str) -> Tuple[str, str]:
    # Group A->B and B->A in the same bundle so both directions can avoid overlap.
    return (source, target) if source <= target else (target, source)


def _edge_lane_offset(
    source_name: str,
    target_name: str,
    bundle_totals: Dict[Tuple[str, str], int],
    bundle_seen: Dict[Tuple[str, str], int],
    lane_gap: float = 18.0,
) -> float:
    key = _bundle_key(source_name, target_name)
    idx = bundle_seen.get(key, 0)
    bundle_seen[key] = idx + 1
    total = bundle_totals.get(key, 1)
    center = (total - 1) / 2.0
    return (idx - center) * lane_gap


def build_svg(classes: Dict[str, ClassNode], title: str = "JJscript Graph") -> str:
    sizes = _compute_node_sizes(classes)
    pos = _compute_circle_layout(classes)

    min_x = min(pos[name][0] - sizes[name][0] / 2 for name in classes)
    max_x = max(pos[name][0] + sizes[name][0] / 2 for name in classes)
    min_y = min(pos[name][1] - sizes[name][1] / 2 for name in classes)
    max_y = max(pos[name][1] + sizes[name][1] / 2 for name in classes)

    padding = 80
    width = int(max_x - min_x + 2 * padding)
    height = int(max_y - min_y + 2 * padding)

    def tr(point: Tuple[float, float]) -> Tuple[float, float]:
        x, y = point
        return x - min_x + padding, y - min_y + padding

    lines: List[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" style="max-width:100%;height:auto;">'
    )
    lines.append("<defs>")
    lines.append(
        '<marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">'
    )
    lines.append('<path d="M0,0 L10,4 L0,8 z" fill="#4b5563"/>')
    lines.append("</marker>")
    lines.append("</defs>")

    lines.append('<rect x="0" y="0" width="100%" height="100%" fill="#f8fafc"/>')
    lines.append(
        f'<text x="24" y="34" font-family="Arial, sans-serif" font-size="22" fill="#0f172a" font-weight="700">{html.escape(title)}</text>'
    )

    bundle_totals: Dict[Tuple[str, str], int] = {}
    for source_name, source in classes.items():
        for rel in source.relations:
            if rel.target not in classes:
                continue
            key = _bundle_key(source_name, rel.target)
            bundle_totals[key] = bundle_totals.get(key, 0) + 1
    bundle_seen: Dict[Tuple[str, str], int] = {}

    # Draw edges first.
    for source_name, source in classes.items():
        sx, sy = tr(pos[source_name])
        sw, sh = sizes[source_name]

        for rel in source.relations:
            if rel.target not in classes:
                continue
            tx, ty = tr(pos[rel.target])
            tw, th = sizes[rel.target]

            x1, y1 = _line_box_intersection(sx, sy, tx, ty, sw, sh)
            x2, y2 = _line_box_intersection(tx, ty, sx, sy, tw, th)

            dx = tx - sx
            dy = ty - sy
            length = math.hypot(dx, dy) or 1.0
            nx = -dy / length
            ny = dx / length
            lane_offset = _edge_lane_offset(source_name, rel.target, bundle_totals, bundle_seen)
            x1 += nx * lane_offset
            y1 += ny * lane_offset
            x2 += nx * lane_offset
            y2 += ny * lane_offset

            lines.append(
                f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                'stroke="#4b5563" stroke-width="1.8" marker-end="url(#arrow)"/>'
            )

            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            label = rel.name + (f" {rel.multiplicity}" if rel.multiplicity else "")
            label_dy = (lane_offset / 18.0) * 14.0
            ly = my + label_dy
            label_w = max(96, 8 * len(label) + 16)
            lines.append(
                f'<rect x="{mx - label_w / 2:.2f}" y="{ly - 13:.2f}" width="{label_w:.2f}" height="20" rx="6" fill="#ffffff" opacity="0.9"/>'
            )
            lines.append(
                f'<text x="{mx:.2f}" y="{ly + 2:.2f}" text-anchor="middle" '
                'font-family="Arial, sans-serif" font-size="12" fill="#1f2937">'
                f"{html.escape(label)}</text>"
            )

    # Draw nodes.
    for name, node in classes.items():
        cx, cy = tr(pos[name])
        w, h = sizes[name]
        x = cx - w / 2
        y = cy - h / 2

        lines.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w}" height="{h}" rx="10" '
            'fill="#ffffff" stroke="#334155" stroke-width="2"/>'
        )
        lines.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w}" height="34" rx="10" '
            'fill="#0f766e"/>'
        )
        lines.append(
            f'<text x="{cx:.2f}" y="{y + 22:.2f}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="14" fill="#ffffff" font-weight="700">'
            f"{html.escape(name)}</text>"
        )

        text_y = y + 52
        for attr_name, attr_type in node.attributes:
            lines.append(
                f'<text x="{x + 12:.2f}" y="{text_y:.2f}" '
                'font-family="Arial, sans-serif" font-size="12" fill="#1e293b">'
                f"{html.escape(attr_name)}: {html.escape(attr_type)}</text>"
            )
            text_y += 22

    lines.append("</svg>")
    return "\n".join(lines)


def _render_png_with_pillow(
    classes: Dict[str, ClassNode], output_path: Path, title: str = "JJscript Graph"
) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return False

    sizes = _compute_node_sizes(classes)
    pos = _compute_circle_layout(classes)

    min_x = min(pos[name][0] - sizes[name][0] / 2 for name in classes)
    max_x = max(pos[name][0] + sizes[name][0] / 2 for name in classes)
    min_y = min(pos[name][1] - sizes[name][1] / 2 for name in classes)
    max_y = max(pos[name][1] + sizes[name][1] / 2 for name in classes)

    padding = 80
    width = int(max_x - min_x + 2 * padding)
    height = int(max_y - min_y + 2 * padding)

    def tr(point: Tuple[float, float]) -> Tuple[float, float]:
        x, y = point
        return x - min_x + padding, y - min_y + padding

    img = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("Arial.ttf", 22)
        font_header = ImageFont.truetype("Arial.ttf", 14)
        font_body = ImageFont.truetype("Arial.ttf", 12)
    except Exception:
        font_title = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.text((24, 12), title, fill="#0f172a", font=font_title)

    bundle_totals: Dict[Tuple[str, str], int] = {}
    for source_name, source in classes.items():
        for rel in source.relations:
            if rel.target not in classes:
                continue
            key = _bundle_key(source_name, rel.target)
            bundle_totals[key] = bundle_totals.get(key, 0) + 1
    bundle_seen: Dict[Tuple[str, str], int] = {}

    # Edges.
    for source_name, source in classes.items():
        sx, sy = tr(pos[source_name])
        sw, sh = sizes[source_name]

        for rel in source.relations:
            if rel.target not in classes:
                continue
            tx, ty = tr(pos[rel.target])
            tw, th = sizes[rel.target]

            x1, y1 = _line_box_intersection(sx, sy, tx, ty, sw, sh)
            x2, y2 = _line_box_intersection(tx, ty, sx, sy, tw, th)

            dx = tx - sx
            dy = ty - sy
            length = math.hypot(dx, dy) or 1.0
            nx = -dy / length
            ny = dx / length
            lane_offset = _edge_lane_offset(source_name, rel.target, bundle_totals, bundle_seen)
            x1 += nx * lane_offset
            y1 += ny * lane_offset
            x2 += nx * lane_offset
            y2 += ny * lane_offset

            draw.line((x1, y1, x2, y2), fill="#4b5563", width=2)

            # Arrow head.
            angle = math.atan2(y2 - y1, x2 - x1)
            ah = 10
            p1 = (x2, y2)
            p2 = (x2 - ah * math.cos(angle - math.pi / 8), y2 - ah * math.sin(angle - math.pi / 8))
            p3 = (x2 - ah * math.cos(angle + math.pi / 8), y2 - ah * math.sin(angle + math.pi / 8))
            draw.polygon([p1, p2, p3], fill="#4b5563")

            label = rel.name + (f" {rel.multiplicity}" if rel.multiplicity else "")
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            label_dy = (lane_offset / 18.0) * 14.0
            ly = my + label_dy
            tw_label = draw.textlength(label, font=font_body)
            rect = [mx - tw_label / 2 - 6, ly - 10, mx + tw_label / 2 + 6, ly + 8]
            draw.rounded_rectangle(rect, radius=6, fill="#ffffff", outline=None)
            draw.text((mx - tw_label / 2, ly - 8), label, fill="#1f2937", font=font_body)

    # Nodes.
    for name, node in classes.items():
        cx, cy = tr(pos[name])
        w, h = sizes[name]
        x = cx - w / 2
        y = cy - h / 2

        draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill="#ffffff", outline="#334155", width=2)
        draw.rounded_rectangle((x, y, x + w, y + 34), radius=10, fill="#0f766e", outline=None)

        title_w = draw.textlength(name, font=font_header)
        draw.text((cx - title_w / 2, y + 10), name, fill="#ffffff", font=font_header)

        ty = y + 52
        for attr_name, attr_type in node.attributes:
            draw.text((x + 12, ty), f"{attr_name}: {attr_type}", fill="#1e293b", font=font_body)
            ty += 22

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return True


def convert_jjscript_to_image(
    jjscript: str,
    output_path: str,
    title: str = "JJscript Graph",
) -> str:
    """Parse JJscript and save an image (SVG always, PNG when optional deps are available)."""
    classes = parse_jjscript(jjscript)
    out = Path(output_path)
    suffix = out.suffix.lower()

    if suffix not in {".svg", ".png"}:
        raise ValueError("output_path must end with .svg or .png")

    svg = build_svg(classes, title=title)

    if suffix == ".svg":
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg, encoding="utf-8")
        return str(out)

    # Try direct PNG render through Pillow first.
    if _render_png_with_pillow(classes, out, title=title):
        return str(out)

    # Fallback through cairosvg from generated SVG.
    try:
        import cairosvg  # type: ignore

        out.parent.mkdir(parents=True, exist_ok=True)
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(out))
        return str(out)
    except Exception as exc:
        fallback = out.with_suffix(".svg")
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_text(svg, encoding="utf-8")
        raise RuntimeError(
            "PNG export requires Pillow or cairosvg. "
            f"Wrote SVG fallback to: {fallback}"
        ) from exc


def _read_input_text(path: Optional[str], inline_text: Optional[str]) -> str:
    if inline_text is not None:
        return inline_text
    if path is None:
        raise ValueError("Provide --input-file or --text")
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    return p.read_text(encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Convert JJscript to graph image (SVG/PNG).")
    parser.add_argument("--input-file", "-i", help="Path to JJscript text file")
    parser.add_argument("--text", help="Inline JJscript text")
    parser.add_argument("--output", "-o", required=True, help="Output image path (.svg or .png)")
    parser.add_argument("--title", default="JJscript Graph", help="Image title")

    args = parser.parse_args(argv)

    try:
        source_text = _read_input_text(args.input_file, args.text)
        result = convert_jjscript_to_image(source_text, args.output, title=args.title)
        print(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
