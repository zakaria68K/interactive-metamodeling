
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

class RelationEdge(NamedTuple):
    source: str   # owning class
    name: str     # reference name  ("extends" for inheritance)
    target: str   # target class (or parent class)
    kind: str     # "reference" | "containment" | "inheritance"

    def normalised(self) -> "RelationEdge":
        return RelationEdge(
            self.source.strip().lower(),
            self.name.strip().lower(),
            self.target.strip().lower(),
            self.kind.strip().lower(),
        )

    def __str__(self) -> str:
        if self.kind == "inheritance":
            return f"{self.source} extends {self.target}"
        return f"{self.source}.{self.name} --[{self.kind}]--> {self.target}"


@dataclass
class RelationSet:
    edges: list[RelationEdge] = field(default_factory=list)

    def normalised(self) -> set[RelationEdge]:
        return {e.normalised() for e in self.edges}

    def __len__(self) -> int:
        return len(self.edges)


# ─────────────────────────────────────────────────────────────────────────────
# JjScript parser
# ─────────────────────────────────────────────────────────────────────────────

# create reference <name> in <Source> type <Target> [multiplicity]
# create containment <name> in <Source> type <Target> [multiplicity]
_REF_RE = re.compile(
    r"^\s*create\s+(reference|containment)\s+(\S+)\s+in\s+(\S+)\s+type\s+(\S+)",
    re.IGNORECASE,
)
# <Child> extends <Parent>   (also catches: create class X extends Y)
_INHERIT_RE = re.compile(
    r"(?:^|\s)([A-Za-z_][A-Za-z0-9_]*)\s+extends\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def extract_relations_from_jjscript(jjscript: str) -> RelationSet:
    rs = RelationSet()
    for line in jjscript.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m = _REF_RE.match(line)
        if m:
            kind   = m.group(1).lower()
            name   = m.group(2)
            source = m.group(3)
            target = re.sub(r"\[.*?\]$", "", m.group(4)).strip()
            rs.edges.append(RelationEdge(source, name, target, kind))
            continue

        # inheritance — can appear inside "create class X extends Y" or standalone
        for m2 in _INHERIT_RE.finditer(line):
            child, parent = m2.group(1), m2.group(2)
            rs.edges.append(RelationEdge(child, "extends", parent, "inheritance"))

    return rs


# ─────────────────────────────────────────────────────────────────────────────
# Ecore parser — handles both root formats
# ─────────────────────────────────────────────────────────────────────────────

_XSI = "http://www.w3.org/2001/XMLSchema-instance"


def _resolve_ref(ref: str, pkg_class_names: dict[str, str]) -> str:
    """
    Resolve an eType / eSuperTypes token to a plain class name.

    Handles:
      #//ClassName              -> ClassName
      /N/ClassName              -> ClassName   (multi-package XMI)
      /N/ClassName/subFeature   -> ClassName   (take first segment only)
      bare ClassName            -> ClassName
    """
    # /N/ClassName  or  /N/ClassName/...
    m = re.match(r"^/\d+/([A-Za-z_][A-Za-z0-9_]*)", ref)
    if m:
        return m.group(1)
    # #//ClassName
    m2 = re.match(r"^#//([A-Za-z_][A-Za-z0-9_]*)", ref)
    if m2:
        return m2.group(1)
    # fallback: strip everything before last /
    return ref.split("/")[-1]


def _extract_from_package(pkg_elem: ET.Element) -> list[RelationEdge]:
    """Extract all relation edges from a single <ecore:EPackage> element."""
    edges: list[RelationEdge] = []
    for cls in pkg_elem:
        ctype = cls.get(f"{{{_XSI}}}type", "")
        if "EClass" not in ctype:
            continue
        owner = cls.get("name", "")
        if not owner:
            continue

        # Inheritance
        supers = cls.get("eSuperTypes", "")
        for token in supers.split():
            parent = _resolve_ref(token, {})
            if parent:
                edges.append(RelationEdge(owner, "extends", parent, "inheritance"))

        # Structural features
        for feat in cls:
            ft = feat.get(f"{{{_XSI}}}type", "")
            if "EReference" not in ft:
                continue
            ref_name = feat.get("name", "")
            e_type   = feat.get("eType", "")
            target   = _resolve_ref(e_type, {})
            is_cont  = feat.get("containment", "false").lower() == "true"
            kind     = "containment" if is_cont else "reference"
            if ref_name and target:
                edges.append(RelationEdge(owner, ref_name, target, kind))

    return edges


def extract_relations_from_ecore(ecore_path: Path | str) -> RelationSet:
    """Parse any of the supported .ecore / .xmi formats and return all edges."""
    content = Path(ecore_path).read_text(encoding="utf-8", errors="replace")
    root = ET.fromstring(content)
    rs = RelationSet()

    root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    if root_tag == "EPackage":
        # Standard single-package format
        rs.edges.extend(_extract_from_package(root))

    elif root_tag == "XMI":
        # Multi-package XMI: iterate direct EPackage children
        for child in root:
            ctag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if ctag == "EPackage":
                rs.edges.extend(_extract_from_package(child))

    return rs


# ─────────────────────────────────────────────────────────────────────────────
# Precision scorer
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RelationPrecisionResult:
    generated: RelationSet
    golden: RelationSet
    true_positives: list[RelationEdge]
    false_positives: list[RelationEdge]
    precision: float

    def summary(self) -> str:
        lines = [
            f"Generated : {len(self.generated)} edges",
            f"Golden    : {len(self.golden)} edges",
            f"TP        : {len(self.true_positives)}",
            f"FP        : {len(self.false_positives)}",
            f"Precision : {self.precision:.3f}",
            "",
            "✓ Matched:",
        ]
        for e in sorted(self.true_positives):
            lines.append(f"  {e}")
        lines += ["", "✗ Not in golden:"]
        for e in sorted(self.false_positives):
            lines.append(f"  {e}")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "generated_count": len(self.generated),
            "golden_count": len(self.golden),
            "true_positives": [str(e) for e in self.true_positives],
            "false_positives": [str(e) for e in self.false_positives],
            "precision": self.precision,
        }


def compute_relation_precision(
    generated: RelationSet,
    golden: RelationSet,
) -> RelationPrecisionResult:
    golden_norm = golden.normalised()
    tp, fp = [], []
    for edge in generated.edges:
        (tp if edge.normalised() in golden_norm else fp).append(edge)
    precision = len(tp) / len(generated) if generated.edges else 0.0
    return RelationPrecisionResult(generated, golden, tp, fp, precision)


def evaluate_jjscript_against_ecore(
    jjscript: str,
    ecore_path: Path | str,
) -> RelationPrecisionResult:
    return compute_relation_precision(
        extract_relations_from_jjscript(jjscript),
        extract_relations_from_ecore(ecore_path),
    )
