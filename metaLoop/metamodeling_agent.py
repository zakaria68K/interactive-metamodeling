from .system_prompt import prompt
import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypedDict
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
load_dotenv()
import sys

class State(TypedDict):
    user_prompt: str
    intent_summary: str # A concise summary of the user's intent, extracted from the original prompt.
    concepts: list[str] # A list of core metamodeling concepts that need to be addressed to fulfill the user's request. These should be derived from the intent summary and represent distinct aspects of the metamodel.
    added_functionalities: list[str] # A list of additional functionalities that are necessary to implement the metamodel effectively. These should be identified during the decomposition of the user's request.
    current_index: int # Which concept is being processed right now
    current_concept: str # The current concept being processed
    current_chunk: str # The JjScript code generated for the current concept
    current_sample_model: str # A sample model generated for the current concept
    current_validation: dict # Validation result (valid, issues, suggestion)
    human_approved: bool # Whether a human approved the current chunk
    approved_chunks: list[str] # All chunks that passed validation and approval
    final_metamodel: str # The final output
    done: bool # Whether the loop should terminate


class MetamodelingAgent:
    def __init__(self):
        openai_model = os.getenv("OPENAI_MODEL", "gpt-5.3-chat-latest")
        self.system_prompt = prompt
        self.llm = ChatOpenAI(model=openai_model, max_retries=2)
        self._human_validator: Callable[[dict], bool] | None = None

    def _invoke_text(self, user_content: str) -> str:
        response = self.llm.invoke([
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_content),
        ])
        return response.content if isinstance(response.content, str) else str(response.content)

    def _invoke_json(self, user_content: str) -> dict:
        raw = self._invoke_text(user_content)
        return json.loads(raw)

    def _gather_intent(self, state: State) -> State:
        return {"intent_summary": state.get("user_prompt", "")}

    def _decompose_concepts(self, state: State) -> State:
        parsed = self._invoke_json(
            "Decompose this request into 2 core metamodel concepts and identify any missing "
            "essential functionalities.\n\n"
            "Reply with raw JSON only, no markdown, no extra text. Keys: "
            "intent_summary (string), concepts (array of strings), added_functionalities (array of strings).\n\n"
            f"Request:\n{state.get('intent_summary', '')}"
        )
        concepts = [c.strip() for c in parsed.get("concepts", []) if str(c).strip()]
        print("\n=== Concepts ===")
        for c in concepts:
            print(f"  - {c}")
        #sys.exit(0)
        if not concepts:
            concepts = [state.get("intent_summary", "")]
        return {
            "intent_summary": parsed.get("intent_summary", state.get("intent_summary", "")),
            "concepts": concepts,
            "added_functionalities": parsed.get("added_functionalities", []),
            "current_index": 0,
            "approved_chunks": [],
            "done": False,
        }

    def _generate_chunk(self, state: State) -> State:
        concepts = state.get("concepts", [])
        idx = state.get("current_index", 0)
        if idx >= len(concepts):
            return {
                "done": True,
                "final_metamodel": "\n\n".join(state.get("approved_chunks", [])),
            }
        concept = concepts[idx]
        approved_chunks = "\n\n".join(state.get("approved_chunks", [])) or "(none)"
        chunk = self._invoke_text(
            "Generate the next JjScript chunk for the concept below. "
            "Output code only, no markdown fences.\n\n"
            f"Intent: {state.get('intent_summary', '')}\n"
            f"Concept: {concept}\n"
            f"Approved chunks so far:\n{approved_chunks}"
        )
        return {"current_concept": concept, "current_chunk": chunk}

    def _build_sample_model(self, state: State) -> str:
        return self._invoke_text(
            "Write one compact plain-text sample model instance that this concept should represent.\n\n"
            f"Chunk:\n{state.get('current_chunk', '')}"
        )

    def _validate_chunk(self, state: State, sample_model: str) -> dict:
        return self._invoke_json(
            "Does this chunk correctly cover the concept and represent the sample model?\n\n"
            "Reply with raw JSON only, no markdown, no extra text. Keys: "
            "valid (bool), issues (array of strings), suggestion (string).\n\n"
            f"Concept: {state.get('current_concept', '')}\n"
            f"Sample model:\n{sample_model}\n"
            f"Chunk:\n{state.get('current_chunk', '')}"
        )

    def _parallel_validate(self, state: State) -> State:
        with ThreadPoolExecutor(max_workers=2) as executor:
            sample_model = executor.submit(self._build_sample_model, state).result()
            validation = executor.submit(self._validate_chunk, state, sample_model).result()
        return {"current_sample_model": sample_model, "current_validation": validation}

    def _human_validate(self, state: State) -> State:
        payload = {
            "concept": state.get("current_concept", ""),
            "chunk": state.get("current_chunk", ""),
            "sample_model": state.get("current_sample_model", ""),
            "validation": state.get("current_validation", {}),
        }
        approved = self._human_validator(payload) if self._human_validator else True
        return {"human_approved": approved}

    def _advance(self, state: State) -> State:
        valid = bool(state.get("current_validation", {}).get("valid", False))
        human_approved = bool(state.get("human_approved", False))
        if valid and human_approved:
            approved_chunks = [*state.get("approved_chunks", []), state.get("current_chunk", "")]
            next_idx = state.get("current_index", 0) + 1
            done = next_idx >= len(state.get("concepts", []))
            return {
                "approved_chunks": approved_chunks,
                "current_index": next_idx,
                "done": done,
                "final_metamodel": "\n\n".join(approved_chunks) if done else "",
            }
        return {}

    def _router(self, state: State) -> str:
        return "end" if state.get("done", False) else "next"

    def create_metamodeling_agent(self):
        builder = StateGraph(State)
        builder.add_node("gather_intent", self._gather_intent)
        builder.add_node("decompose_concepts", self._decompose_concepts)
        builder.add_node("generate_chunk", self._generate_chunk)
        builder.add_node("parallel_validate", self._parallel_validate)
        builder.add_node("human_validate", self._human_validate)
        builder.add_node("advance", self._advance)

        builder.add_edge(START, "gather_intent")
        builder.add_edge("gather_intent", "decompose_concepts")
        builder.add_edge("decompose_concepts", "generate_chunk")
        builder.add_edge("generate_chunk", "parallel_validate")
        builder.add_edge("parallel_validate", "human_validate")
        builder.add_edge("human_validate", "advance")
        builder.add_conditional_edges("advance", self._router, {"next": "generate_chunk", "end": END})
        return builder.compile()

    def run_iterative(
        self,
        user_prompt: str,
        human_validator: Callable[[dict], bool] | None = None,
    ) -> dict:
        self._human_validator = human_validator
        return self.create_metamodeling_agent().invoke({"user_prompt": user_prompt})