import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable, List, Set

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
from pypdf import PdfReader
from metaLoop.baselineApproaches.direct_generation import generate_direct
from metaLoop.elicitation import decompose_concepts, gather_intent
from metaLoop.evaluation.llm_extractor import ConceptExtractor
from metaLoop.evaluation.user_simulator import ProfileUserLLM, SimulatedUserProfile
from metaLoop.metamodeling_agent import MetamodelingAgent


GENERATED_SAMPLE_DIR = ROOT / "metaLoop" / "evaluation" / "sample_files" / "generated"

DOMAIN_CONFIGS = {
    "state_machine": {
        "prompt": "I want a state machine metamodel for interactive applications.",
        "users": [
            ("events", ["State", "Event", "Transition", "Trigger", "StateMachine"]),
            ("transitions", ["State", "Transition", "Guard", "Action", "Event"]),
            ("start_end", ["InitialState", "FinalState", "State", "Transition", "StateMachine"]),
            ("workflow_container", ["StateMachine", "State", "Transition", "Region", "Event"]),
            ("triggering", ["Trigger", "Event", "Transition", "State", "Guard"]),
            ("behavior", ["Action", "Transition", "Event", "State", "Guard"]),
            ("conditions", ["Guard", "Transition", "State", "Event", "Action"]),
            ("hierarchy", ["Region", "State", "StateMachine", "Transition", "Event"]),
            ("navigation", ["State", "Trigger", "Transition", "Action", "FinalState"]),
            ("teaching", ["State", "InitialState", "FinalState", "Transition", "Event"]),
        ],
    },
    "university": {
        "prompt": "I want a university course management metamodel.",
        "users": [
            ("enrollment", ["Student", "Enrollment", "Course", "Semester", "Program"]),
            ("teaching", ["Professor", "Course", "Department", "Classroom", "Semester"]),
            ("programs", ["Program", "Student", "Course", "Department", "Professor"]),
            ("departments", ["Department", "Professor", "Course", "Semester", "Classroom"]),
            ("grading", ["Grade", "Assignment", "Student", "Course", "Professor"]),
            ("semester_planning", ["Semester", "Course", "Classroom", "Professor", "Department"]),
            ("classrooms", ["Classroom", "Course", "Semester", "Professor", "Student"]),
            ("course_progress", ["Student", "Assignment", "Grade", "Course", "Program"]),
            ("offerings", ["Department", "Course", "Semester", "Professor", "Enrollment"]),
            ("advising", ["Student", "Program", "Professor", "Course", "Grade"]),
        ],
    },
    "library": {
        "prompt": "I want a library lending metamodel.",
        "users": [
            ("borrowing", ["Member", "Loan", "Book", "Copy", "Fine"]),
            ("catalog", ["Book", "Category", "Author", "Copy", "Library"]),
            ("authors", ["Book", "Author", "Category", "Library", "Copy"]),
            ("returns", ["Loan", "Fine", "Book", "Member", "Librarian"]),
            ("reservations", ["Reservation", "Member", "Book", "Copy", "Librarian"]),
            ("staff", ["Librarian", "Library", "Member", "Loan", "Reservation"]),
            ("copies", ["Copy", "Book", "Category", "Library", "Loan"]),
            ("availability", ["Book", "Copy", "Loan", "Member", "Reservation"]),
            ("membership", ["Member", "Library", "Loan", "Fine", "Reservation"]),
            ("circulation", ["Book", "Member", "Loan", "Copy", "Librarian"]),
        ],
    },
    "hospital": {
        "prompt": "I want a hospital appointment management metamodel.",
        "users": [
            ("appointments", ["Patient", "Appointment", "Doctor", "Department", "MedicalRecord"]),
            ("doctors", ["Doctor", "Appointment", "Department", "Patient", "Diagnosis"]),
            ("departments", ["Department", "Doctor", "Appointment", "Room", "Nurse"]),
            ("records", ["Patient", "MedicalRecord", "Diagnosis", "Prescription", "Treatment"]),
            ("prescriptions", ["Prescription", "Patient", "Doctor", "Appointment", "MedicalRecord"]),
            ("treatments", ["Treatment", "Diagnosis", "Patient", "Doctor", "Room"]),
            ("rooms", ["Room", "Patient", "Nurse", "Appointment", "Treatment"]),
            ("nursing", ["Nurse", "Patient", "Room", "Treatment", "MedicalRecord"]),
            ("consultations", ["Doctor", "Diagnosis", "Appointment", "Patient", "Prescription"]),
            ("care_flow", ["Patient", "Appointment", "Prescription", "Treatment", "MedicalRecord"]),
        ],
    },
    "ecommerce": {
        "prompt": "I want an e-commerce order management metamodel.",
        "users": [
            ("orders", ["Order", "Product", "Customer", "OrderItem", "Payment"]),
            ("shipping", ["Order", "Shipment", "Address", "Customer", "Inventory"]),
            ("payments", ["Order", "Payment", "Customer", "Product", "OrderItem"]),
            ("customers", ["Customer", "Address", "Cart", "Order", "Payment"]),
            ("catalog", ["Product", "Category", "Inventory", "Cart", "OrderItem"]),
            ("cart", ["Cart", "Product", "Customer", "OrderItem", "Order"]),
            ("line_items", ["Order", "OrderItem", "Product", "Payment", "Shipment"]),
            ("stock", ["Inventory", "Product", "Category", "OrderItem", "Shipment"]),
            ("checkout", ["Customer", "Cart", "Payment", "Order", "Address"]),
            ("fulfillment", ["Order", "Shipment", "Inventory", "Product", "OrderItem"]),
        ],
    },
}


@dataclass
class MethodResult:
    name: str
    initial_concepts: Set[str]
    final_concepts: Set[str]
    initial_precision: float
    initial_recall: float
    initial_f1: float
    precision: float
    recall: float
    f1: float
    initial_transcript: list[dict[str, str]]
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


def evaluate_prediction(target: Set[str], predicted: Set[str]) -> tuple[float, float, float]:
    precision, recall, f1 = precision_recall_f1(target, predicted)
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





def run_interactive(agent: MetamodelingAgent, profile: SimulatedUserProfile, ) -> MethodResult:
    initial_user_llm = ProfileUserLLM(profile)
    initial_state = agent.run_concepts_only(
        profile.prompt,
        user_responder=initial_user_llm.respond,
    )
    initial_concepts = normalize(initial_state.get("concepts", []))
    initial_precision, initial_recall, initial_f1 = evaluate_prediction(
        normalize(profile.target_concepts), initial_concepts
    )

    user_llm = ProfileUserLLM(profile)
    result = agent.run_iterative(
        profile.prompt,
        human_validator=lambda _: True,
        user_responder=user_llm.respond,
        initial_state={
            "attached_file_content": read_sample_file(profile.sample_file_path),
            "skip_isolated_validation": True,
        },
    )
    final_concepts = normalize(result.get("concepts", []))
    precision, recall, f1 = evaluate_prediction(normalize(profile.target_concepts), final_concepts)
    return MethodResult(
        "interactive",
        initial_concepts,
        final_concepts,
        initial_precision,
        initial_recall,
        initial_f1,
        precision,
        recall,
        f1,
        list(initial_user_llm.history),
        list(user_llm.history),
    )


def run_no_elicitation(agent: MetamodelingAgent, profile: SimulatedUserProfile) -> MethodResult:
    state = {"user_prompt": profile.prompt}
    state.update(gather_intent(state))
    state.update(decompose_concepts(state, agent.llm_client.invoke_json))
    predicted = normalize(state.get("concepts", []))
    precision, recall, f1 = evaluate_prediction(normalize(profile.target_concepts), predicted)
    transcript = [{"stage": "prompt", "question": profile.prompt, "answer": ""}]
    return MethodResult(
        "no_elicitation",
        predicted,
        predicted,
        precision,
        recall,
        f1,
        precision,
        recall,
        f1,
        transcript,
        transcript,
    )


def run_one_shot(extractor: ConceptExtractor, profile: SimulatedUserProfile) -> MethodResult:
    metamodel_text = generate_direct(profile.prompt)
    extracted = extractor.extract(profile.prompt, metamodel_text)
    predicted = normalize(extracted.get("concepts", []))
    precision, recall, f1 = evaluate_prediction(normalize(profile.target_concepts), predicted)
    transcript = [{"stage": "prompt", "question": profile.prompt, "answer": metamodel_text}]
    return MethodResult(
        "one_shot",
        predicted,
        predicted,
        precision,
        recall,
        f1,
        precision,
        recall,
        f1,
        transcript,
        transcript,
    )


def write_report(rows: list[dict]) -> Path:
    out_dir = ROOT / "metaLoop" / "evaluation" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "concept_eval_report.json"
    report_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return report_path


def build_profiles() -> list[SimulatedUserProfile]:
    profiles: list[SimulatedUserProfile] = []
    for domain_name, config in DOMAIN_CONFIGS.items():
        for index, (suffix, target_concepts) in enumerate(config["users"], start=1):
            sample_path = GENERATED_SAMPLE_DIR / f"{domain_name}_{suffix}.md"
            profiles.append(
                SimulatedUserProfile(
                    profile_id=f"{domain_name}_user_{index:02d}_{suffix}",
                    prompt=config["prompt"],
                    target_concepts=target_concepts,
                    sample_file_path=str(sample_path.relative_to(ROOT)),
                )
            )
    return profiles


def main() -> None:
    runs = int(os.getenv("EVAL_RUNS", "1"))
    profiles = build_profiles()

    agent = MetamodelingAgent()
    extractor = ConceptExtractor()

    methods: List[tuple[str, Callable[[SimulatedUserProfile], MethodResult]]] = [
        ("interactive", lambda profile: run_interactive(agent, profile)),
        ("no_elicitation", lambda profile: run_no_elicitation(agent, profile)),
        ("one_shot", lambda profile: run_one_shot(extractor, profile)),
    ]

    per_method_metrics: dict[str, dict[str, List[float]]] = {
        name: {"initial_f1": [], "final_f1": []} for name, _ in methods
    }
    report_rows: list[dict] = []

    for run_idx in range(1, runs + 1):
        print(f"\n=== Run {run_idx} ===")
        for profile in profiles:
            print(f"\n{profile.profile_id}")
            print(f"Target: {sorted(normalize(profile.target_concepts))}")
            print(f"Sample file: {profile.sample_file_path or '(none)'}")
            for method_name, runner in methods:
                result = runner(profile)
                per_method_metrics[method_name]["initial_f1"].append(result.initial_f1)
                per_method_metrics[method_name]["final_f1"].append(result.f1)
                report_rows.append({
                    "run": run_idx,
                    "profile_id": profile.profile_id,
                    "sample_file_path": profile.sample_file_path,
                    "method": result.name,
                    "target": sorted(normalize(profile.target_concepts)),
                    "initial_proposed_concepts": sorted(result.initial_concepts),
                    "final_concepts": sorted(result.final_concepts),
                    "predicted": sorted(result.final_concepts),
                    "initial_precision": result.initial_precision,
                    "initial_recall": result.initial_recall,
                    "initial_f1": result.initial_f1,
                    "precision": result.precision,
                    "recall": result.recall,
                    "f1": result.f1,
                    "initial_transcript": result.initial_transcript,
                    "transcript": result.transcript,
                })
                print(
                    f"{result.name:>14} | initial={sorted(result.initial_concepts)} | final={sorted(result.final_concepts)} "
                    f"| initial F1={result.initial_f1:.3f} | final F1={result.f1:.3f}"
                )

    print("\n=== Summary ===")
    for method_name, _ in methods:
        avg_initial_f1 = sum(per_method_metrics[method_name]["initial_f1"]) / len(per_method_metrics[method_name]["initial_f1"])
        avg_final_f1 = sum(per_method_metrics[method_name]["final_f1"]) / len(per_method_metrics[method_name]["final_f1"])
        print(f"{method_name:>14} | avg_initial_f1={avg_initial_f1:.3f} | avg_final_f1={avg_final_f1:.3f}")

    report_path = write_report(report_rows)
    print(f"\nReport: {report_path}")

if __name__ == "__main__":
    main()
