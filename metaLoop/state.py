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
    current_new_chunk: str
    current_validated_chunk: str
    current_sample_model: str
    current_isolated_sample_model: str
    current_validation: dict
    current_isolated_validation: dict
    wants_isolated_validation: bool
    human_approved: bool
    approved_chunks: list[str]
    cumulative_sample_model: str
    final_metamodel: str
    final_validation: dict
    done: bool
    
    # New validation features
    validation_challenge_level: str  # "easy", "moderate", "hard"
    attached_file_content: str
    file_analysis_validation: dict
    highlighted_concepts: dict  # {concept: [highlight_positions]}
    concept_coverage_report: dict


