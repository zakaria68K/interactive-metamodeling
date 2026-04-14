from typing import Callable

from langgraph.graph import END, START, StateGraph

from .elicitation import decompose_concepts, gather_intent, knowledge_elicitation
from .generation import advance, generate_chunk, human_validate, parallel_validate, reconcile_metamodel, router
from .llm_client import LLMClient
from .state import State

# TODO: add the executable validity
class MetamodelingAgent:
    def __init__(self):
        self.llm_client = LLMClient()
        self._human_validator: Callable[[dict], bool] | None = None
        self._user_responder: Callable[[str, dict], str] | None = None

    def _invoke_text(self, user_content: str) -> str:
        return self.llm_client.invoke_text(user_content)

    def _invoke_json(self, user_content: str) -> dict:
        return self.llm_client.invoke_json(user_content)

    def _invoke_text_validator(self, user_content: str) -> str:
        return self.llm_client.invoke_text_validator(user_content)

    def _invoke_json_validator(self, user_content: str) -> dict:
        return self.llm_client.invoke_json_validator(user_content)

    def _gather_intent(self, state: State) -> State:
        return gather_intent(state)

    def _knowledge_elicitation(self, state: State) -> State:
        return knowledge_elicitation(state, self._invoke_json, self._user_responder)

    def _decompose_concepts(self, state: State) -> State:
        return decompose_concepts(state, self._invoke_json)

    def _generate_chunk(self, state: State) -> State:
        return generate_chunk(state, self._invoke_text)

    def _parallel_validate(self, state: State) -> State:
        return parallel_validate(
            state,
            self._invoke_text,
            self._invoke_json,
            validator_invoke_text=self._invoke_text_validator,
            validator_invoke_json=self._invoke_json_validator,
        )

    def _human_validate(self, state: State) -> State:
        return human_validate(state, self._human_validator)

    def _advance(self, state: State) -> State:
        return advance(state)

    def _router(self, state: State) -> str:
        return router(state)

    def _reconcile_metamodel(self, state: State) -> State:
        return reconcile_metamodel(state, self._invoke_text_validator)

    def create_metamodeling_agent(self):
        builder = StateGraph(State)
        builder.add_node("knowledge_elicitation", self._knowledge_elicitation)
        builder.add_node("gather_intent", self._gather_intent)
        builder.add_node("decompose_concepts", self._decompose_concepts)
        builder.add_node("generate_chunk", self._generate_chunk)
        builder.add_node("parallel_validate", self._parallel_validate)
        builder.add_node("human_validate", self._human_validate)
        builder.add_node("advance", self._advance)
        builder.add_node("reconcile", self._reconcile_metamodel)
        builder.add_edge(START, "gather_intent")
        builder.add_edge("gather_intent", "knowledge_elicitation")
        builder.add_edge("knowledge_elicitation", "decompose_concepts")
        builder.add_edge("decompose_concepts", "generate_chunk")
        builder.add_edge("generate_chunk", "parallel_validate")
        builder.add_edge("parallel_validate", "human_validate")
        builder.add_edge("human_validate", "advance")
        builder.add_conditional_edges("advance", self._router, {"next": "generate_chunk", "end": "reconcile"})
        builder.add_edge("reconcile", END)
        return builder.compile()

    def run_iterative(
        self,
        user_prompt: str,
        human_validator: Callable[[dict], bool] | None = None,
        user_responder: Callable[[str, dict], str] | None = None,
    ) -> dict:
        self._human_validator = human_validator
        self._user_responder = user_responder
        return self.create_metamodeling_agent().invoke({"user_prompt": user_prompt})

    def run_concepts_only(
        self,
        user_prompt: str,
        user_responder: Callable[[str, dict], str] | None = None,
    ) -> dict:
        self._user_responder = user_responder
        state: State = {"user_prompt": user_prompt}
        state.update(self._gather_intent(state))
        state.update(self._knowledge_elicitation(state))
        state.update(self._decompose_concepts(state))
        return state