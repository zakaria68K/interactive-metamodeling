from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .state import State


def generate_chunk(state: State, invoke_text: Callable[[str], str]) -> State:
    concepts = state.get("concepts", [])
    idx = state.get("current_index", 0)
    if idx >= len(concepts):
        return {
            "done": True,
            "final_metamodel": "\n\n".join(state.get("approved_chunks", [])),
        }

    concept = concepts[idx]
    approved_chunks = "\n\n".join(state.get("approved_chunks", [])) or "(none)"
    feedback = ""
    if state.get("current_validation") and not state.get("current_validation", {}).get("valid"):
        issues = state["current_validation"].get("issues", [])
        suggestion = state["current_validation"].get("suggestion", "")
        feedback = (
            f"\n\nPrevious validation feedback:\n"
            f"Issues: {', '.join(issues)}\n"
            f"Suggestion: {suggestion}"
        )

    chunk = invoke_text(
        f"Generate the next JjScript chunk for the concept below.{feedback}"
        "Output code only, no markdown or explanations.\n\n"
        f"Intent: {state.get('intent_summary', '')}\n"
        f"Concept: {concept}\n"
        f"Approved chunks so far:\n{approved_chunks}"
    )
    return {"current_concept": concept, "current_chunk": chunk}


def build_sample_model(state: State, invoke_text: Callable[[str], str]) -> str:
    return invoke_text(
        "Write one compact plain-text sample model instance that this concept should represent. "
        "This should challenge the model's understanding and cover edge cases.\n\n"
        f"Concept:\n{state.get('current_concept', '')}"
    )


def validate_chunk(state: State, sample_model: str, invoke_json: Callable[[str], dict]) -> dict:
    return invoke_json(
        "Does this chunk correctly cover the concept and represent the sample model?\n\n"
        "Reply with raw JSON only, no markdown, no extra text. Keys: "
        "valid (bool), issues (array of strings), suggestion (string).\n\n"
        f"Concept: {state.get('current_concept', '')}\n"
        f"Sample model:\n{sample_model}\n"
        f"Chunk:\n{state.get('current_chunk', '')}"
    )


def parallel_validate(
    state: State,
    invoke_text: Callable[[str], str],
    invoke_json: Callable[[str], dict],
    validator_invoke_text: Callable[[str], str] | None = None,
    validator_invoke_json: Callable[[str], dict] | None = None,
) -> State:
    validation_text = validator_invoke_text or invoke_text
    validation_json = validator_invoke_json or invoke_json
    with ThreadPoolExecutor(max_workers=2) as executor:
        sample_model = executor.submit(build_sample_model, state, validation_text).result()
        validation = executor.submit(validate_chunk, state, sample_model, validation_json).result()
    return {"current_sample_model": sample_model, "current_validation": validation}


def human_validate(state: State, human_validator: Callable[[dict], bool] | None) -> State:
    payload = {
        "concept": state.get("current_concept", ""),
        "chunk": state.get("current_chunk", ""),
        "sample_model": state.get("current_sample_model", ""),
        "validation": state.get("current_validation", {}),
    }
    approved = human_validator(payload) if human_validator else True
    return {"human_approved": approved}


def advance(state: State) -> State:
    max_retries = 3
    valid = bool(state.get("current_validation", {}).get("valid", False))
    human_approved = bool(state.get("human_approved", False))
    if human_approved and valid:
        approved_chunks = [*state.get("approved_chunks", []), state.get("current_chunk", "")]
        next_idx = state.get("current_index", 0) + 1
        done = next_idx >= len(state.get("concepts", []))
        return {
            "approved_chunks": approved_chunks,
            "current_index": next_idx,
            "concept_retry_count": 0,
            "done": done,
            "final_metamodel": "\n\n".join(approved_chunks) if done else "",
        }

    retry_count = state.get("concept_retry_count", 0) + 1
    if retry_count >= max_retries:
        concept = state.get("current_concept", "")
        print(f"Concept '{concept}' failed after {max_retries} retries, skipping it.")
        next_idx = state.get("current_index", 0) + 1
        done = next_idx >= len(state.get("concepts", []))
        return {
            "current_index": next_idx,
            "concept_retry_count": 0,
            "done": done,
            "final_metamodel": "\n\n".join(state.get("approved_chunks", [])) if done else "",
        }

    return {"concept_retry_count": retry_count}


def router(state: State) -> str:
    return "end" if state.get("done", False) else "next"


def reconcile_metamodel(state: State, invoke_text: Callable[[str], str]) -> State:
    chunks = state.get("approved_chunks", [])
    if not chunks:
        return {"final_metamodel": ""}
    combined = "\n\n".join(chunks)
    reconciled = invoke_text(
        "Below are independently generated metamodel chunks for the same domain.\n"
        "Reconcile them into one coherent metamodel:\n"
        "1. Resolve any contradictions between chunks.\n"
        "2. Merge duplicate or overlapping abstractions.\n"
        "3. Normalize all naming (PascalCase for classes, camelCase for attributes/references).\n"
        "Output JjScript only, no markdown or explanations.\n\n"
        f"Intent: {state.get('intent_summary', '')}\n\n"
        f"Chunks:\n{combined}"
    )
    return {"final_metamodel": reconciled}
