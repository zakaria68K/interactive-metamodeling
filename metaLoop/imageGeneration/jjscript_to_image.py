#!/usr/bin/env python3
"""
Self-contained JJscript -> graph image converter.

Relation kinds rendered:
  inheritance  : hollow triangle arrowhead (UML generalization)
  containment  : filled diamond at source  (UML composition)
  reference    : open arrowhead            (UML association)
  instance link: dashed open arrowhead

Abstract classes rendered with italic name and dashed border.
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


# ── data model ────────────────────────────────────────────────────────────────

@dataclass
class Relation:
    name: str
    target: str
    multiplicity: str = ""
    kind: str = "reference"   # "reference" | "containment" | "inheritance" | "instance"


@dataclass
class ClassNode:
    name: str
    is_abstract: bool = False
    attributes: List[Tuple[str, str]] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)


@dataclass
class InstanceNode:
    name: str
    class_name: str
    attributes: List[Tuple[str, str]] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)


# ── regexes ───────────────────────────────────────────────────────────────────

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
# standalone: "ChildClass extends ParentClass"
STANDALONE_EXTENDS_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+extends\s+([A-Za-z_][A-Za-z0-9_]*)\s*$",
    re.IGNORECASE,
)
CREATE_ATTR_RE = re.compile(
    r"^\s*create\s+attribute\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([A-Za-z_][A-Za-z0-9_]*)\s+type\s+([^\n#\[]+?)\s*(?:\[[^\]]*\])?\s*$",
    re.IGNORECASE,
)
CREATE_REF_RE = re.compile(
    r"^\s*create\s+(reference|containment)\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([A-Za-z_][A-Za-z0-9_]*)\s+type\s+([A-Za-z_][A-Za-z0-9_]*)\s*(\[[^\]]+\])?\s*$",
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

def parse_jjscript(text: str) -> Tuple[Dict[str, ClassNode], Dict[str, InstanceNode]]:
    classes: Dict[str, ClassNode] = {}
    instances: Dict[str, InstanceNode] = {}

    for raw_line in text.splitlines():
        line = _strip_comment(raw_line).strip()
        if not line or line.lower() in {"end:", "create"}:
            continue

        # ── create object (instance) ─────────────────────────────────────────
        m = CREATE_OBJECT_RE.match(line)
        if m:
            class_name, inst_name = m.groups()
            instances[inst_name] = InstanceNode(name=inst_name, class_name=class_name)
            continue

        # ── set / add (instance links) ───────────────────────────────────────
        m = SET_VALUE_RE.match(line)
        if m:
            attr, inst_name, value = m.groups()
            inst = instances.get(inst_name)
            if inst:
                value_clean = value.strip().strip('"').strip("'")
                originally_quoted = value.strip().startswith(("'", '"'))
                if not originally_quoted and value_clean in instances:
                    inst.relations.append(Relation(name=attr, target=value_clean, kind="instance"))
                else:
                    inst.attributes.append((attr, value_clean))
            continue

        m = SET_DOT_RE.match(line)
        if m:
            inst_name, attr, value = m.groups()
            inst = instances.get(inst_name)
            if inst:
                value_clean = value.strip().strip('"').strip("'")
                originally_quoted = value.strip().startswith(("'", '"'))
                if not originally_quoted and value_clean in instances:
                    inst.relations.append(Relation(name=attr, target=value_clean, kind="instance"))
                else:
                    inst.attributes.append((attr, value_clean))
            continue

        m = ADD_TO_RE.match(line)
        if m:
            value, ref_name, inst_name = m.groups()
            inst = instances.get(inst_name)
            if inst and value in instances:
                inst.relations.append(Relation(name=ref_name, target=value, kind="instance"))
            continue

        # ── create abstract class [extends] ──────────────────────────────────
        m = CREATE_ABSTRACT_CLASS_RE.match(line)
        if m:
            class_name, parent = m.group(1), m.group(2)
            node = classes.setdefault(class_name, ClassNode(name=class_name))
            node.is_abstract = True
            if parent:
                classes.setdefault(parent, ClassNode(name=parent))
                node.relations.append(Relation(name="", target=parent, kind="inheritance"))
            continue

        # ── create class [extends] ────────────────────────────────────────────
        m = CREATE_CLASS_EXTENDS_RE.match(line)
        if m:
            class_name, parent = m.groups()
            node = classes.setdefault(class_name, ClassNode(name=class_name))
            classes.setdefault(parent, ClassNode(name=parent))
            node.relations.append(Relation(name="", target=parent, kind="inheritance"))
            continue

        m = CREATE_CLASS_RE.match(line)
        if m:
            classes.setdefault(m.group(1), ClassNode(name=m.group(1)))
            continue

        # ── standalone: Child extends Parent ─────────────────────────────────
        m = STANDALONE_EXTENDS_RE.match(line)
        if m:
            child, parent = m.groups()
            node = classes.setdefault(child, ClassNode(name=child))
            classes.setdefault(parent, ClassNode(name=parent))
            # avoid duplicate if already added via create class X extends Y
            already = any(r.kind == "inheritance" and r.target == parent for r in node.relations)
            if not already:
                node.relations.append(Relation(name="", target=parent, kind="inheritance"))
            continue

        # ── create attribute ──────────────────────────────────────────────────
        m = CREATE_ATTR_RE.match(line)
        if m:
            attr_name, owner_name, attr_type = m.groups()
            owner = classes.setdefault(owner_name, ClassNode(name=owner_name))
            owner.attributes.append((attr_name, attr_type.strip()))
            continue

        # ── create reference / containment ────────────────────────────────────
        m = CREATE_REF_RE.match(line)
        if m:
            rel_kind, rel_name, owner_name, target_name, mult = m.groups()
            owner = classes.setdefault(owner_name, ClassNode(name=owner_name))
            owner.relations.append(Relation(
                name=rel_name,
                target=target_name,
                multiplicity=(mult or ""),
                kind=rel_kind.lower(),   # "reference" or "containment"
            ))
            classes.setdefault(target_name, ClassNode(name=target_name))
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
        width  = max(180, 12 * max_line + 36)
        height = 48 + max(0, len(node.attributes)) * 24
        sizes[name] = (width, height)
    for name, inst in instances.items():
        label = f"{name} : {inst.class_name}"
        max_line = len(label)
        for a, v in inst.attributes:
            max_line = max(max_line, len(f"{a} = {v}"))
        width  = max(180, 12 * max_line + 36)
        height = 48 + max(0, len(inst.attributes)) * 24
        sizes[name] = (width, height)
    return sizes


def _compute_layout(
    classes: Dict[str, ClassNode],
    instances: Dict[str, InstanceNode],
) -> Dict[str, Tuple[float, float]]:
    class_names = sorted(classes.keys())
    inst_names  = sorted(instances.keys())
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
        place_ring(inst_names, max(200.0, 80.0 * n_i))
    elif n_i == 0:
        place_ring(class_names, max(200.0, 80.0 * n_c))
    else:
        outer_r = max(250.0, 80.0 * n_c)
        inner_r = min(max(150.0, 60.0 * n_i), outer_r * 0.50)
        place_ring(class_names, outer_r)
        place_ring(inst_names, inner_r)
    return positions


def _bundle_key(source: str, target: str) -> Tuple[str, str]:
    return (source, target) if source <= target else (target, source)


def _edge_lane_offset(
    source_name: str, target_name: str,
    bundle_totals: Dict, bundle_seen: Dict,
    lane_gap: float = 18.0,
) -> float:
    key = _bundle_key(source_name, target_name)
    idx = bundle_seen.get(key, 0)
    bundle_seen[key] = idx + 1
    total = bundle_totals.get(key, 1)
    return (idx - (total - 1) / 2.0) * lane_gap


def _line_box_intersection(cx, cy, tx, ty, w, h) -> Tuple[float, float]:
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
    highlight_classes: set | None = None,
) -> str:
    all_names = set(classes) | set(instances)
    if not all_names:
        return "<svg xmlns='http://www.w3.org/2000/svg'><text x='10' y='20'>Empty</text></svg>"

    sizes = _compute_node_sizes(classes, instances)
    pos   = _compute_layout(classes, instances)

    min_x = min(pos[n][0] - sizes[n][0] / 2 for n in all_names)
    max_x = max(pos[n][0] + sizes[n][0] / 2 for n in all_names)
    min_y = min(pos[n][1] - sizes[n][1] / 2 for n in all_names)
    max_y = max(pos[n][1] + sizes[n][1] / 2 for n in all_names)

    padding = 80
    W = int(max_x - min_x + 2 * padding)
    H = int(max_y - min_y + 2 * padding)

    def tr(pt):
        return pt[0] - min_x + padding, pt[1] - min_y + padding

    # ── collect edges ─────────────────────────────────────────────────────────
    all_relations: List[Tuple[str, str, Relation]] = []
    for src, node in classes.items():
        for rel in node.relations:
            if rel.target in all_names:
                all_relations.append((src, rel.target, rel))
    for src, inst in instances.items():
        for rel in inst.relations:
            if rel.target in all_names:
                all_relations.append((src, rel.target, rel))

    bundle_totals: Dict = {}
    for src, tgt, _ in all_relations:
        key = _bundle_key(src, tgt)
        bundle_totals[key] = bundle_totals.get(key, 0) + 1
    bundle_seen: Dict = {}

    out: List[str] = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        'width="100%" height="100%" preserveAspectRatio="xMidYMid meet" '
        'style="max-width:100%;height:auto;display:block;">'
    )

    out.append("<defs></defs>")
    out.append('<rect x="0" y="0" width="100%" height="100%" fill="#f8fafc"/>')
    out.append(
        f'<text x="24" y="34" font-family="Arial, sans-serif" font-size="22" '
        f'fill="#0f172a" font-weight="700">{html.escape(title)}</text>'
    )

    # ── draw edges ────────────────────────────────────────────────────────────
    for src, tgt, rel in all_relations:
        sx, sy = tr(pos[src]); sw, sh = sizes[src]
        tx2, ty2 = tr(pos[tgt]); tw, th = sizes[tgt]
        x1, y1 = _line_box_intersection(sx, sy, tx2, ty2, sw, sh)
        x2, y2 = _line_box_intersection(tx2, ty2, sx, sy, tw, th)
        dx, dy = tx2 - sx, ty2 - sy
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        lo = _edge_lane_offset(src, tgt, bundle_totals, bundle_seen)
        x1 += nx * lo; y1 += ny * lo
        x2 += nx * lo; y2 += ny * lo

        kind = rel.kind
        ux, uy = dx / length, dy / length  # unit vector source→target

        if kind == "inheritance":
            color = "#7c3aed"
            # line stops short of target to leave room for hollow triangle
            TRI = 14
            lx2 = x2 - ux * TRI; ly2_e = y2 - uy * TRI
            out.append(
                f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{lx2:.2f}" y2="{ly2_e:.2f}" '
                f'stroke="{color}" stroke-width="1.8"/>'
            )
            # hollow triangle pointing at (x2,y2)
            perp_x, perp_y = -uy * TRI * 0.6, ux * TRI * 0.6
            p1x, p1y = x2, y2
            p2x, p2y = lx2 + perp_x, ly2_e + perp_y
            p3x, p3y = lx2 - perp_x, ly2_e - perp_y
            out.append(
                f'<polygon points="{p1x:.2f},{p1y:.2f} {p2x:.2f},{p2y:.2f} {p3x:.2f},{p3y:.2f}" '
                f'fill="#ffffff" stroke="{color}" stroke-width="1.8"/>'
            )

        elif kind == "containment":
                    color = "#1d4ed8"
                    DIA = 10
                    d_back_x, d_back_y = x1, y1
                    d_tip_x  = x1 + ux * DIA * 2;  d_tip_y  = y1 + uy * DIA * 2
                    d_left_x = x1 + ux * DIA - uy * DIA * 0.7
                    d_left_y = y1 + uy * DIA + ux * DIA * 0.7
                    d_right_x = x1 + ux * DIA + uy * DIA * 0.7
                    d_right_y = y1 + uy * DIA - ux * DIA * 0.7
                    # line from diamond tip to target
                    out.append(
                        f'<line x1="{d_tip_x:.2f}" y1="{d_tip_y:.2f}" '
                        f'x2="{x2:.2f}" y2="{y2:.2f}" '
                        f'stroke="{color}" stroke-width="2"/>'
                    )
                    # filled diamond at source (owner/container)
                    out.append(
                        f'<polygon points="{d_back_x:.2f},{d_back_y:.2f} {d_left_x:.2f},{d_left_y:.2f} '
                        f'{d_tip_x:.2f},{d_tip_y:.2f} {d_right_x:.2f},{d_right_y:.2f}" '
                        f'fill="{color}" stroke="{color}" stroke-width="1"/>'
                    )
                    # # open arrowhead at target to clarify direction
                    # ARR = 10
                    # lx2 = x2 - ux * ARR; ly2_e = y2 - uy * ARR
                    # perp_x, perp_y = -uy * ARR * 0.6, ux * ARR * 0.6
                    # out.append(
                    #     f'<polyline points="{lx2 + perp_x:.2f},{ly2_e + perp_y:.2f} {x2:.2f},{y2:.2f} '
                    #     f'{lx2 - perp_x:.2f},{ly2_e - perp_y:.2f}" '
                    #     f'fill="none" stroke="{color}" stroke-width="1.8"/>'
                    # )

        elif kind == "instance":
            color = "#64748b"
            out.append(
                f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="{color}" stroke-width="1.5" stroke-dasharray="6,3"/>'
            )

        else:  # reference — open arrowhead
            color = "#4b5563"
            ARR = 10
            lx2 = x2 - ux * ARR; ly2_e = y2 - uy * ARR
            perp_x, perp_y = -uy * ARR * 0.6, ux * ARR * 0.6
            out.append(
                f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{lx2:.2f}" y2="{ly2_e:.2f}" '
                f'stroke="{color}" stroke-width="1.8"/>'
            )
            out.append(
                f'<polyline points="{lx2 + perp_x:.2f},{ly2_e + perp_y:.2f} {x2:.2f},{y2:.2f} '
                f'{lx2 - perp_x:.2f},{ly2_e - perp_y:.2f}" '
                f'fill="none" stroke="{color}" stroke-width="1.8"/>'
            )

        # edge label: skip for inheritance (no name) and instance links (implicit)
        label = rel.name + (f" {rel.multiplicity}" if rel.multiplicity else "")
        if label.strip() and kind not in {"inheritance", "instance"}:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ly2 = my + (lo / 18.0) * 14.0
            lw  = max(80, 8 * len(label) + 16)
            out.append(
                f'<rect x="{mx - lw/2:.2f}" y="{ly2 - 13:.2f}" width="{lw:.2f}" height="20" '
                f'rx="5" fill="#ffffff" opacity="0.9"/>'
            )
            out.append(
                f'<text x="{mx:.2f}" y="{ly2 + 2:.2f}" text-anchor="middle" '
                f'font-family="Arial, sans-serif" font-size="11" fill="{color}">'
                f"{html.escape(label)}</text>"
            )

    # ── draw class nodes ──────────────────────────────────────────────────────
    for name, node in classes.items():
        cx, cy = tr(pos[name]); w, h = sizes[name]
        x, y = cx - w / 2, cy - h / 2
        highlighted = bool(highlight_classes and name in highlight_classes)
        stroke_color = "#fb923c" if highlighted else "#334155"
        stroke_w     = 3 if highlighted else 2
        header_color = "#6d28d9" if node.is_abstract else "#0f766e"
        border_dash  = ' stroke-dasharray="6,3"' if node.is_abstract else ""

        out.append(f'<g class="class-node" data-name="{html.escape(name)}">')
        out.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w}" height="{h}" rx="10" '
            f'fill="#ffffff" stroke="{stroke_color}" stroke-width="{stroke_w}"{border_dash}/>'
        )
        out.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w}" height="34" rx="10" fill="{header_color}"/>'
        )
        font_style = 'font-style="italic"' if node.is_abstract else 'font-weight="700"'
        out.append(
            f'<text x="{cx:.2f}" y="{y + 22:.2f}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="14" fill="#ffffff" {font_style}>'
            f"{html.escape(name)}</text>"
        )
        ty = y + 52
        for a, t in node.attributes:
            out.append(
                f'<text x="{x + 12:.2f}" y="{ty:.2f}" '
                'font-family="Arial, sans-serif" font-size="12" fill="#1e293b">'
                f"{html.escape(a)}: {html.escape(t)}</text>"
            )
            ty += 24
        out.append("</g>")

    # ── draw instance nodes ───────────────────────────────────────────────────
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
            ty += 24

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
    pos   = _compute_layout(classes, instances)

    min_x = min(pos[n][0] - sizes[n][0] / 2 for n in all_names)
    max_x = max(pos[n][0] + sizes[n][0] / 2 for n in all_names)
    min_y = min(pos[n][1] - sizes[n][1] / 2 for n in all_names)
    max_y = max(pos[n][1] + sizes[n][1] / 2 for n in all_names)

    padding = 80
    W = int(max_x - min_x + 2 * padding)
    H = int(max_y - min_y + 2 * padding)

    def tr(pt):
        return pt[0] - min_x + padding, pt[1] - min_y + padding

    img  = Image.new("RGB", (W, H), "#f8fafc")
    draw = ImageDraw.Draw(img)

    try:
        font_title  = ImageFont.truetype("Arial.ttf", 22)
        font_header = ImageFont.truetype("Arial.ttf", 14)
        font_body   = ImageFont.truetype("Arial.ttf", 12)
    except Exception:
        font_title = font_header = font_body = ImageFont.load_default()

    draw.text((24, 12), title, fill="#0f172a", font=font_title)

    KIND_COLOR = {
        "inheritance": "#7c3aed",
        "containment": "#1d4ed8",
        "reference":   "#4b5563",
        "instance":    "#0e9488",
    }

    all_relations = []
    for src, node in classes.items():
        for rel in node.relations:
            if rel.target in all_names:
                all_relations.append((src, rel.target, rel))
    for src, inst in instances.items():
        for rel in inst.relations:
            if rel.target in all_names:
                all_relations.append((src, rel.target, rel))

    bundle_totals: Dict = {}
    for src, tgt, _ in all_relations:
        key = _bundle_key(src, tgt)
        bundle_totals[key] = bundle_totals.get(key, 0) + 1
    bundle_seen: Dict = {}

    for src, tgt, rel in all_relations:
        sx, sy = tr(pos[src]); sw, sh = sizes[src]
        tx2, ty2 = tr(pos[tgt]); tw, th = sizes[tgt]
        x1, y1 = _line_box_intersection(sx, sy, tx2, ty2, sw, sh)
        x2, y2 = _line_box_intersection(tx2, ty2, sx, sy, tw, th)
        dx, dy = tx2 - sx, ty2 - sy
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        lo = _edge_lane_offset(src, tgt, bundle_totals, bundle_seen)
        x1 += nx * lo; y1 += ny * lo
        x2 += nx * lo; y2 += ny * lo

        color = KIND_COLOR.get(rel.kind, "#4b5563")
        dash = (8, 4) if rel.kind == "instance" else None

        if dash:
            # Pillow doesn't have native dash; draw segmented
            seg_len, gap = dash
            total = math.hypot(x2 - x1, y2 - y1)
            ux, uy = (x2 - x1) / total, (y2 - y1) / total
            t = 0.0
            drawing = True
            while t < total:
                t2 = min(t + (seg_len if drawing else gap), total)
                if drawing:
                    draw.line(
                        (x1 + ux * t, y1 + uy * t, x1 + ux * t2, y1 + uy * t2),
                        fill=color, width=2
                    )
                t = t2
                drawing = not drawing
        else:
            draw.line((x1, y1, x2, y2), fill=color, width=2)

        # arrowhead at target
        angle = math.atan2(y2 - y1, x2 - x1)
        ah = 10
        if rel.kind == "inheritance":
            # hollow triangle
            pts = [
                (x2, y2),
                (x2 - ah * math.cos(angle - math.pi/7), y2 - ah * math.sin(angle - math.pi/7)),
                (x2 - ah * math.cos(angle + math.pi/7), y2 - ah * math.sin(angle + math.pi/7)),
            ]
            draw.polygon(pts, fill="#ffffff", outline=color)
        elif rel.kind == "containment":
            # diamond at source
            pts_d = [
                (x1, y1),
                (x1 - 10 * math.cos(angle - math.pi/6), y1 - 10 * math.sin(angle - math.pi/6)),
                (x1 - 18 * math.cos(angle), y1 - 18 * math.sin(angle)),
                (x1 - 10 * math.cos(angle + math.pi/6), y1 - 10 * math.sin(angle + math.pi/6)),
            ]
            draw.polygon(pts_d, fill=color)
            pts_a = [
                (x2, y2),
                (x2 - ah * math.cos(angle - math.pi/8), y2 - ah * math.sin(angle - math.pi/8)),
                (x2 - ah * math.cos(angle + math.pi/8), y2 - ah * math.sin(angle + math.pi/8)),
            ]
            draw.polygon(pts_a, fill=color)
        else:
            pts = [
                (x2, y2),
                (x2 - ah * math.cos(angle - math.pi/8), y2 - ah * math.sin(angle - math.pi/8)),
                (x2 - ah * math.cos(angle + math.pi/8), y2 - ah * math.sin(angle + math.pi/8)),
            ]
            draw.polygon(pts, fill=color)

        label = rel.name + (f" {rel.multiplicity}" if rel.multiplicity else "")
        if label.strip():
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            lw2 = draw.textlength(label, font=font_body)
            ly2 = my + (lo / 18.0) * 14.0
            draw.rounded_rectangle(
                [mx - lw2/2 - 6, ly2 - 10, mx + lw2/2 + 6, ly2 + 8],
                radius=5, fill="#ffffff"
            )
            draw.text((mx - lw2/2, ly2 - 8), label, fill=color, font=font_body)

    for name, node in classes.items():
        cx, cy = tr(pos[name]); w, h = sizes[name]
        x, y = cx - w/2, cy - h/2
        header_color = "#6d28d9" if node.is_abstract else "#0f766e"
        outline = "#fb923c" if (highlight_classes and name in (highlight_classes or set())) else "#334155"
        draw.rounded_rectangle((x, y, x+w, y+h), radius=10, fill="#ffffff", outline=outline, width=2)
        draw.rounded_rectangle((x, y, x+w, y+34), radius=10, fill=header_color, outline=None)
        nw = draw.textlength(name, font=font_header)
        draw.text((cx - nw/2, y+10), name, fill="#ffffff", font=font_header)
        ty = y + 52
        for a, t in node.attributes:
            draw.text((x+12, ty), f"{a}: {t}", fill="#1e293b", font=font_body)
            ty += 24

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
            ty += 24

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

    out    = Path(output_path)
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