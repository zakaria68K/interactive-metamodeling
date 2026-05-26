import json
import os
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
from metaLoop.baselineApproaches.generate_then_validate import refine_metamodel
from metaLoop.evaluation.llm_extractor import ConceptExtractor
from metaLoop.evaluation.user_simulator import ProfileUserLLM, SimulatedUserProfile
from metaLoop.evaluation.datasets import DOMAIN_CONFIGS
from metaLoop.metamodeling_agent import MetamodelingAgent


GENERATED_SAMPLE_DIR = ROOT / "metaLoop" / "evaluation" / "sample_files" / "generated"


@dataclass
class MethodResult:
    name: str
    final_concepts: Set[str]
    precision: float
    recall: float
    f1: float
    transcript: list[dict[str, str]]


def normalize(items: List[str]) -> Set[str]:
    return {x.strip().lower() for x in items if x and x.strip()}


def precision_recall_f1(expected: Set[str], predicted: Set[str]) -> tuple[float, float, float]:
    tp = len(expected & predicted)
    fp = len(predicted - expected)
    fn = len(expected - predicted)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


def read_sample_file(file_path: str | None) -> str:
    if not file_path:
        return ""

    resolved_path = Path(file_path)
    if not resolved_path.is_absolute():
        resolved_path = (ROOT / resolved_path).resolve()

    if resolved_path.suffix.lower() == ".pdf":
        reader = PdfReader(str(resolved_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    return resolved_path.read_text(encoding="utf-8", errors="ignore")


def run_interactive(agent: MetamodelingAgent, profile: SimulatedUserProfile) -> MethodResult:
    user_llm = ProfileUserLLM(profile)
    # Use only the concept extraction pipeline (with file-based detection), skip metamodel/JjScript generation
    result = agent.run_concepts_only(
        profile.prompt,
        user_responder=user_llm.respond,
        initial_state={"attached_file_content": read_sample_file(profile.sample_file_path)},
    )
    final_concepts = normalize(result.get("concepts", []))
    precision, recall, f1 = precision_recall_f1(normalize(profile.target_concepts), final_concepts)
    return MethodResult(
        "interactive",
        final_concepts,
        precision,
        recall,
        f1,
        list(user_llm.history),
    )


def run_one_shot(extractor: ConceptExtractor, profile: SimulatedUserProfile) -> MethodResult:
    # Generate full JjScript metamodel then extract concepts from it
    file_content = read_sample_file(profile.sample_file_path)
    metamodel_text = generate_direct(profile.prompt, file_content)
    extracted = extractor.extract(profile.prompt, metamodel_text)
    predicted = normalize(extracted.get("concepts", []))
    precision, recall, f1 = precision_recall_f1(normalize(profile.target_concepts), predicted)
    transcript = [{"stage": "prompt", "question": profile.prompt, "answer": metamodel_text}]
    return MethodResult(
        "one_shot",
        predicted,
        precision,
        recall,
        f1,
        transcript,
    )


def run_generate_then_validate(
    extractor: ConceptExtractor,
    profile: SimulatedUserProfile,
    max_iterations: int = 3,
) -> MethodResult:
    """Generate a full metamodel first, then validate and refine with the user.

    Interaction mirrors the interactive approach:
    - Per-concept yes/no confirmation (same as elicitation confirmation step).
    - A neutral feedback question after each pass (same style as the background
      question in knowledge_elicitation) where the user may mention concepts
      organically but is not asked to enumerate what is missing.
    """
    user_llm = ProfileUserLLM(profile)
    file_content = read_sample_file(profile.sample_file_path)

    def _is_yes(answer: str) -> bool:
        return answer.strip().lower().rstrip(".?!") in {"yes", "y"}

    # Step 1: initial one-shot generation
    metamodel_text = generate_direct(profile.prompt, file_content)
    transcript: list[dict[str, str]] = [
        {"stage": "initial_generation", "question": profile.prompt, "answer": metamodel_text}
    ]

    approved: list[str] = []

    def _confirm_concepts(candidates: list[str]) -> None:
        for concept in candidates:
            if concept in approved:
                continue
            q = f"Is '{concept}' a relevant concept in your domain? Answer yes or no only."
            answer = user_llm.respond(q, {"stage": "concept_confirmation", "concept": concept})
            transcript.append({"stage": "concept_confirmation", "question": q, "answer": answer})
            if _is_yes(answer):
                approved.append(concept)

    # Step 2: confirm initial candidates one by one
    _confirm_concepts(extractor.extract(profile.prompt, metamodel_text).get("concepts", []))

    # Step 3: neutral feedback question + refinement (same style as background question in interactive)
    feedback_q = "Do you have any feedback about this metamodel or the domain it covers?"
    for _ in range(max_iterations - 1):
        feedback = user_llm.respond(feedback_q, {"stage": "feedback", "approved": approved})
        transcript.append({"stage": "feedback", "question": feedback_q, "answer": feedback})
        metamodel_text = refine_metamodel(profile.prompt, metamodel_text, feedback)
        transcript.append({"stage": "refinement", "question": "refinement", "answer": metamodel_text})
        new_candidates = extractor.extract(profile.prompt, metamodel_text).get("concepts", [])
        _confirm_concepts(new_candidates)

    predicted = normalize(approved)
    precision, recall, f1 = precision_recall_f1(normalize(profile.target_concepts), predicted)
    return MethodResult("generate_then_validate", predicted, precision, recall, f1, transcript)


def write_report(rows: list[dict], methods: list[str]) -> Path:
    out_dir = ROOT / "metaLoop" / "evaluation" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "_".join(methods)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = out_dir / f"concept_eval_{tag}_{timestamp}.json"
    report_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return report_path


def build_profiles() -> list[SimulatedUserProfile]:
    profiles: list[SimulatedUserProfile] = []
    for domain_name, config in DOMAIN_CONFIGS.items():
        for index, user in enumerate(config["users"], start=1):
            sample_path = GENERATED_SAMPLE_DIR / f"{domain_name}_{user['sample_suffix']}.md"
            profiles.append(
                SimulatedUserProfile(
                    profile_id=f"{domain_name}_user_{index:02d}_{user['role']}",
                    prompt=config["prompt"],
                    target_concepts=user["target_concepts"],
                    sample_file_path=str(sample_path.relative_to(ROOT)),
                    emotion=user["emotion"],
                    verbosity=user["verbosity"],
                    strategy=user["strategy"],
                    competency=user["competency"],
                )
            )
    return profiles


def main() -> None:
    runs = int(os.getenv("EVAL_RUNS", "1"))
    profiles = build_profiles()
    limit = int(os.getenv("EVAL_LIMIT", "0"))
    if limit > 0:
        profiles = profiles[:limit]

    agent = MetamodelingAgent()
    extractor = ConceptExtractor()

    all_methods: List[tuple[str, Callable[[SimulatedUserProfile], MethodResult]]] = [
        ("interactive", lambda profile: run_interactive(agent, profile)),
        ("one_shot", lambda profile: run_one_shot(extractor, profile)),
        ("generate_then_validate", lambda profile: run_generate_then_validate(extractor, profile)),
    ]
    _method_filter = {m.strip() for m in os.getenv("EVAL_METHODS", "").split(",") if m.strip()}
    methods = [(n, f) for n, f in all_methods if not _method_filter or n in _method_filter]

    per_method_metrics: dict[str, List[float]] = {name: [] for name, _ in methods}
    report_rows: list[dict] = []

    for run_idx in range(1, runs + 1):
        print(f"\n=== Run {run_idx} ===")
        for profile in profiles:
            print(f"\n{profile.profile_id}")
            print(f"Target: {sorted(normalize(profile.target_concepts))}")
            print(f"Sample file: {profile.sample_file_path or '(none)'}")
            for method_name, runner in methods:
                result = runner(profile)
                per_method_metrics[method_name].append(result.f1)
                report_rows.append({
                    "run": run_idx,
                    "profile_id": profile.profile_id,
                    "sample_file_path": profile.sample_file_path,
                    # Trait fields — used for per-trait breakdown plots
                    "emotion": profile.emotion,
                    "verbosity": profile.verbosity,
                    "strategy": profile.strategy,
                    "competency": profile.competency,
                    "method": result.name,
                    "target": sorted(normalize(profile.target_concepts)),
                    "target_size": len(profile.target_concepts),
                    "predicted": sorted(result.final_concepts),
                    "precision": result.precision,
                    "recall": result.recall,
                    "f1": result.f1,
                    "transcript": result.transcript,
                })
                print(
                    f"{result.name:>14} | predicted={sorted(result.final_concepts)} "
                    f"| F1={result.f1:.3f}"
                )

    print("\n=== Summary ===")
    for method_name, _ in methods:
        avg_f1 = sum(per_method_metrics[method_name]) / len(per_method_metrics[method_name])
        print(f"{method_name:>14} | avg_f1={avg_f1:.3f}")

    report_path = write_report(report_rows, [name for name, _ in methods])
    print(f"\nReport: {report_path}")

if __name__ == "__main__":
    main()
