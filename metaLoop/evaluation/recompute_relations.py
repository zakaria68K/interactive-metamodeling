import json
import re
import sys
from pathlib import Path


# ── inline copy of relation_eval logic (no import needed) ────────────────────

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import NamedTuple


class RelationEdge(NamedTuple):
    source: str
    name: str
    target: str
    kind: str

    def __str__(self):
        if self.kind == "inheritance":
            return f"{self.source} extends {self.target}"
        return f"{self.source}.{self.name} --[{self.kind}]--> {self.target}"


@dataclass
class RelationSet:
    edges: list = field(default_factory=list)

    def normalised_keys(self):
        return {
            (e.source.strip().lower(), e.target.strip().lower(), e.kind.strip().lower())
            for e in self.edges
        }

    def __len__(self):
        return len(self.edges)


_REF_RE = re.compile(
    r"^\s*create\s+(reference|containment)\s+(\S+)\s+in\s+(\S+)\s+type\s+(\S+)",
    re.IGNORECASE,
)
_INHERIT_RE = re.compile(
    r"(?:^|\s)([A-Za-z_][A-Za-z0-9_]*)\s+extends\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_JJSCRIPT_KW = (
    "create object ", "create class ", "create attribute ",
    "create reference ", "create containment ", "set ", "add ",
)
_FENCE_RE = re.compile(r"```(?:jjscript)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _clean(raw: str) -> str:
    """Extract JjScript from prose-wrapped fenced blocks, or return as-is."""
    blocks = _FENCE_RE.findall(raw)
    if blocks:
        raw = "\n".join(blocks)
    return "\n".join(
        line for line in raw.splitlines()
        if (s := line.strip()) and (
            s.startswith("#") or any(s.lower().startswith(k) for k in _JJSCRIPT_KW)
            or re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s+extends\s+[A-Za-z_]", s, re.IGNORECASE)
        )
    ).strip()


def extract_jjscript_relations(jjscript: str) -> RelationSet:
    rs = RelationSet()
    for line in jjscript.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = _REF_RE.match(line)
        if m:
            kind   = m.group(1).lower()
            name   = m.group(2)
            source = m.group(3)
            target = re.sub(r"\[.*?\]$", "", m.group(4)).strip()
            rs.edges.append(RelationEdge(source, name, target, kind))
            continue
        for m2 in _INHERIT_RE.finditer(line):
            rs.edges.append(RelationEdge(m2.group(1), "extends", m2.group(2), "inheritance"))
    return rs


_XSI = "http://www.w3.org/2001/XMLSchema-instance"


def _resolve(ref: str) -> str:
    m = re.match(r"^/\d+/([A-Za-z_][A-Za-z0-9_]*)", ref)
    if m:
        return m.group(1)
    m2 = re.match(r"^#//([A-Za-z_][A-Za-z0-9_]*)", ref)
    if m2:
        return m2.group(1)
    return ref.split("/")[-1]


def _from_pkg(pkg: ET.Element) -> list:
    edges = []
    for cls in pkg:
        ctype = cls.get(f"{{{_XSI}}}type", "")
        if "EClass" not in ctype:
            continue
        owner = cls.get("name", "")
        if not owner:
            continue
        for token in cls.get("eSuperTypes", "").split():
            parent = _resolve(token)
            if parent:
                edges.append(RelationEdge(owner, "extends", parent, "inheritance"))
        for feat in cls:
            if "EReference" not in feat.get(f"{{{_XSI}}}type", ""):
                continue
            ref_name = feat.get("name", "")
            target   = _resolve(feat.get("eType", ""))
            is_cont  = feat.get("containment", "false").lower() == "true"
            kind     = "containment" if is_cont else "reference"
            if ref_name and target:
                edges.append(RelationEdge(owner, ref_name, target, kind))
    return edges


def extract_ecore_relations(ecore_path: Path) -> RelationSet:
    root = ET.fromstring(ecore_path.read_text(encoding="utf-8", errors="replace"))
    rs = RelationSet()
    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if tag == "EPackage":
        rs.edges.extend(_from_pkg(root))
    elif tag == "XMI":
        for child in root:
            ctag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if ctag == "EPackage":
                rs.edges.extend(_from_pkg(child))
    return rs


def compute_precision(generated: RelationSet, golden: RelationSet):
    golden_keys = golden.normalised_keys()
    tp, fp = [], []
    for edge in generated.edges:
        key = (edge.source.lower(), edge.target.lower(), edge.kind.lower())
        (tp if key in golden_keys else fp).append(edge)
    precision = len(tp) / len(generated) if generated.edges else 0.0
    return precision, tp, fp


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    report_path   = Path(sys.argv[1])
    metamodels_dir = Path(sys.argv[2])

    rows = json.loads(report_path.read_text(encoding="utf-8"))

    # domain -> ecore path  (try common suffixes)
    def find_ecore(domain: str) -> Path | None:
        candidates = [
            metamodels_dir / f"{domain}.ecore",
            metamodels_dir / f"{domain.upper()}.ecore",
            metamodels_dir / f"{domain.capitalize()}.ecore",
            metamodels_dir / f"MySql.ecore" if domain == "mysql" else None,
        ]
        for c in candidates:
            if c and c.exists():
                return c
        # case-insensitive fallback
        for p in metamodels_dir.glob("*.ecore"):
            if p.stem.lower() == domain.lower():
                return p
        return None

    # preload golden relations
    golden_cache: dict[str, RelationSet] = {}

    updated_rows = []
    summary: dict[str, list[float]] = {}

    for row in rows:
        domain  = row["profile_id"]
        method  = row["method"]
        raw_mm  = row.get("final_metamodel", "")

        # clean JjScript
        clean_mm = _clean(raw_mm)

        # get or load golden
        if domain not in golden_cache:
            ecore_path = find_ecore(domain)
            if ecore_path:
                golden_cache[domain] = extract_ecore_relations(ecore_path)
                print(f"  Loaded golden: {ecore_path.name}  ({len(golden_cache[domain])} edges)")
            else:
                print(f"  WARNING: no ecore found for domain '{domain}' in {metamodels_dir}")
                golden_cache[domain] = RelationSet()

        golden  = golden_cache[domain]
        gen_rel = extract_jjscript_relations(clean_mm)
        precision, tp, fp = compute_precision(gen_rel, golden)

        row["final_metamodel"]            = clean_mm          # store clean version
        row["relation_precision"]         = precision
        row["relation_generated_count"]   = len(gen_rel)
        row["relation_golden_count"]      = len(golden)
        row["relation_true_positives"]    = [str(e) for e in tp]
        row["relation_false_positives"]   = [str(e) for e in fp]

        summary.setdefault(method, []).append(precision)

        print(
            f"  {method:<24} | {domain:<12} | "
            f"generated={len(gen_rel):>3}  golden={len(golden):>3}  "
            f"TP={len(tp):>3}  FP={len(fp):>3}  precision={precision:.3f}"
        )
        updated_rows.append(row)

    # write updated report
    out_path = report_path.parent / (report_path.stem + "_with_relations.json")
    out_path.write_text(json.dumps(updated_rows, indent=2), encoding="utf-8")
    print(f"\nUpdated report: {out_path}")

    # summary
    print("\n" + "═" * 60)
    print(f"{'method':<26}  {'avg_relation_precision':>22}")
    print(f"{'─'*26}  {'─'*22}")
    for method, scores in summary.items():
        avg = sum(scores) / len(scores)
        print(f"{method:<26}  {avg:>22.3f}")
    print("═" * 60)


if __name__ == "__main__":
    main()