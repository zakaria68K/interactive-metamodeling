import json
import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Callable, List, Set

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from pypdf import PdfReader
from metaLoop.baselineApproaches.direct_generation import generate_direct

from metaLoop.evaluation.llm_extractor import ConceptExtractor
from metaLoop.evaluation.user_simulator import ProfileUserLLM, SimulatedUserProfile
from metaLoop.evaluation.datasets import DOMAIN_CONFIGS
from metaLoop.metamodeling_agent import MetamodelingAgent
from metaLoop.evaluation.relation_eval import evaluate_jjscript_against_ecore, RelationPrecisionResult


GENERATED_SAMPLE_DIR = ROOT / "metaLoop" / "evaluation" / "sample_files" / "generated"
ONE_SHOT_ITERATIONS = int(os.getenv("ONE_SHOT_ITERATIONS", "3"))


# ─────────────────────────────────────────────────────────────────────────────
# Logging  — created inside main(), not at import time
# ─────────────────────────────────────────────────────────────────────────────

def _setup_logger() -> logging.Logger:
    log_dir = ROOT / "metaLoop" / "evaluation" / "results"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path  = log_dir / f"eval_{timestamp}.log"

    log = logging.getLogger("metaLoop.eval")
    log.setLevel(logging.DEBUG)
    log.handlers.clear()

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    log.addHandler(fh)
    log.addHandler(ch)
    log.info("Log file: %s", log_path)
    return log


# Module-level placeholder; replaced by _setup_logger() inside main()
logger: logging.Logger = logging.getLogger("metaLoop.eval")


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MethodResult:
    name: str
    final_metamodel: str          # raw JjScript produced by this method
    final_concepts: Set[str]
    # concept metrics
    concept_precision: float
    concept_recall: float
    concept_f1: float
    # relation metrics
    relation_precision: float
    relation_tp: list[str]        # matched edges as strings
    relation_fp: list[str]        # unmatched edges as strings
    relation_generated_count: int
    relation_golden_count: int
    # interaction log
    transcript: list[dict[str, str]]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize(items: List[str]) -> Set[str]:
    return {x.strip().lower() for x in items if x and x.strip()}


def precision_recall_f1(expected: Set[str], predicted: Set[str]) -> tuple[float, float, float]:
    tp = len(expected & predicted)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1        = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


def parse_ecore_concepts(ecore_path: Path) -> List[str]:
    """Extract all EClass names from any supported .ecore / .xmi format."""
    XSI = "http://www.w3.org/2001/XMLSchema-instance"
    try:
        tree = ET.parse(str(ecore_path))
        root = tree.getroot()
        # root.iter() descends into all children regardless of root tag style
        # so this handles both standard EPackage and multi-package XMI roots
        return [
            elem.get("name")
            for elem in root.iter()
            if elem.get(f"{{{XSI}}}type") == "ecore:EClass" and elem.get("name")
        ]
    except ET.ParseError as exc:
        raise ValueError(f"Failed to parse ecore file {ecore_path}: {exc}") from exc


def read_sample_file(file_path: str | None) -> str:
    if not file_path:
        return ""
    resolved = Path(file_path)
    if not resolved.is_absolute():
        resolved = (ROOT / resolved).resolve()
    if resolved.suffix.lower() == ".pdf":
        reader = PdfReader(str(resolved))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return resolved.read_text(encoding="utf-8", errors="ignore")


def _log_final_metamodel(method_name: str, profile_id: str, metamodel: str) -> None:
    """Log the full JjScript to the file at DEBUG level (not shown on console)."""
    sep = "─" * 72
    logger.debug(
        "\n%s\n  FINAL METAMODEL  |  method=%-24s  |  domain=%s\n%s\n%s\n%s",
        sep, method_name, profile_id, sep, metamodel.strip(), sep,
    )


def _eval_relations(metamodel: str, ecore_path: Path) -> RelationPrecisionResult:
    return evaluate_jjscript_against_ecore(metamodel, ecore_path)


# ─────────────────────────────────────────────────────────────────────────────
# Method runners
# ─────────────────────────────────────────────────────────────────────────────

def run_interactive(
    agent: MetamodelingAgent,
    extractor: ConceptExtractor,
    profile: SimulatedUserProfile,
    ecore_path: Path,
) -> MethodResult:
    user_llm = ProfileUserLLM(profile)
    result = agent.run_iterative(
        profile.prompt,
        human_validator=lambda _: True,   # auto-approve during evaluation
        user_responder=user_llm.respond,
        initial_state={
            "attached_file_content": read_sample_file(profile.sample_file_path),
            "skip_isolated_validation": True,
        },
    )

    final_metamodel = result.get("final_metamodel", "")
    _log_final_metamodel("interactive", profile.profile_id, final_metamodel)

    extracted      = extractor.extract(profile.prompt, final_metamodel)
    final_concepts = normalize(extracted.get("concepts", []))
    cp, cr, cf1    = precision_recall_f1(normalize(profile.target_concepts), final_concepts)

    rel = _eval_relations(final_metamodel, ecore_path)
    logger.debug("  relation eval (interactive / %s): precision=%.3f  TP=%d  FP=%d",
                 profile.profile_id, rel.precision, len(rel.true_positives), len(rel.false_positives))

    return MethodResult(
        name="interactive",
        final_metamodel=final_metamodel,
        final_concepts=final_concepts,
        concept_precision=cp, concept_recall=cr, concept_f1=cf1,
        relation_precision=rel.precision,
        relation_tp=[str(e) for e in rel.true_positives],
        relation_fp=[str(e) for e in rel.false_positives],
        relation_generated_count=len(rel.generated),
        relation_golden_count=len(rel.golden),
        transcript=list(user_llm.history),
    )


def run_one_shot(
    extractor: ConceptExtractor,
    profile: SimulatedUserProfile,
    ecore_path: Path,
) -> MethodResult:
    file_content = read_sample_file(profile.sample_file_path)
    transcript: list[dict[str, str]] = []

    metamodel_text = generate_direct(profile.prompt, file_content)
    transcript.append({"stage": "generation_1", "question": profile.prompt, "answer": metamodel_text})

    for iteration in range(2, ONE_SHOT_ITERATIONS + 1):
        metamodel_text = generate_direct(profile.prompt, file_content, previous_result=metamodel_text)
        transcript.append({
            "stage": f"generation_{iteration}",
            "question": profile.prompt,
            "answer": metamodel_text,
        })

    _log_final_metamodel("one_shot", profile.profile_id, metamodel_text)

    extracted = extractor.extract(profile.prompt, metamodel_text)
    predicted = normalize(extracted.get("concepts", []))
    cp, cr, cf1 = precision_recall_f1(normalize(profile.target_concepts), predicted)

    rel = _eval_relations(metamodel_text, ecore_path)
    logger.debug("  relation eval (one_shot / %s): precision=%.3f  TP=%d  FP=%d",
                 profile.profile_id, rel.precision, len(rel.true_positives), len(rel.false_positives))

    return MethodResult(
        name="one_shot",
        final_metamodel=metamodel_text,
        final_concepts=predicted,
        concept_precision=cp, concept_recall=cr, concept_f1=cf1,
        relation_precision=rel.precision,
        relation_tp=[str(e) for e in rel.true_positives],
        relation_fp=[str(e) for e in rel.false_positives],
        relation_generated_count=len(rel.generated),
        relation_golden_count=len(rel.golden),
        transcript=transcript,
    )



# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────

def write_report(rows: list[dict], methods: list[str]) -> Path:
    out_dir = ROOT / "metaLoop" / "evaluation" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag       = "_".join(methods)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = out_dir / f"eval_{tag}_{timestamp}.json"
    report_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return report_path


def build_profiles() -> list[tuple[SimulatedUserProfile, Path]]:
    """Return (profile, ecore_path) pairs — one per domain config."""
    pairs = []
    for domain_name, config in DOMAIN_CONFIGS.items():
        ecore_path      = ROOT / config["metamodel_path"]
        target_concepts = parse_ecore_concepts(ecore_path)
        sample_path     = GENERATED_SAMPLE_DIR / f"{domain_name}_{config['sample_suffix']}.md"
        profile = SimulatedUserProfile(
            profile_id=domain_name,
            prompt=config["prompt"],
            target_concepts=target_concepts,
            sample_file_path=str(sample_path.relative_to(ROOT)) if sample_path.exists() else None,
        )
        pairs.append((profile, ecore_path))
    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    global logger
    logger = _setup_logger()   # create log file only when actually running

    runs  = int(os.getenv("EVAL_RUNS", "1"))
    limit = int(os.getenv("EVAL_LIMIT", "0"))

    profile_pairs = build_profiles()
    if limit > 0:
        profile_pairs = profile_pairs[:limit]

    agent     = MetamodelingAgent()
    extractor = ConceptExtractor()

    all_methods: List[tuple[str, Callable[[SimulatedUserProfile, Path], MethodResult]]] = [
        ("interactive",            lambda p, ep: run_interactive(agent, extractor, p, ep)),
        ("one_shot",               lambda p, ep: run_one_shot(extractor, p, ep))
    ]
    _filter = {m.strip() for m in os.getenv("EVAL_METHODS", "").split(",") if m.strip()}
    methods = [(n, f) for n, f in all_methods if not _filter or n in _filter]

    per_method_concept_f1:         dict[str, List[float]] = {n: [] for n, _ in methods}
    per_method_relation_precision: dict[str, List[float]] = {n: [] for n, _ in methods}
    report_rows: list[dict] = []

    for run_idx in range(1, runs + 1):
        logger.info("\n=== Run %d ===", run_idx)

        for profile, ecore_path in profile_pairs:
            logger.info("\n  Domain : %s", profile.profile_id)
            logger.info("  Target : %d concepts : %s",
                        len(profile.target_concepts),
                        sorted(normalize(profile.target_concepts)))
            logger.info("  Sample : %s", profile.sample_file_path or "(none)")
            logger.info("  Golden : %s", ecore_path.name)

            for method_name, runner in methods:
                logger.info("  Running: %s ...", method_name)
                result = runner(profile, ecore_path)

                per_method_concept_f1[method_name].append(result.concept_f1)
                per_method_relation_precision[method_name].append(result.relation_precision)

                logger.info(
                    "  %-24s | concept  P=%.3f R=%.3f F1=%.3f | "
                    "relation P=%.3f  TP=%d  FP=%d  golden=%d",
                    result.name,
                    result.concept_precision, result.concept_recall, result.concept_f1,
                    result.relation_precision,
                    len(result.relation_tp), len(result.relation_fp),
                    result.relation_golden_count,
                )

                report_rows.append({
                    "run":              run_idx,
                    "profile_id":       profile.profile_id,
                    "sample_file_path": profile.sample_file_path,
                    "method":           result.name,
                    # ── concept evaluation ──────────────────────────────────
                    "target":               sorted(normalize(profile.target_concepts)),
                    "target_size":          len(profile.target_concepts),
                    "predicted_concepts":   sorted(result.final_concepts),
                    "concept_precision":    result.concept_precision,
                    "concept_recall":       result.concept_recall,
                    "concept_f1":           result.concept_f1,
                    # ── relation evaluation ─────────────────────────────────
                    "relation_precision":        result.relation_precision,
                    "relation_generated_count":  result.relation_generated_count,
                    "relation_golden_count":     result.relation_golden_count,
                    "relation_true_positives":   result.relation_tp,
                    "relation_false_positives":  result.relation_fp,
                    # ── generated JjScript ──────────────────────────────────
                    "final_metamodel": result.final_metamodel,
                    # ── interaction transcript ──────────────────────────────
                    "transcript":      result.transcript,
                })

    # ── Summary ──────────────────────────────────────────────────────────────
    logger.info("\n%s", "═" * 72)
    logger.info("SUMMARY")
    logger.info("%-26s  %-14s  %-22s", "method", "avg_concept_F1", "avg_relation_precision")
    logger.info("%-26s  %-14s  %-22s", "─" * 26, "─" * 14, "─" * 22)
    for method_name, _ in methods:
        cf1 = per_method_concept_f1[method_name]
        rp  = per_method_relation_precision[method_name]
        logger.info("%-26s  %-14.3f  %-22.3f",
                    method_name,
                    sum(cf1) / len(cf1) if cf1 else 0.0,
                    sum(rp)  / len(rp)  if rp  else 0.0)
    logger.info("═" * 72)

    report_path = write_report(report_rows, [n for n, _ in methods])
    logger.info("\nReport: %s", report_path)


if __name__ == "__main__":
    main()