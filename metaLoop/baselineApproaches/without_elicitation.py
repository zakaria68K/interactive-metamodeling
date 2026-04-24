import sys
from pathlib import Path
from typing import Callable

from langgraph.graph import END, START, StateGraph


sys.path.append(str(Path(__file__).resolve().parents[2]))
from metaLoop.elicitation import decompose_concepts, gather_intent
from metaLoop.generation import advance, dual_validation, generate_chunk, human_validate, router
from metaLoop.llm_client import LLMClient
from metaLoop.state import State


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


class NoElicitationAgent:
    def __init__(self):
        self.llm_client = LLMClient()
        self._human_validator: Callable[[dict], bool] | None = None

    def run(self, user_prompt: str, human_validator: Callable[[dict], bool] | None = None) -> dict:
        self._human_validator = human_validator
        lc, hv = self.llm_client, self._human_validator
        builder = StateGraph(State)
        builder.add_node("gather_intent",      gather_intent)
        builder.add_node("decompose_concepts", lambda s: decompose_concepts(s, lc.invoke_json))
        builder.add_node("generate_chunk",     lambda s: generate_chunk(s, lc.invoke_text))
        builder.add_node("dual_validation",    lambda s: dual_validation(s, lc.invoke_text, lc.invoke_json))
        builder.add_node("human_validate",     lambda s: human_validate(s, hv))
        builder.add_node("advance",            advance)
        builder.add_edge(START,                "gather_intent")
        builder.add_edge("gather_intent",      "decompose_concepts")
        builder.add_edge("decompose_concepts", "generate_chunk")
        builder.add_edge("generate_chunk",     "dual_validation")
        builder.add_edge("dual_validation",    "human_validate")
        builder.add_edge("human_validate",     "advance")
        builder.add_conditional_edges("advance", router, {"next": "generate_chunk", "end": END})
        return builder.compile().invoke({"user_prompt": user_prompt})


def main() -> None:
    user_prompt = " ".join(sys.argv[1:]).strip() or input("Prompt: ").strip()
    if not user_prompt:
        print("No prompt provided.")
        return

    agent = NoElicitationAgent()
    result = agent.run(user_prompt, human_validator=ask_human_validation)

    print("\n=== Concepts ===")
    print(result.get("concepts", []))
    print("\n=== Added Functionalities ===")
    print(result.get("added_functionalities", []))
    print("\n=== Final Metamodel ===")
    print(result.get("final_metamodel", ""))


if __name__ == "__main__":
    main()
