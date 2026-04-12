from typing import Callable

from .state import State


def gather_intent(state: State) -> State:
    return {"intent_summary": state.get("user_prompt", "")}


def knowledge_elicitation(state: State, invoke_json: Callable[[str], dict]) -> State:
    intent = state.get("intent_summary", "")
    familiar_answer = input("Are you familiar with the domain concepts? [y/N]: ").strip().lower()
    user_familiar = familiar_answer in {"y", "yes"}

    if not user_familiar:
        background = input("What do you already know about this domain (or type 'nothing')? ").strip()
        base_prompt = (
            f"The user is not familiar with this domain. Their background: {background or 'nothing'}.\n"
            "Propose 2 core metamodel concepts using plain, everyday language -- no jargon. "
            "For each concept add a simple one-sentence explanation a non-expert can understand.\n"
            "Reply with raw JSON only with key: concepts "
            "(array of objects, each with 'name' (string) and 'description' (string)).\n\n"
            f"Request:\n{intent}"
        )
    else:
        base_prompt = (
            "Propose 2 core metamodel concepts for the request below. "
            "Reply with raw JSON only with key: concepts (array of strings).\n\n"
            f"Request:\n{intent}"
        )

    concepts: list[str] = []
    for _ in range(3):
        parsed = invoke_json(base_prompt)
        raw = parsed.get("concepts", [])
        if not user_familiar:
            concepts = [c["name"].strip() for c in raw if isinstance(c, dict) and c.get("name", "").strip()]
            if not concepts:
                break
            print("\nLLM suggested concepts:")
            for i, c in enumerate(raw, start=1):
                print(f"{i}. {c.get('name', '')}")
                if c.get("description"):
                    print(f"  {c['description']}")
        else:
            concepts = [c.strip() for c in raw if str(c).strip()]
            if not concepts:
                break
            print("\nLLM suggested concepts:")
            for i, c in enumerate(concepts, start=1):
                print(f"  {i}. {c}")

        ok = input("Do you agree with these concepts? [Y/n]: ").strip().lower()
        if ok in {"", "y", "yes"}:
            return {"user_familiar": user_familiar, "concepts": concepts}
        feedback = input("What should be changed? ").strip()
        if not user_familiar:
            base_prompt = (
                "Revise the concept list based on this user feedback. "
                "Keep plain, non-technical language and include a one-sentence description per concept. "
                "Reply with raw JSON only with key: concepts "
                "(array of objects with 'name' and 'description').\n\n"
                f"Request:\n{intent}\n\nCurrent concepts: {concepts}\nUser feedback: {feedback}"
            )
        else:
            base_prompt = (
                "Revise the concept list based on this user feedback. "
                "Reply with raw JSON only with key: concepts (array of strings).\n\n"
                f"Request:\n{intent}\n\nCurrent concepts: {concepts}\nUser feedback: {feedback}"
            )

    return {"user_familiar": user_familiar, "concepts": concepts or [intent]}


def decompose_concepts(state: State, invoke_json: Callable[[str], dict]) -> State:
    if state.get("concepts"):
        return {
            "concepts": state.get("concepts", []),
            "added_functionalities": state.get("added_functionalities", []),
            "current_index": 0,
            "concept_retry_count": 0,
            "approved_chunks": [],
            "done": False,
        }

    parsed = invoke_json(
        "Decompose this request into 2 core metamodel concepts and identify any missing "
        "essential functionalities.\n\n"
        "Reply with raw JSON ONLY, no markdown, no extra text. Keys: "
        "intent_summary (string), concepts (array of strings), added_functionalities (array of strings).\n\n"
        f"Request:\n{state.get('intent_summary', '')}"
    )
    concepts = [c.strip() for c in parsed.get("concepts", []) if str(c).strip()]
    print("\n=== Concepts ===")
    for c in concepts:
        print(f"  - {c}")
    if not concepts:
        concepts = [state.get("intent_summary", "")]
    return {
        "intent_summary": parsed.get("intent_summary", state.get("intent_summary", "")),
        "concepts": concepts,
        "added_functionalities": parsed.get("added_functionalities", []),
        "current_index": 0,
        "concept_retry_count": 0,
        "approved_chunks": [],
        "done": False,
    }
