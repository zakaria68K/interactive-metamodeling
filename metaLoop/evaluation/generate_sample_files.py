import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]

# Default suffix for each known metamodel file name
_SUFFIX_MAP: dict[str, str] = {
    "BPMN": "process",
    "Relational": "schema",
    "KM3": "metamodel",
    "Measure": "quality",
    "MySql": "database",
    "RSS": "feed",
}

_SYSTEM_PROMPT = """\
You are a requirements engineer specialising in domain modelling.

Your task is to write a semi-formal requirements specification (200-400 words, plain
text, no markdown headings, no bullet lists) that describes what a system for the given
domain must manage and how the elements of that domain relate to each other.

Rules
─────
1. The document must implicitly cover EVERY concept from the internal inventory so that
   a reader can infer each one from the requirements text.  The concept names themselves
   must NEVER appear in the output — not as headings, not inline, not in any form.
2. Rephrase every concept as plain domain language (e.g. instead of "SequenceFlow" say
   "the directed connection between two steps"; instead of "EnumColumn" say "a column
   restricted to a fixed set of allowed values").
3. Write in a formal but readable requirements style: "The system shall …", "Each … must …",
   "A … is associated with …", "When … the system records …".
4. Be concrete: use cardinalities, optionality, and ownership (e.g. "each table contains
   one or more columns", "a metric belongs to exactly one category").
5. Do NOT produce bullet lists, numbered lists, or section headings — continuous prose only.
"""

_HUMAN_TEMPLATE = """\
Domain: {domain_name}

The following internal concept inventory drives your writing — do NOT mention, list, \
or echo any of these names anywhere in the output document:
{concept_list}

Output only the requirements document text. Do not include any preamble, concept list, \
section headers, or metadata.
"""


def parse_ecore_classes(ecore_path: Path) -> list[str]:
    XSI = "http://www.w3.org/2001/XMLSchema-instance"
    tree = ET.parse(str(ecore_path))
    root = tree.getroot()
    names: list[str] = []
    for elem in root.iter():
        if elem.get(f"{{{XSI}}}type") == "ecore:EClass":
            name = elem.get("name")
            if name:
                names.append(name)
    return names


def generate_sample(domain_name: str, concepts: list[str]) -> str:
    model_name = os.getenv("EVAL_SYSTEM_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    llm = ChatOpenAI(model=model_name, max_retries=2)
    chain = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        ("human", _HUMAN_TEMPLATE),
    ]) | llm
    response = chain.invoke({
        "domain_name": domain_name,
        "concept_list": "\n".join(f"- {c}" for c in concepts),
    })
    return response.content if isinstance(response.content, str) else str(response.content)


def process_ecore(ecore_path: Path, out_dir: Path) -> None:
    stem = ecore_path.stem  # e.g. "BPMN"
    suffix = _SUFFIX_MAP.get(stem, stem.lower())
    domain_name = stem.lower()
    out_file = out_dir / f"{domain_name}_{suffix}.md"

    print(f"Processing {ecore_path.name} ...", end=" ", flush=True)
    concepts = parse_ecore_classes(ecore_path)
    if not concepts:
        print("SKIP (no EClass found)")
        return

    print(f"{len(concepts)} concepts found, generating ...", end=" ", flush=True)
    text = generate_sample(stem, concepts)
    out_file.write_text(text, encoding="utf-8")
    print(f"saved → {out_file.relative_to(ROOT)}")


def main() -> None:
    out_dir = ROOT / "metaLoop" / "evaluation" / "sample_files" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) > 1:
        ecore_files = [Path(p).resolve() for p in sys.argv[1:]]
    else:
        metamodels_dir = ROOT / "metaLoop" / "evaluation" / "metamodels"
        ecore_files = sorted(metamodels_dir.glob("*.ecore"))

    if not ecore_files:
        print("No .ecore files found.")
        sys.exit(1)

    for ecore_path in ecore_files:
        process_ecore(ecore_path, out_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
