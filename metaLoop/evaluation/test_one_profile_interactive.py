from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


from metaLoop.baselineApproaches.direct_generation import generate_direct
from metaLoop.elicitation import decompose_concepts, gather_intent
from metaLoop.evaluation.llm_extractor import ConceptExtractor
from metaLoop.evaluation.user_simulator import ProfileUserLLM, SimulatedUserProfile
from metaLoop.metamodeling_agent import MetamodelingAgent


def normalize(items: list[str]) -> set[str]:
    return {item.strip().lower() for item in items if item and item.strip()}


def precision_recall_f1(expected: set[str], predicted: set[str]) -> tuple[float, float, float]:
    tp = len(expected & predicted)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


def print_score(name: str, target: set[str], predicted: set[str]) -> None:
    precision, recall, f1 = precision_recall_f1(target, predicted)
    extras = sorted(predicted - target)
    missing = sorted(target - predicted)
    print(name)
    print("predicted:", sorted(predicted))
    print(f"precision: {precision:.3f}")
    print(f"recall: {recall:.3f}")
    print(f"f1: {f1:.3f}")
    print("exact_hit:", predicted == target)
    print("missing:", missing)
    print("extras:", extras)
    print()


def main() -> None:
    profile = SimulatedUserProfile(
        profile_id="user_a_event_driven",
        prompt="I want a state machine metamodel for interactive applications.",
        goal="Focus on event-driven behavior. The essential concepts are State and Event.",
        target_concepts=["State", "Event"],
    )

    user = ProfileUserLLM(profile)
    agent = MetamodelingAgent()
    extractor = ConceptExtractor()
    transcript: list[dict[str, str]] = []
    reviews: list[dict[str, str | bool]] = []

    def traced_responder(prompt: str, context: dict) -> str:
        if context.get("validation_stage") == "challenge_selection":
            answer = "moderate"
        else:
            answer = user.respond(prompt, context)
        transcript.append(
            {
                "stage": context.get("stage") or context.get("validation_stage", ""),
                "question": prompt,
                "answer": answer,
            }
        )
        return answer

    def auto_approve(payload: dict) -> bool:
        approved = bool(payload.get("validation", {}).get("valid", False))
        reviews.append(
            {
                "concept": payload.get("concept", ""),
                "validation": str(payload.get("validation", {})),
                "approved": approved,
            }
        )
        return approved

    result = agent.run_iterative(
        profile.prompt,
        human_validator=auto_approve,
        user_responder=traced_responder,
        initial_state={"skip_isolated_validation": True},
    )

    interactive_predicted = normalize(result.get("concepts", []))
    target = normalize(profile.target_concepts)

    # Simulate the baseline where the system sees only the prompt and never interacts with the user
    no_elicitation_state = {"user_prompt": profile.prompt}
    no_elicitation_state.update(gather_intent(no_elicitation_state))
    no_elicitation_state.update(decompose_concepts(no_elicitation_state, agent.llm_client.invoke_json))
    no_elicitation_predicted = normalize(no_elicitation_state.get("concepts", []))

    # One-shot baseline
    one_shot_text = generate_direct(profile.prompt)
    one_shot_predicted = normalize(extractor.extract(profile.prompt, one_shot_text).get("concepts", []))

    print("=== Full Interactive System Test ===")
    print("profile:", profile.profile_id)
    print("final_concepts:", result.get("concepts", []))
    print("user_familiar:", result.get("user_familiar"))
    print("final_metamodel:")
    print(result.get("final_metamodel", ""))
    print()
    print("=== Transcript ===")
    for turn in transcript:
        print(f"[{turn['stage']}] Q: {turn['question']}")
        print(f"[{turn['stage']}] A: {turn['answer']}")
        print()
    print("=== Auto Approvals ===")
    for review in reviews:
        print("concept:", review["concept"])
        print("approved:", review["approved"])
        print("validation:", review["validation"])
        print()

    print("=== Concept Score Comparison ===")
    print("target:", sorted(target))
    print()
    print_score("interactive_full", target, interactive_predicted)
    print_score("no_elicitation", target, no_elicitation_predicted)
    print_score("one_shot", target, one_shot_predicted)


if __name__ == "__main__":
    main()