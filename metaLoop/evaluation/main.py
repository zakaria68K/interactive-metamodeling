from dataclasses import dataclass
import builtins
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import List, Set

sys.path.append(str(Path(__file__).resolve().parents[2]))

from user_protocols import ScriptedUserProtocol, UserTurnPolicy, contains_gold_leakage
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


def auto_human_validation(_: dict) -> bool:
    return True

# Simulating user interaction
@contextmanager
def patched_input(answers: List[str]):
    original_input = builtins.input
    queue = answers.copy()

    def _fake_input(prompt: str = "") -> str:
        if queue:
            ans = queue.pop(0)
            print(f"{prompt}{ans}")
            return ans
        print(f"{prompt}")
        return ""

    builtins.input = _fake_input
    try:
        yield
    finally:
        builtins.input = original_input

# Converts one UserTurnPolicy into the exact answer sequence expected by the interactive flow.
def build_answers(policy: UserTurnPolicy) -> List[str]:
    answers = ["y" if policy.familiar else "n"]
    if not policy.familiar:
        answers.append(policy.background)
    # First concept agreement answer.
    answers.append("y" if policy.agree else "n")
    if not policy.agree:
        answers.append(policy.feedback)
        # Second agreement after revision.
        answers.append("y")
    return answers


def main() -> None:
    dataset = [
        EvalItem(
            item_id="item_1",
            metamodel="state machines",
            expected_concepts=["transitions", "states"]
        )
    ]

    # Fixed per-prompt user behavior for reproducible evaluation
    scripted_user = ScriptedUserProtocol(
        {
            "item_1": UserTurnPolicy(
                familiar=False,
                background="I only know high-level behavior.",
                agree=True,
                feedback="",
            )
        }
    )

    agent = MetamodelingAgent()

    for item in dataset:
        policy = scripted_user.get(item.item_id)
        leak = contains_gold_leakage(
            policy.background + " " + policy.feedback,
            item.expected_concepts
        )

        answers = build_answers(policy)
        with patched_input(answers):
            result = agent.run_iterative(item.metamodel, human_validator=auto_human_validation)

        expected_concepts = normalize(item.expected_concepts)

        predicted_concepts = normalize(result.get("concepts", []))

        c_precision, c_recall, c_f1 = precision_recall_f1(expected_concepts, predicted_concepts)

        print(f"\n=== Evaluation: {item.item_id} ({item.metamodel}) ===")
        print(f"Leakage detected: {leak}")
        print(f"Predicted concepts: {sorted(predicted_concepts)}")
        print("\nConcept metrics")
        print(f"  Precision: {c_precision:.3f}")
        print(f"  Recall:    {c_recall:.3f}")
        print(f"  F1:        {c_f1:.3f}")

if __name__ == "__main__":
    main()
