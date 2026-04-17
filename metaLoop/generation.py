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
    approved_chunks = state.get("approved_chunks", [])
    approved_text = "\n\n".join(approved_chunks) if approved_chunks else "(none yet)"

    feedback = ""
    if state.get("current_validation") and not state.get("current_validation", {}).get("valid"):
        issues = state["current_validation"].get("issues", [])
        suggestion = state["current_validation"].get("suggestion", "")
        issues_text = "\n".join(f"  - {i}" for i in issues)
        feedback = (
            f"\n\nIMPORTANT — You MUST address this validation feedback from the previous attempt:\n"
            f"Issues found:\n{issues_text}\n"
            f"Suggested fix: {suggestion}\n"
        )

    prompt = (
        f"Generate a JjScript metamodel chunk ONLY for the concept: '{concept}'.\n\n"
        "STRICT SCOPE RULES:\n"
        f"- ONLY create classes, attributes, and references that directly belong to '{concept}'.\n"
        "- Do NOT add classes for other concepts — those will be handled in later iterations.\n"
        "- Do NOT anticipate future concepts or add extra classes 'for completeness'.\n"
        "- If approved chunks exist, you may add references FROM your new classes TO existing classes, "
        "but do NOT redefine or extend existing classes.\n\n"
    )
    if feedback:
        prompt += feedback + "\n\n"
    prompt += (
        "Use PascalCase for classes, camelCase for attributes/references.\n"
        "Output JjScript code only — no markdown fences, no explanations.\n\n"
        f"Domain intent: {state.get('intent_summary', '')}\n"
        f"Concept to implement: {concept}\n\n"
        f"Previously approved chunks:\n{approved_text}"
    )
    new_chunk = invoke_text(prompt)
    # The current_chunk is the CUMULATIVE metamodel: all approved + new
    if approved_chunks:
        cumulative = "\n\n".join([*approved_chunks, new_chunk])
    else:
        cumulative = new_chunk
    return {"current_concept": concept, "current_chunk": cumulative, "current_new_chunk": new_chunk}


def build_sample_model(state: State, invoke_text: Callable[[str], str]) -> str:
    """Generate a concrete sample model (M1) in JJScript that tests the cumulative metamodel."""
    approved = state.get("approved_chunks", [])
    current = state.get("current_chunk", "")
    cumulative_metamodel = "\n\n".join([*approved, current])

    concepts = state.get("concepts", [])
    idx = state.get("current_index", 0)
    covered_concepts = concepts[: idx + 1]

    prev_sample = state.get("cumulative_sample_model", "")

    prompt = (
        "Generate a CONCRETE SAMPLE MODEL in JJScript that tests the metamodel below.\n\n"
        "The sample model is an M1-level model — a specific example that conforms to the metamodel.\n"
        "For example, if the metamodel defines 'State' and 'Transition' metaclasses, "
        "the sample model should create concrete states like 'RedLight', 'GreenLight' "
        "and transitions like 'RedToGreen'.\n\n"
        "Use JJScript syntax: create class, create attribute, create reference, create containment.\n"
        "Give each class a concrete, domain-specific name (e.g., 'MathCourse' not 'Course1').\n"
        "Set attribute types to match the metamodel's attribute types.\n"
        "Create references between concrete classes matching the metamodel's references.\n"
        "Create 2-3 concrete instances per metaclass to test coverage.\n\n"
        "Output JJScript code only — no markdown fences, no explanations.\n\n"
    )

    if prev_sample:
        prompt += (
            "IMPORTANT: You must EXTEND the existing sample model below. "
            "Keep ALL existing classes/instances and ADD new ones for the newly added concept. "
            "Link new concrete classes to existing ones where the metamodel defines references.\n\n"
            f"Existing sample model to extend:\n{prev_sample}\n\n"
        )

    prompt += (
        f"Concepts covered so far: {', '.join(covered_concepts)}\n"
        f"Current concept being tested: {state.get('current_concept', '')}\n\n"
        f"Metamodel to test against:\n{cumulative_metamodel}"
    )

    return invoke_text(prompt)


def validate_chunk(state: State, sample_model: str, invoke_json: Callable[[str], dict]) -> dict:
    approved = state.get("approved_chunks", [])
    current = state.get("current_chunk", "")
    cumulative_metamodel = "\n\n".join([*approved, current])

    concepts = state.get("concepts", [])
    idx = state.get("current_index", 0)
    covered_concepts = concepts[: idx + 1]

    prev_validation = state.get("current_validation", {})
    prev_context = ""
    if prev_validation:
        prev_context = f"\nPrevious validation attempt:\n{prev_validation}\n"

    remaining_concepts = concepts[idx + 1:]
    remaining_note = ""
    if remaining_concepts:
        remaining_note = (
            f"\nUpcoming concepts (will be added later, do NOT penalize for their absence): "
            f"{', '.join(remaining_concepts)}\n"
        )

    return invoke_json(
        "Evaluate whether this metamodel chunk covers the BREADTH of the concept.\n\n"
        "The sample model shows diverse instances that COULD exist in this domain. "
        "Use it to check: does the chunk capture enough variety? "
        "Are there important aspects of the concept that the chunk cannot represent?\n\n"
        "Do NOT check conformance of the sample to the chunk. "
        "The sample is just a coverage probe — ignore minor mismatches.\n"
        "Mark as invalid ONLY if the chunk misses a major aspect of the concept.\n\n"
        "Reply with raw JSON only, no markdown. Keys: "
        "valid (bool), issues (array of strings), suggestion (string).\n\n"
        f"Current concept: {state.get('current_concept', '')}\n"
        f"{remaining_note}"
        f"Chunk:\n{current}\n\n"
        f"Sample instances (for coverage check only):\n{sample_model}"
        f"{prev_context}"
    )

def dual_validation(
    state: State,
    invoke_text: Callable[[str], str],
    invoke_json: Callable[[str], dict],
    validator_invoke_text: Callable[[str], str] | None = None,
    validator_invoke_json: Callable[[str], dict] | None = None,
) -> State:
    validation_text = validator_invoke_text or invoke_text
    validation_json = validator_invoke_json or invoke_json
    sample_model = build_sample_model(state, validation_text)
    validation = validate_chunk(state, sample_model, validation_json)
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
        approved_chunks = [*state.get("approved_chunks", []), state.get("current_new_chunk", state.get("current_chunk", ""))]
        next_idx = state.get("current_index", 0) + 1
        done = next_idx >= len(state.get("concepts", []))
        return {
            "approved_chunks": approved_chunks,
            "current_index": next_idx,
            "concept_retry_count": 0,
            "done": done,
            "cumulative_sample_model": state.get("current_sample_model", ""),
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

# Incremental chunking without robust global reconciliation can create contradictions across chunks, duplicate abstractions, and unstable naming semantics.
def reconcile_metamodel(state: State, invoke_text: Callable[[str], str], invoke_json: Callable[[str], dict] | None = None) -> State:
    chunks = state.get("approved_chunks", [])
    if not chunks:
        return {"final_metamodel": ""}
    combined = "\n\n".join(chunks)
    concepts = state.get("concepts", [])
    reconciled = invoke_text(
        "Below are incrementally generated metamodel chunks for the same domain.\n"
        "Reconcile them into one coherent metamodel:\n"
        "1. Resolve any contradictions between chunks.\n"
        "2. Merge duplicate or overlapping abstractions.\n"
        "3. Normalize all naming (PascalCase for classes, camelCase for attributes/references).\n"
        "4. Ensure all cross-references between concepts are present.\n"
        "Output JjScript only, no markdown or explanations.\n\n"
        f"Intent: {state.get('intent_summary', '')}\n"
        f"Concepts: {', '.join(concepts)}\n\n"
        f"Chunks:\n{combined}"
    )

    # Generate a final comprehensive sample model in JJScript
    final_sample = invoke_text(
        "Generate a comprehensive CONCRETE SAMPLE MODEL in JJScript for this final metamodel.\n\n"
        "The sample model is an M1-level model — a specific, realistic example that conforms to the metamodel.\n"
        "Use JJScript syntax: create class, create attribute, create reference, create containment.\n"
        "Give each class a concrete, domain-specific name (e.g., 'MathCourse' not 'Course1').\n"
        "Create 2-3 concrete instances per metaclass. Cover all references and test multiplicities.\n"
        "Output JJScript code only — no markdown, no explanations.\n\n"
        f"Concepts: {', '.join(concepts)}\n\n"
        f"Final metamodel:\n{reconciled}"
    )

    # Validate the final sample model against the final metamodel
    final_validation = {}
    if invoke_json:
        final_validation = invoke_json(
            "Evaluate whether this final metamodel covers all the concepts breadth.\n\n"
            "The sample model shows diverse instances across ALL concepts. "
            "Use it to check: does the metamodel capture enough variety for each concept? "
            "Are there important aspects that the metamodel cannot represent?\n\n"
            "Do NOT check strict conformance. The sample is a coverage probe.\n"
            "Mark as invalid ONLY if the metamodel misses a major aspect of a concept.\n\n"
            "Reply with raw JSON only, no markdown. Keys: "
            "valid (bool), issues (array of strings), suggestion (string).\n\n"
            f"Concepts: {', '.join(concepts)}\n\n"
            f"Final metamodel:\n{reconciled}\n\n"
            f"Sample model:\n{final_sample}"
        )

    return {"final_metamodel": reconciled, "cumulative_sample_model": final_sample, "final_validation": final_validation}
