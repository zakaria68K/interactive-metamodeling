#!/usr/bin/env python3
"""
Self-contained JJscript -> graph image converter.

Supported JJscript subset:

    # Metamodel (M2)
    create class State
    create attribute name in State type String
    create reference transitions in State type Transition [*]

    # Instance model (M1)
    create object State s1
    set name of s1 to "Idle"
    set transitions of s1 to t1

Rules:
- "create class" / "create abstract class" / "create class X extends Y" define classes.
- "create attribute" / "create reference" / "create containment" define structure.
- "create object <ClassName> <instanceName>" defines an instance.
- "set <attr> of <instance> to <value>" sets an attribute value or reference link.
- "add <value> to <ref> of <instance>" adds a reference link (multi-valued).
- "end:" is optional and ignored.
- # and // comments are stripped.

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


@dataclass
class InstanceNode:
    name: str
    class_name: str
    attributes: List[Tuple[str, str]] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)


# ── regexes ───────────────────────────────────────────────────────────────────

CLASS_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
ATTR_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^\n#]+?)\s*$")
REL_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*->\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\[[^\]]+\])?\s*$"
)
CREATE_CLASS_RE = re.compile(
    r"^\s*create\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", re.IGNORECASE
)
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
CREATE_OBJECT_RE = re.compile(
    r"^\s*create\s+object\s+([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$",
    re.IGNORECASE,
)
SET_VALUE_RE = re.compile(
    r"^\s*set\s+([A-Za-z_][A-Za-z0-9_]*)\s+of\s+([A-Za-z_][A-Za-z0-9_]*)\s+to\s+(.+?)\s*$",
    re.IGNORECASE,
)
SET_DOT_RE = re.compile(
    r"^\s*set\s+([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$",
    re.IGNORECASE,
)
ADD_TO_RE = re.compile(
    r"^\s*add\s+([A-Za-z_][A-Za-z0-9_]*)\s+to\s+([A-Za-z_][A-Za-z0-9_]*)\s+of\s+([A-Za-z_][A-Za-z0-9_]*)\s*$",
    re.IGNORECASE,
)


def _strip_comment(line: str) -> str:
    line = line.split("//")[0]
    idx = line.find("#")
    return line if idx < 0 else line[:idx]


# ── parser ────────────────────────────────────────────────────────────────────

def parse_jjscript(
    text: str,
) -> Tuple[Dict[str, ClassNode], Dict[str, InstanceNode]]:
    """Parse JJscript text into (classes, instances)."""
    classes: Dict[str, ClassNode] = {}
    instances: Dict[str, InstanceNode] = {}
    current: Optional[ClassNode] = None
    current_instance: Optional[InstanceNode] = None

    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).strip()
        if not line:
            continue

        if line.lower() == "end:":
            current = None
            current_instance = None
            continue

        if line.lower() == "create":
            continue

        # ── instance: create object ──────────────────────────────────────────
        m = CREATE_OBJECT_RE.match(line)
        if m:
            class_name, inst_name = m.groups()
            inst = InstanceNode(name=inst_name, class_name=class_name)
            instances[inst_name] = inst
            current_instance = inst
            current = None
            continue

        # ── instance: set attr/ref  (of syntax) ─────────────────────────────
        m = SET_VALUE_RE.match(line)
        if m:
            attr, inst_name, value = m.groups()
            inst = instances.get(inst_name)
            if inst:
                value_clean = value.strip().strip('"').strip("'")
                # Treat as a reference only when:
                # - the value (unquoted) resolves to a known instance, AND
                # - the original value was NOT quoted (quoted values are always literals)
                originally_quoted = value.strip().startswith(("'", '"'))
                if not originally_quoted and value_clean in instances:
                    inst.relations.append(Relation(name=attr, target=value_clean))
                else:
                    inst.attributes.append((attr, value_clean))
            continue

        # ── instance: set inst.attr = value  (dot syntax) ───────────────────
        m = SET_DOT_RE.match(line)
        if m:
            inst_name, attr, value = m.groups()
            inst = instances.get(inst_name)
            if inst:
                value_clean = value.strip().strip('"').strip("'")
                originally_quoted = value.strip().startswith(("'", '"'))
                if not originally_quoted and value_clean in instances:
                    inst.relations.append(Relation(name=attr, target=value_clean))
                else:
                    inst.attributes.append((attr, value_clean))
            continue

        # ── instance: add value to ref of inst ──────────────────────────────
        m = ADD_TO_RE.match(line)
        if m:
            value, ref_name, inst_name = m.groups()
            inst = instances.get(inst_name)
            if inst:
                if value in instances:
                    inst.relations.append(Relation(name=ref_name, target=value))
            continue

        # ── metamodel: create class (extends) ───────────────────────────────
        m = CREATE_CLASS_EXTENDS_RE.match(line) or CREATE_CLASS_RE.match(line)
        if m:
            class_name = m.group(1)
            current = classes.setdefault(class_name, ClassNode(name=class_name))
            if m.lastindex and m.lastindex >= 2 and m.group(2):
                parent = m.group(2)
                classes.setdefault(parent, ClassNode(name=parent))
                current.relations.append(Relation(name="extends", target=parent))
            current_instance = None
            continue

        m = CREATE_ABSTRACT_CLASS_RE.match(line)
        if m:
            class_name = m.group(1)
            current = classes.setdefault(class_name, ClassNode(name=class_name))
            if m.group(2):
                parent = m.group(2)
                classes.setdefault(parent, ClassNode(name=parent))
                current.relations.append(Relation(name="extends", target=parent))
            current_instance = None
            continue

        m = CREATE_ATTR_RE.match(line)
        if m:
            attr_name, owner_name, attr_type = m.groups()
            owner = classes.setdefault(owner_name, ClassNode(name=owner_name))
            owner.attributes.append((attr_name, attr_type.strip()))
            current = owner
            current_instance = None
            continue

        m = CREATE_REF_RE.match(line)
        if m:
            rel_name, owner_name, target_name, mult = m.groups()
            owner = classes.setdefault(owner_name, ClassNode(name=owner_name))
            owner.relations.append(
                Relation(name=rel_name, target=target_name, multiplicity=(mult or ""))
            )
            classes.setdefault(target_name, ClassNode(name=target_name))
            current = owner
            current_instance = None
            continue

        m = CREATE_INSTANCE_RE.match(line)
        if m:
            inst_name, owner_name = m.groups()
            current = classes.setdefault(owner_name, ClassNode(name=owner_name))
            current_instance = None
            continue

        m = CLASS_RE.match(line)
        if m:
            class_name = m.group(1)
            current = classes.setdefault(class_name, ClassNode(name=class_name))
            current_instance = None
            continue

        if current is None and current_instance is None:
            continue

        m = REL_RE.match(line)
        if m and current:
            rel_name, target, mult = m.groups()
            current.relations.append(
                Relation(name=rel_name, target=target, multiplicity=(mult or ""))
            )
            classes.setdefault(target, ClassNode(name=target))
            continue

        m = ATTR_RE.match(line)
        if m and current:
            attr_name, attr_type = m.groups()
            current.attributes.append((attr_name, attr_type.strip()))
            continue

    return classes, instances


# ── sizing & layout ───────────────────────────────────────────────────────────

def _compute_node_sizes(
    classes: Dict[str, ClassNode],
    instances: Dict[str, InstanceNode],
) -> Dict[str, Tuple[int, int]]:
    sizes: Dict[str, Tuple[int, int]] = {}
    for name, node in classes.items():
        max_line = len(name)
        for a, t in node.attributes:
            max_line = max(max_line, len(f"{a}: {t}"))
        width = max(180, 12 * max_line + 36)
        height = 48 + max(0, len(node.attributes)) * 24
        sizes[name] = (width, height)
    for name, inst in instances.items():
        label = f"{name} : {inst.class_name}"
        max_line = len(label)
        for a, v in inst.attributes:
            max_line = max(max_line, len(f"{a} = {v}"))
        width = max(180, 12 * max_line + 36)
        height = 48 + max(0, len(inst.attributes)) * 24
        sizes[name] = (width, height)
    return sizes


def _compute_layout(
    classes: Dict[str, ClassNode],
    instances: Dict[str, InstanceNode],
) -> Dict[str, Tuple[float, float]]:
    """
    Two-ring layout:
      - metamodel classes on the outer ring
      - instances on the inner ring
    Falls back to a single ring when one group is empty.
    """
    class_names = sorted(classes.keys())
    inst_names = sorted(instances.keys())
    positions: Dict[str, Tuple[float, float]] = {}

    def place_ring(names: List[str], radius: float, offset_x: float = 0.0) -> None:
        n = len(names)
        if n == 0:
            return
        if n == 1:
            positions[names[0]] = (offset_x, 0.0)
            return
        for i, name in enumerate(names):
            angle = (2.0 * math.pi * i / n) - (math.pi / 2.0)
            positions[name] = (offset_x + radius * math.cos(angle), radius * math.sin(angle))

    n_c, n_i = len(class_names), len(inst_names)

    if n_c == 0 and n_i == 0:
        return {}
    elif n_c == 0:
        place_ring(inst_names, max(200.0, 85.0 * n_i))
    elif n_i == 0:
        place_ring(class_names, max(220.0, 90.0 * n_c))
    else:
        outer_r = max(300.0, 100.0 * n_c)
        # inner ring must not exceed 55% of outer so nodes don't overlap
        inner_r = min(max(130.0, 60.0 * n_i), outer_r * 0.52)
        place_ring(class_names, outer_r)
        place_ring(inst_names, inner_r)

    return positions


def _bundle_key(source: str, target: str) -> Tuple[str, str]:
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
    return (idx - (total - 1) / 2.0) * lane_gap


def _line_box_intersection(
    cx: float, cy: float, tx: float, ty: float, w: float, h: float
) -> Tuple[float, float]:
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    scale_x = abs(w / 2.0 / dx) if dx != 0 else float("inf")
    scale_y = abs(h / 2.0 / dy) if dy != 0 else float("inf")
    return cx + dx * min(scale_x, scale_y), cy + dy * min(scale_x, scale_y)


# ── SVG builder ───────────────────────────────────────────────────────────────

def build_svg(
    classes: Dict[str, ClassNode],
    instances: Dict[str, InstanceNode],
    title: str = "JJscript Graph",
) -> str:
    all_names = set(classes) | set(instances)
    if not all_names:
        return "<svg xmlns='http://www.w3.org/2000/svg'><text x='10' y='20'>Empty</text></svg>"

    sizes = _compute_node_sizes(classes, instances)
    pos = _compute_layout(classes, instances)

    min_x = min(pos[n][0] - sizes[n][0] / 2 for n in all_names)
    max_x = max(pos[n][0] + sizes[n][0] / 2 for n in all_names)
    min_y = min(pos[n][1] - sizes[n][1] / 2 for n in all_names)
    max_y = max(pos[n][1] + sizes[n][1] / 2 for n in all_names)

    padding = 80
    width = int(max_x - min_x + 2 * padding)
    height = int(max_y - min_y + 2 * padding)

    def tr(pt: Tuple[float, float]) -> Tuple[float, float]:
        return pt[0] - min_x + padding, pt[1] - min_y + padding

    all_relations: List[Tuple[str, str, Relation]] = []
    for src, node in classes.items():
        for rel in node.relations:
            if rel.target in all_names:
                all_relations.append((src, rel.target, rel))
    for src, inst in instances.items():
        for rel in inst.relations:
            if rel.target in all_names:
                all_relations.append((src, rel.target, rel))

    bundle_totals: Dict[Tuple[str, str], int] = {}
    for src, tgt, _ in all_relations:
        key = _bundle_key(src, tgt)
        bundle_totals[key] = bundle_totals.get(key, 0) + 1
    bundle_seen: Dict[Tuple[str, str], int] = {}

    out: List[str] = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'style="max-width:100%;height:auto;">'
    )
    out.append("<defs>")
    out.append(
        '<marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" '
        'orient="auto" markerUnits="strokeWidth">'
    )
    out.append('<path d="M0,0 L10,4 L0,8 z" fill="#4b5563"/>')
    out.append("</marker>")
    out.append("</defs>")
    out.append('<rect x="0" y="0" width="100%" height="100%" fill="#f8fafc"/>')
    out.append(
        f'<text x="24" y="34" font-family="Arial, sans-serif" font-size="22" '
        f'fill="#0f172a" font-weight="700">{html.escape(title)}</text>'
    )

    for src, tgt, rel in all_relations:
        sx, sy = tr(pos[src]); sw, sh = sizes[src]
        tx2, ty2 = tr(pos[tgt]); tw, th = sizes[tgt]
        x1, y1 = _line_box_intersection(sx, sy, tx2, ty2, sw, sh)
        x2, y2 = _line_box_intersection(tx2, ty2, sx, sy, tw, th)
        dx, dy = tx2 - sx, ty2 - sy
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        lo = _edge_lane_offset(src, tgt, bundle_totals, bundle_seen)
        x1 += nx * lo; y1 += ny * lo; x2 += nx * lo; y2 += ny * lo
        dash = ' stroke-dasharray="6,3"' if src in instances else ""
        out.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="#4b5563" stroke-width="1.8" marker-end="url(#arrow)"{dash}/>'
        )
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        label = rel.name + (f" {rel.multiplicity}" if rel.multiplicity else "")
        ly = my + (lo / 18.0) * 14.0
        lw = max(96, 8 * len(label) + 16)
        out.append(
            f'<rect x="{mx - lw/2:.2f}" y="{ly - 13:.2f}" width="{lw:.2f}" height="20" '
            'rx="6" fill="#ffffff" opacity="0.9"/>'
        )
        out.append(
            f'<text x="{mx:.2f}" y="{ly + 2:.2f}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="12" fill="#1f2937">'
            f"{html.escape(label)}</text>"
        )

    for name, node in classes.items():
        cx, cy = tr(pos[name]); w, h = sizes[name]
        x, y = cx - w / 2, cy - h / 2
        out.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w}" height="{h}" rx="10" '
            'fill="#ffffff" stroke="#334155" stroke-width="2"/>'
        )
        out.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w}" height="34" rx="10" fill="#0f766e"/>'
        )
        out.append(
            f'<text x="{cx:.2f}" y="{y + 22:.2f}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="14" fill="#ffffff" font-weight="700">'
            f"{html.escape(name)}</text>"
        )
        ty = y + 52
        for a, t in node.attributes:
            out.append(
                f'<text x="{x + 12:.2f}" y="{ty:.2f}" '
                'font-family="Arial, sans-serif" font-size="12" fill="#1e293b">'
                f"{html.escape(a)}: {html.escape(t)}</text>"
            )
            ty += 22

    for name, inst in instances.items():
        cx, cy = tr(pos[name]); w, h = sizes[name]
        x, y = cx - w / 2, cy - h / 2
        out.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w}" height="{h}" rx="10" '
            'fill="#f0fdfa" stroke="#334155" stroke-width="2" stroke-dasharray="6,3"/>'
        )
        out.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w}" height="34" rx="10" fill="#0e9488"/>'
        )
        label = f"{name} : {inst.class_name}"
        out.append(
            f'<text x="{cx:.2f}" y="{y + 22:.2f}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="13" fill="#ffffff" font-style="italic">'
            f"{html.escape(label)}</text>"
        )
        ty = y + 52
        for a, v in inst.attributes:
            out.append(
                f'<text x="{x + 12:.2f}" y="{ty:.2f}" '
                'font-family="Arial, sans-serif" font-size="12" fill="#1e293b">'
                f"{html.escape(a)} = {html.escape(v)}</text>"
            )
            ty += 22

    out.append("</svg>")
    return "\n".join(out)


# ── PNG renderer ──────────────────────────────────────────────────────────────

def _render_png_with_pillow(
    classes: Dict[str, ClassNode],
    instances: Dict[str, InstanceNode],
    output_path: Path,
    title: str = "JJscript Graph",
) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return False

    all_names = set(classes) | set(instances)
    sizes = _compute_node_sizes(classes, instances)
    pos = _compute_layout(classes, instances)

    min_x = min(pos[n][0] - sizes[n][0] / 2 for n in all_names)
    max_x = max(pos[n][0] + sizes[n][0] / 2 for n in all_names)
    min_y = min(pos[n][1] - sizes[n][1] / 2 for n in all_names)
    max_y = max(pos[n][1] + sizes[n][1] / 2 for n in all_names)

    padding = 80
    width = int(max_x - min_x + 2 * padding)
    height = int(max_y - min_y + 2 * padding)

    def tr(pt: Tuple[float, float]) -> Tuple[float, float]:
        return pt[0] - min_x + padding, pt[1] - min_y + padding

    img = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("Arial.ttf", 22)
        font_header = ImageFont.truetype("Arial.ttf", 14)
        font_body = ImageFont.truetype("Arial.ttf", 12)
    except Exception:
        font_title = font_header = font_body = ImageFont.load_default()

    draw.text((24, 12), title, fill="#0f172a", font=font_title)

    all_relations: List[Tuple[str, str, Relation]] = []
    for src, node in classes.items():
        for rel in node.relations:
            if rel.target in all_names:
                all_relations.append((src, rel.target, rel))
    for src, inst in instances.items():
        for rel in inst.relations:
            if rel.target in all_names:
                all_relations.append((src, rel.target, rel))

    bundle_totals: Dict[Tuple[str, str], int] = {}
    for src, tgt, _ in all_relations:
        key = _bundle_key(src, tgt)
        bundle_totals[key] = bundle_totals.get(key, 0) + 1
    bundle_seen: Dict[Tuple[str, str], int] = {}

    for src, tgt, rel in all_relations:
        sx, sy = tr(pos[src]); sw, sh = sizes[src]
        tx2, ty2 = tr(pos[tgt]); tw, th = sizes[tgt]
        x1, y1 = _line_box_intersection(sx, sy, tx2, ty2, sw, sh)
        x2, y2 = _line_box_intersection(tx2, ty2, sx, sy, tw, th)
        dx, dy = tx2 - sx, ty2 - sy
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        lo = _edge_lane_offset(src, tgt, bundle_totals, bundle_seen)
        x1 += nx * lo; y1 += ny * lo; x2 += nx * lo; y2 += ny * lo
        draw.line((x1, y1, x2, y2), fill="#4b5563", width=2)
        angle = math.atan2(y2 - y1, x2 - x1)
        ah = 10
        draw.polygon([
            (x2, y2),
            (x2 - ah * math.cos(angle - math.pi/8), y2 - ah * math.sin(angle - math.pi/8)),
            (x2 - ah * math.cos(angle + math.pi/8), y2 - ah * math.sin(angle + math.pi/8)),
        ], fill="#4b5563")
        label = rel.name + (f" {rel.multiplicity}" if rel.multiplicity else "")
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ly = my + (lo / 18.0) * 14.0
        lw2 = draw.textlength(label, font=font_body)
        draw.rounded_rectangle(
            [mx - lw2/2 - 6, ly - 10, mx + lw2/2 + 6, ly + 8],
            radius=6, fill="#ffffff"
        )
        draw.text((mx - lw2/2, ly - 8), label, fill="#1f2937", font=font_body)

    for name, node in classes.items():
        cx, cy = tr(pos[name]); w, h = sizes[name]
        x, y = cx - w/2, cy - h/2
        draw.rounded_rectangle((x, y, x+w, y+h), radius=10, fill="#ffffff", outline="#334155", width=2)
        draw.rounded_rectangle((x, y, x+w, y+34), radius=10, fill="#0f766e", outline=None)
        nw = draw.textlength(name, font=font_header)
        draw.text((cx - nw/2, y+10), name, fill="#ffffff", font=font_header)
        ty = y + 52
        for a, t in node.attributes:
            draw.text((x+12, ty), f"{a}: {t}", fill="#1e293b", font=font_body)
            ty += 22

    for name, inst in instances.items():
        cx, cy = tr(pos[name]); w, h = sizes[name]
        x, y = cx - w/2, cy - h/2
        draw.rounded_rectangle((x, y, x+w, y+h), radius=10, fill="#f0fdfa", outline="#334155", width=2)
        draw.rounded_rectangle((x, y, x+w, y+34), radius=10, fill="#0e9488", outline=None)
        label = f"{name} : {inst.class_name}"
        lw2 = draw.textlength(label, font=font_body)
        draw.text((cx - lw2/2, y+10), label, fill="#ffffff", font=font_body)
        ty = y + 52
        for a, v in inst.attributes:
            draw.text((x+12, ty), f"{a} = {v}", fill="#1e293b", font=font_body)
            ty += 22

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return True


# ── public API ────────────────────────────────────────────────────────────────

def convert_jjscript_to_image(
    jjscript: str,
    output_path: str,
    title: str = "JJscript Graph",
) -> str:
    classes, instances = parse_jjscript(jjscript)
    if not classes and not instances:
        raise ValueError("No classes or instances parsed from JJscript input.")

    out = Path(output_path)
    suffix = out.suffix.lower()
    if suffix not in {".svg", ".png"}:
        raise ValueError("output_path must end with .svg or .png")

    svg = build_svg(classes, instances, title=title)

    if suffix == ".svg":
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg, encoding="utf-8")
        return str(out)

    if _render_png_with_pillow(classes, instances, out, title=title):
        return str(out)

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
            f"PNG export requires Pillow or cairosvg. Wrote SVG fallback to: {fallback}"
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
    parser.add_argument("--input-file", "-i")
    parser.add_argument("--text")
    parser.add_argument("--output", "-o", required=True)
    parser.add_argument("--title", default="JJscript Graph")
    args = parser.parse_args(argv)
    try:
        source_text = _read_input_text(args.input_file, args.text)
        print(convert_jjscript_to_image(source_text, args.output, title=args.title))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())