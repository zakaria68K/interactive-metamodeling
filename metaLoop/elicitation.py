from typing import Callable

from .state import State

# Depending on the LLM used, the JSON can be malformed, which may cause the proposed concepts section to be skipped.

def gather_intent(state: State) -> State:
    return {"intent_summary": state.get("user_prompt", "")}


def _ask_user(
    prompt: str,
    context: dict,
    responder: Callable[[str, dict], str] | None,
) -> str:
    if responder is None:
        return input(prompt).strip()
    answer = responder(prompt, context)
    return str(answer).strip()


def knowledge_elicitation(
    state: State,
    invoke_json: Callable[[str], dict],
    ask_user: Callable[[str, dict], str] | None = None,
) -> State:
    intent = state.get("intent_summary", "")
    familiar_answer = _ask_user(
        "Are you familiar with the domain concepts? [y/N]: ",
        {"intent": intent, "stage": "familiarity"},
        ask_user,
    ).lower()
    user_familiar = familiar_answer in {"y", "yes"}

    if not user_familiar:
        background = _ask_user(
            "What do you already know about this domain (or type 'nothing')? ",
            {"intent": intent, "stage": "background", "user_familiar": user_familiar},
            ask_user,
        )
        base_prompt = (
            f"The user is not familiar with this domain. Their background: {background or 'nothing'}.\n"
            "Propose 2 core metamodel concepts using plain, everyday language -- no jargon. "
            "For each concept add a simple one-sentence explanation a non-expert can understand.\n"
            "Concept names must be singular with first letter uppercase (e.g., State, Transition).\n"
            "Reply with raw JSON only with key: concepts "
            "(array of objects, each with 'name' (string) and 'description' (string)).\n\n"
            f"Request:\n{intent}"
        )
    else:
        base_prompt = (
            "Propose 2 core metamodel concepts for the request below. "
            "Concept names must be singular with first letter uppercase (e.g., State, Transition). "
            "Reply with raw JSON only with key: concepts (array of strings).\n\n"
            f"Request:\n{intent}"
        )

    concepts: list[str] = []
    for attempt in range(3):
        parsed = invoke_json(base_prompt)
        raw = parsed.get("concepts", [])
        if not user_familiar:
            concepts = [c["name"].strip() for c in raw if isinstance(c, dict) and c.get("name", "").strip()]
            if not concepts:
                continue
        else:
            concepts = [c.strip() for c in raw if str(c).strip()]
            if not concepts:
                continue

        ok = _ask_user(
            "Do you agree with these concepts? [Y/n]: ",
            {
                "intent": intent,
                "stage": "agreement",
                "user_familiar": user_familiar,
                "proposed_concepts": concepts,
                "proposed_concepts_raw": raw if not user_familiar else None,
            },
            ask_user,
        ).lower()
        if ok in {"", "y", "yes"}:
            return {"user_familiar": user_familiar, "concepts": concepts}
        feedback = _ask_user(
            "What should be changed? ",
            {
                "intent": intent,
                "stage": "feedback",
                "user_familiar": user_familiar,
                "proposed_concepts": concepts,
            },
            ask_user,
        )
        if not user_familiar:
            base_prompt = (
                "Revise the concept list based on this user feedback. "
                "Keep plain, non-technical language and include a one-sentence description per concept. "
                "Concept names must be singular with first letter uppercase (e.g., State, Transition). "
                "Reply with raw JSON only with key: concepts "
                "(array of objects with 'name' and 'description').\n\n"
                f"Request:\n{intent}\n\nCurrent concepts: {concepts}\nUser feedback: {feedback}"
            )
        else:
            base_prompt = (
                "Revise the concept list based on this user feedback. "
                "Concept names must be singular with first letter uppercase (e.g., State, Transition). "
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
            "cumulative_sample_model": "",
            "done": False,
        }

    parsed = invoke_json(
        "Decompose this request into 2 core metamodel concepts and identify any missing "
        "essential functionalities.\n\n"
        "Concept names must be singular with first letter uppercase (e.g., State, Transition).\n"
        "Reply with raw JSON ONLY, no markdown, no extra text. Keys: "
        "intent_summary (string), concepts (array of strings), added_functionalities (array of strings).\n\n"
        f"Request:\n{state.get('intent_summary', '')}"
    )
    concepts = [c.strip() for c in parsed.get("concepts", []) if str(c).strip()]
    if not concepts:
        concepts = [state.get("intent_summary", "")]
    return {
        "intent_summary": parsed.get("intent_summary", state.get("intent_summary", "")),
        "concepts": concepts,
        "added_functionalities": parsed.get("added_functionalities", []),
        "current_index": 0,
        "concept_retry_count": 0,
        "approved_chunks": [],
        "cumulative_sample_model": "",
        "done": False,
    }
