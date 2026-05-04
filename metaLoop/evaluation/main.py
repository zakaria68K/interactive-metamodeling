import json
import os
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable, List, Set

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from metaLoop.baselineApproaches.direct_generation import generate_direct
from metaLoop.elicitation import decompose_concepts, gather_intent
from metaLoop.evaluation.llm_extractor import ConceptExtractor
from metaLoop.evaluation.user_simulator import ProfileUserLLM, SimulatedUserProfile
from metaLoop.metamodeling_agent import MetamodelingAgent


@dataclass
class MethodResult:
    name: str
    concepts: Set[str]
    precision: float
    recall: float
    f1: float
    leakage: Set[str]
    exact_hit: bool
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


def evaluate_prediction(target: Set[str], predicted: Set[str], universe: Set[str]) -> tuple[float, float, float, Set[str]]:
    precision, recall, f1 = precision_recall_f1(target, predicted)
    leakage = (predicted & universe) - target
    return precision, recall, f1, leakage


def run_interactive(agent: MetamodelingAgent, profile: SimulatedUserProfile, universe: Set[str]) -> MethodResult:
    user_llm = ProfileUserLLM(profile)
    result = agent.run_concepts_only(profile.prompt, user_responder=user_llm.respond)
    predicted = normalize(result.get("concepts", []))
    target = normalize(profile.target_concepts)
    precision, recall, f1, leakage = evaluate_prediction(normalize(profile.target_concepts), predicted, universe)
    return MethodResult("interactive", predicted, precision, recall, f1, leakage, predicted == target, list(user_llm.history))


def run_no_elicitation(agent: MetamodelingAgent, profile: SimulatedUserProfile, universe: Set[str]) -> MethodResult:
    state = {"user_prompt": profile.prompt}
    state.update(gather_intent(state))
    state.update(decompose_concepts(state, agent.llm_client.invoke_json))
    predicted = normalize(state.get("concepts", []))
    target = normalize(profile.target_concepts)
    precision, recall, f1, leakage = evaluate_prediction(normalize(profile.target_concepts), predicted, universe)
    transcript = [{"stage": "prompt", "question": profile.prompt, "answer": ""}]
    return MethodResult("no_elicitation", predicted, precision, recall, f1, leakage, predicted == target, transcript)


def run_one_shot(extractor: ConceptExtractor, profile: SimulatedUserProfile, universe: Set[str]) -> MethodResult:
    metamodel_text = generate_direct(profile.prompt)
    extracted = extractor.extract("State machine", metamodel_text)
    predicted = normalize(extracted.get("concepts", []))
    target = normalize(profile.target_concepts)
    precision, recall, f1, leakage = evaluate_prediction(normalize(profile.target_concepts), predicted, universe)
    transcript = [{"stage": "prompt", "question": profile.prompt, "answer": metamodel_text}]
    return MethodResult("one_shot", predicted, precision, recall, f1, leakage, predicted == target, transcript)


def avg_pairwise_jaccard(concept_sets: List[Set[str]]) -> float:
    if len(concept_sets) < 2:
        return 0.0
    scores: List[float] = []
    for idx, left in enumerate(concept_sets):
        for right in concept_sets[idx + 1:]:
            union = left | right
            score = (len(left & right) / len(union)) if union else 1.0
            scores.append(score)
    return sum(scores) / len(scores)


def write_report(rows: list[dict]) -> Path:
    out_dir = ROOT / "metaLoop" / "evaluation" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "concept_eval_report.json"
    report_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return report_path


def main() -> None:
    runs = int(os.getenv("EVAL_RUNS", "3"))
    profiles = [
        SimulatedUserProfile(
            profile_id="user_a_event_driven",
            prompt="I want a state machine metamodel for interactive applications.",
            goal="Focus on event-driven behavior. The essential concepts are State and Event.",
            target_concepts=["State", "Event"],
        ),
        SimulatedUserProfile(
            profile_id="user_b_hierarchical",
            prompt="I want a state machine metamodel for complex systems.",
            goal="Focus on hierarchical and parallel structure. The essential concepts are State and Region.",
            target_concepts=["State", "Region"],
        ),
        SimulatedUserProfile(
            profile_id="user_c_teaching",
            prompt="I want a state machine metamodel for teaching beginners.",
            goal="Keep the model minimal for teaching. The essential concepts are State and FinalState.",
            target_concepts=["State", "FinalState"],
        ),
    ]

    agent = MetamodelingAgent()
    extractor = ConceptExtractor()
    universe = normalize([concept for profile in profiles for concept in profile.target_concepts])
    methods: List[tuple[str, Callable[[SimulatedUserProfile], MethodResult]]] = [
        ("interactive", lambda profile: run_interactive(agent, profile, universe)),
        ("no_elicitation", lambda profile: run_no_elicitation(agent, profile, universe)),
        ("one_shot", lambda profile: run_one_shot(extractor, profile, universe)),
    ]

    per_method_run_sets: dict[str, dict[int, List[Set[str]]]] = {
        name: {run_idx: [] for run_idx in range(1, runs + 1)} for name, _ in methods
    }
    per_method_f1: dict[str, List[float]] = {name: [] for name, _ in methods}
    per_method_exact: dict[str, int] = {name: 0 for name, _ in methods}
    report_rows: list[dict] = []

    for run_idx in range(1, runs + 1):
        print(f"\n=== Run {run_idx} ===")
        for profile in profiles:
            print(f"\n{profile.profile_id}")
            print(f"Target: {sorted(normalize(profile.target_concepts))}")
            for method_name, runner in methods:
                result = runner(profile)
                per_method_run_sets[method_name][run_idx].append(result.concepts)
                per_method_f1[method_name].append(result.f1)
                per_method_exact[method_name] += int(result.exact_hit)
                report_rows.append({
                    "run": run_idx,
                    "profile_id": profile.profile_id,
                    "method": result.name,
                    "target": sorted(normalize(profile.target_concepts)),
                    "predicted": sorted(result.concepts),
                    "precision": result.precision,
                    "recall": result.recall,
                    "f1": result.f1,
                    "leakage": sorted(result.leakage),
                    "exact_hit": result.exact_hit,
                    "transcript": result.transcript,
                })
                print(
                    f"{result.name:>14} | predicted={sorted(result.concepts)} "
                    f"| P={result.precision:.3f} R={result.recall:.3f} F1={result.f1:.3f} "
                    f"| exact={result.exact_hit} | leakage={sorted(result.leakage)}"
                )

    print("\n=== Summary ===")
    for method_name, _ in methods:
        avg_f1 = sum(per_method_f1[method_name]) / len(per_method_f1[method_name])
        distinctiveness_scores = [
            1.0 - avg_pairwise_jaccard(per_method_run_sets[method_name][run_idx])
            for run_idx in range(1, runs + 1)
        ]
        distinctiveness = sum(distinctiveness_scores) / len(distinctiveness_scores)
        exact_rate = per_method_exact[method_name] / (runs * len(profiles))
        print(
            f"{method_name:>14} | avg_f1={avg_f1:.3f} "
            f"| exact_rate={exact_rate:.3f} | distinctiveness={distinctiveness:.3f}"
        )

    report_path = write_report(report_rows)
    print(f"\nReport: {report_path}")

if __name__ == "__main__":
    main()
