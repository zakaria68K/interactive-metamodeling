from typing import TypedDict


class State(TypedDict):
    user_prompt: str
    user_familiar: bool
    intent_summary: str
    concepts: list[str]
    added_functionalities: list[str]
    current_index: int
    concept_retry_count: int
    current_concept: str
    current_chunk: str
    current_sample_model: str
    current_validation: dict
    human_approved: bool
    approved_chunks: list[str]
    final_metamodel: str
    done: bool
