from metaLoop.metamodeling_agent import MetamodelingAgent
import sys


def ask_human_validation(payload: dict) -> bool:
    print("\n--- Concept ---")
    print(payload.get("concept", ""))
    print("\n--- Chunk ---")
    print(payload.get("chunk", ""))
    print("\n--- Sample Model ---")
    print(payload.get("sample_model", ""))
    print("\n--- Auto Validation ---")
    print(payload.get("validation", {}))
    answer = input("\nApprove this chunk? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip() or input("Prompt: ").strip()
    if not prompt:
        print("No prompt provided.")
        return

    agent = MetamodelingAgent()
    result = agent.run_iterative(prompt, human_validator=ask_human_validation)

    print("\n=== Concepts ===")
    print(result.get("concepts", []))
    print("\n=== Added Functionalities ===")
    print(result.get("added_functionalities", []))
    print("\n=== Final Metamodel ===")
    print(result.get("final_metamodel", ""))


if __name__ == "__main__":
    main()