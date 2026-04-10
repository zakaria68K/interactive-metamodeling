from .system_prompt import prompt
import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypedDict
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
load_dotenv()

class State(TypedDict):
    user_prompt: str
    user_familiar: bool # Whether the user is familiar with the domain concepts.
    intent_summary: str # A concise summary of the user's intent, extracted from the original prompt.
    concepts: list[str] # A list of core metamodeling concepts that need to be addressed to fulfill the user's request. These should be derived from the intent summary and represent distinct aspects of the metamodel.
    added_functionalities: list[str] # A list of additional functionalities that are necessary to implement the metamodel effectively. These should be identified during the decomposition of the user's request.
    current_index: int # Which concept is being processed right now.
    concept_retry_count: int # Number of failed attempts for the current concept.
    current_concept: str # The current concept being processed.
    current_chunk: str # The JjScript code generated for the current concept.
    current_sample_model: str # A sample model generated for the current concept.
    current_validation: dict # Validation result (valid, issues, suggestion).
    human_approved: bool # Whether a human approved the current chunk.
    approved_chunks: list[str] # All chunks that passed validation and approval.
    final_metamodel: str # The final output.
    done: bool # Whether the loop should terminate.


class MetamodelingAgent:
    # The constructor initializes the LLM and the prompt template. It also sets up a placeholder for the human validator function, which can be provided when running the agent.
    def __init__(self):
        openai_model = os.getenv("OPENAI_MODEL", "gpt-5.3-chat-latest")
        self.system_prompt = prompt
        llm = ChatOpenAI(model=openai_model, max_retries=2)
        self.llm = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}")
        ]) | llm
        self._human_validator: Callable[[dict], bool] | None = None
    # A helper method to invoke the LLM and get raw text responses, without any parsing or assumptions about the format.
    def _invoke_text(self, user_content: str) -> str:
        response = self.llm.invoke({"input": user_content})
        return response.content if isinstance(response.content, str) else str(response.content)
    # A helper method to invoke the LLM and parse JSON responses, with error handling for invalid JSON.
    def _invoke_json(self, user_content: str) -> dict:
        raw = self._invoke_text(user_content)
        return json.loads(raw)
    # The first step is to understand the user's intent and the domain they are working in. This will help us tailor the concept elicitation and chunk generation to their specific needs.
    def _gather_intent(self, state: State) -> State:
        return {"intent_summary": state.get("user_prompt", "")}
    # Negotiates concept list with the user.
    def _knowledge_elicitation(self, state: State) -> State:
        intent = state.get("intent_summary", "")
        familiar_answer = input("Are you familiar with the domain concepts? [y/N]: ").strip().lower()
        user_familiar = familiar_answer in {"y", "yes"}

        base_prompt = (
            "Propose 2 core metamodel concepts for the request below. "
            "Reply with raw JSON only with key: concepts (array of strings).\n\n"
            f"Request:\n{intent}"
        )
        if not user_familiar:
            base_prompt = (
                "The user is not familiar with the domain. Propose 2 beginner-friendly core metamodel concepts "
                "for the request below. Reply with raw JSON only with key: concepts (array of strings).\n\n"
                f"Request:\n{intent}"
            )

        concepts: list[str] = []
        for _ in range(3):
            parsed = self._invoke_json(base_prompt)
            concepts = [c.strip() for c in parsed.get("concepts", []) if str(c).strip()]
            if not concepts:
                break
            print("\nLLM suggested concepts:")
            for i, c in enumerate(concepts, start=1):
                print(f"  {i}. {c}")
            ok = input("Do you agree with these concepts? [Y/n]: ").strip().lower()
            if ok in {"", "y", "yes"}:
                return {"user_familiar": user_familiar, "concepts": concepts}
            feedback = input("What should be changed? ").strip()
            base_prompt = (
                "Revise the concept list based on this user feedback. "
                "Reply with raw JSON only with key: concepts (array of strings).\n\n"
                f"Request:\n{intent}\n\n"
                f"Current concepts: {concepts}\n"
                f"User feedback: {feedback}"
            )

        return {"user_familiar": user_familiar, "concepts": concepts or [intent]}

    # The LLM generates the concept list and added functionalities based on the user's intent.
    def _decompose_concepts(self, state: State) -> State:
        if state.get("concepts"):
            return {
                "concepts": state.get("concepts", []),
                "added_functionalities": state.get("added_functionalities", []),
                "current_index": 0,
                "concept_retry_count": 0,
                "approved_chunks": [],
                "done": False,
            }

        parsed = self._invoke_json(
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

    # The LLM generates a JjScript chunk for the current concept. If the previous chunk failed validation, it also includes feedback from that validation to guide the generation of the next chunk.
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
        feedback = ""
        if state.get("current_validation") and not state.get("current_validation", {}).get("valid"):
            issues = state["current_validation"].get("issues", [])
            suggestion = state["current_validation"].get("suggestion", "")
            feedback = (
                f"\n\nPrevious validation feedback:\n"
                f"Issues: {', '.join(issues)}\n"
                f"Suggestion: {suggestion}"
            )
        chunk = self._invoke_text(
            f"Generate the next JjScript chunk for the concept below.{feedback}"
            "Output code only, no markdown or explanations.\n\n"
            f"Intent: {state.get('intent_summary', '')}\n"
            f"Concept: {concept}\n"
            f"Approved chunks so far:\n{approved_chunks}"
        )
        return {"current_concept": concept, "current_chunk": chunk}

    # The LLM generates a sample model instance for the current concept and validates the generated chunk against that sample model. These two tasks are done in parallel to save time, as they are independent of each other.
    def _build_sample_model(self, state: State) -> str:
        return self._invoke_text(
            "Write one compact plain-text sample model instance that this concept should represent. This should challenge the model's understanding and cover edge cases.\n\n"
            f"Concept:\n{state.get('current_concept', '')}"
        )
     # The validation prompt asks the LLM to evaluate whether the generated chunk correctly captures the current concept and can represent the sample model. The LLM should provide a boolean validity flag, a list of issues if any, and suggestions for improvement.
    def _validate_chunk(self, state: State, sample_model: str) -> dict:
        return self._invoke_json(
            "Does this chunk correctly cover the concept and represent the sample model?\n\n"
            "Reply with raw JSON only, no markdown, no extra text. Keys: "
            "valid (bool), issues (array of strings), suggestion (string).\n\n"
            f"Concept: {state.get('current_concept', '')}\n"
            f"Sample model:\n{sample_model}\n"
            f"Chunk:\n{state.get('current_chunk', '')}"
        )
    # This method runs the sample model generation and chunk validation in parallel using a thread pool, and then combines their results into the state for the next step.
    def _parallel_validate(self, state: State) -> State:
        with ThreadPoolExecutor(max_workers=2) as executor:
            sample_model = executor.submit(self._build_sample_model, state).result()
            validation = executor.submit(self._validate_chunk, state, sample_model).result()
        return {"current_sample_model": sample_model, "current_validation": validation}

    # After the LLM validation, we ask the human user to review the generated chunk and the validation feedback. The human can approve the chunk or reject it. 
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
        max_retries = 3
        valid = bool(state.get("current_validation", {}).get("valid", False))
        human_approved = bool(state.get("human_approved", False))
        if human_approved: #if valid and human_approved:
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

    def _router(self, state: State) -> str:
        return "end" if state.get("done", False) else "next"

    def create_metamodeling_agent(self):
        builder = StateGraph(State)
        builder.add_node("knowledge_elicitation", self._knowledge_elicitation)
        builder.add_node("gather_intent", self._gather_intent)
        builder.add_node("decompose_concepts", self._decompose_concepts)
        builder.add_node("generate_chunk", self._generate_chunk)
        builder.add_node("parallel_validate", self._parallel_validate)
        builder.add_node("human_validate", self._human_validate)
        builder.add_node("advance", self._advance)
        builder.add_edge(START, "gather_intent")
        builder.add_edge("gather_intent", "knowledge_elicitation")
        builder.add_edge("knowledge_elicitation", "decompose_concepts")
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