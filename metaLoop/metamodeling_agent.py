
from typing import Callable

from langgraph.graph import END, START, StateGraph

from .elicitation import decompose_concepts, gather_intent, knowledge_elicitation
from .generation import advance, dual_validation, generate_chunk, human_validate, isolated_validation_step, router
from .llm_client import LLMClient
from .state import State

# TODO: add executable validity; models don't always reflect intent — add few-shot examples.
class MetamodelingAgent:
    def __init__(self):
        self.llm_client = LLMClient()
        self._human_validator: Callable[[dict], bool] | None = None
        self._user_responder: Callable[[str, dict], str] | None = None

    def _set_callbacks(self, hv, ur) -> None:
        self._human_validator, self._user_responder = hv, ur

    def _chunk_nodes(self) -> dict:
        lc, hv, ur = self.llm_client, self._human_validator, self._user_responder
        return {
            "generate_chunk":      lambda s: generate_chunk(s, lc.invoke_text),
            "dual_validation":     lambda s: dual_validation(
                                        s, lc.invoke_text, lc.invoke_json,
                                        validator_invoke_text=lc.invoke_text_validator,
                                        validator_invoke_json=lc.invoke_json_validator,
                                        user_responder=ur),
            "human_validate":      lambda s: human_validate(s, hv),
            "isolated_validation": lambda s: isolated_validation_step(
                                        s, lc.invoke_text, lc.invoke_json,
                                        user_responder=ur, human_validator=hv,
                                        validator_invoke_text=lc.invoke_text_validator,
                                        validator_invoke_json=lc.invoke_json_validator),
            "advance":             advance,
            "finish":              lambda _: {},
        }

    def _add_chunk_subgraph(self, builder: StateGraph) -> StateGraph:                                   
        for name, fn in self._chunk_nodes().items():
            builder.add_node(name, fn)
        builder.add_edge("generate_chunk",      "dual_validation")
        builder.add_edge("dual_validation",     "human_validate")
        builder.add_edge("human_validate",      "isolated_validation")
        builder.add_edge("isolated_validation", "advance")
        builder.add_conditional_edges("advance", router, {"next": "generate_chunk", "end": "finish"})
        builder.add_edge("finish", END)
        return builder

    # ── public API ────────────────────────────────────────────────────────────

    def run_iterative(
        self,
        user_prompt: str,
        human_validator: Callable[[dict], bool] | None = None,
        user_responder: Callable[[str, dict], str] | None = None,
        initial_state: dict | None = None,
    ) -> dict:
        self._set_callbacks(human_validator, user_responder)
        lc, ur = self.llm_client, self._user_responder
        builder = StateGraph(State)
        builder.add_node("gather_intent",         gather_intent)
        builder.add_node("knowledge_elicitation", lambda s: knowledge_elicitation(s, lc.invoke_json, ur))
        builder.add_node("decompose_concepts",    lambda s: decompose_concepts(s, lc.invoke_json))
        builder.add_edge(START,                   "gather_intent")
        builder.add_edge("gather_intent",         "knowledge_elicitation")
        builder.add_edge("knowledge_elicitation", "decompose_concepts")
        builder.add_edge("decompose_concepts",    "generate_chunk")
        graph = self._add_chunk_subgraph(builder).compile()
        return graph.invoke({"user_prompt": user_prompt, **(initial_state or {})})

    def run_extra_concepts(
        self,
        extra_concepts: list[str],
        seed_state: dict,
        human_validator: Callable[[dict], bool] | None = None,
        user_responder: Callable[[str, dict], str] | None = None,
    ) -> dict:
        """Process additional concepts, skipping elicitation/decomposition."""
        self._set_callbacks(human_validator, user_responder)
        builder = StateGraph(State)
        builder.add_edge(START, "generate_chunk")
        start_state = {**seed_state, "concepts": extra_concepts,
                       "current_index": 0, "done": False, "concept_retry_count": 0}
        return self._add_chunk_subgraph(builder).compile().invoke(start_state)

    def run_concepts_only(
        self,
        user_prompt: str,
        user_responder: Callable[[str, dict], str] | None = None,
    ) -> dict:
        self._set_callbacks(None, user_responder)
        lc, ur = self.llm_client, self._user_responder
        state: State = {"user_prompt": user_prompt}
        state.update(gather_intent(state))
        state.update(knowledge_elicitation(state, lc.invoke_json, ur))
        state.update(decompose_concepts(state, lc.invoke_json))
        return state
