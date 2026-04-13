from dataclasses import dataclass
from pathlib import Path
import sys
from typing import List, Set

sys.path.append(str(Path(__file__).resolve().parents[2]))

from user_protocols import contains_gold_leakage
from student_simulator import StudentRoleLLM
from metaLoop.metamodeling_agent import MetamodelingAgent


@dataclass
class EvalItem:
    item_id: str
    metamodel: str
    expected_concepts: List[str]


def normalize(items: List[str]) -> Set[str]:
    return {x.strip().lower() for x in items if x and x.strip()}

# When model predicts a concept, how often is it correct? How much of the required concepts did model recover 
def precision_recall_f1(expected: Set[str], predicted: Set[str]) -> tuple[float, float, float]:
    tp = len(expected & predicted)
    fp = len(predicted - expected)
    fn = len(expected - predicted)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


def main() -> None:
    dataset = [
        EvalItem(
            item_id="item_1",
            metamodel="Course management",
            expected_concepts=["Student", "Teacher", "Classroom", "Session", "Grade"],
        ),
        EvalItem(
            item_id="item_2",
            metamodel="Arithmetical language",
            expected_concepts=["Expression", "Value", "Operator", "Variable"],
        ),
        EvalItem(
            item_id="item_3",
            metamodel="Repair shop",
            expected_concepts=["Customer", "Device", "Issue", "Technician", "Spare part", "Invoice", "Warranty"],
        ),
        EvalItem(
            item_id="item_4",
            metamodel="Veterinary Clinic",
            expected_concepts=["Animal", "Client", "Practitioner", "Medical procedure", "Prescription", "Medicine", "Invoice"],
        ),
        EvalItem(
            item_id="item_5",
            metamodel="State machine",
            expected_concepts=["State", "Transition"],
        ),
    ]

    agent = MetamodelingAgent()

    for item in dataset:
        simulator = StudentRoleLLM(item.metamodel)
        result = agent.run_concepts_only(
            item.metamodel,
            user_responder=simulator.respond,
        )

        expected_concepts = normalize(item.expected_concepts)

        predicted_concepts = normalize(result.get("concepts", []))

        c_precision, c_recall, c_f1 = precision_recall_f1(expected_concepts, predicted_concepts)

        print(f"\n=== Evaluation: {item.item_id} ({item.metamodel}) ===")
        print(f"Predicted concepts: {sorted(predicted_concepts)}")
        print("\nConcept metrics")
        print(f"  Precision: {c_precision:.3f}")
        print(f"  Recall:    {c_recall:.3f}")
        print(f"  F1:        {c_f1:.3f}")

if __name__ == "__main__":
    main()
