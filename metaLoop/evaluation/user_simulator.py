import os
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


load_dotenv()


@dataclass
class SimulatedUserProfile:
    profile_id: str
    prompt: str
    target_concepts: list[str]
    sample_file_path: str | None = None
    model_name: str | None = None


class ProfileUserLLM:
    def __init__(self, profile: SimulatedUserProfile):
        model_name = profile.model_name or os.getenv("EVAL_OPENAI_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        llm = ChatOpenAI(model=model_name, max_retries=2)
        self.profile = profile
        self.history: list[dict[str, str]] = []
        self.chain = ChatPromptTemplate.from_messages([
            (
                "system",
                "You simulate one specific user in a metamodel elicitation conversation. "
                "Stay consistent with the user's goal."
                "Answer only with the user's reply text, no explanations, no markdown. "
                "Keep replies short and natural. "
                "For familiarity questions, answer yes or no. "
                "For agreement questions, answer yes only if the proposed concepts clearly match the user's goal; otherwise answer no. "
                "For background or feedback questions, mention only the concepts relevant to the user's goal.",
            ),
            (
                "human",
                "Profile id: {profile_id}\n"
                "Domain request: {prompt}\n"
                "Target concepts: {target_concepts}\n"
                "Question: {question}\n"
                "Context: {context}\n"
                "Reply as that user.",
            ),
        ]) | llm

    def respond(self, prompt: str, context: dict) -> str:
        stage = context.get("stage", "")
        proposed = {
            str(concept).strip().lower()
            for concept in context.get("proposed_concepts", [])
            if str(concept).strip()
        }
        target = {
            concept.strip().lower()
            for concept in self.profile.target_concepts
            if concept.strip()
        }

        if stage == "familiarity":
            answer = "no"
        elif stage == "agreement":
            answer = "yes" if target.issubset(proposed) else "no"
        elif context.get("validation_stage") == "file_new_concepts_selection":
            suggested = {
                str(concept).strip().lower()
                for concept in context.get("new_concepts", [])
                if str(concept).strip()
            }
            selected = [concept for concept in self.profile.target_concepts if concept.strip().lower() in suggested]
            answer = ", ".join(selected) if selected else "none"
        else:
            response = self.chain.invoke(
                {
                    "profile_id": self.profile.profile_id,
                    "prompt": self.profile.prompt,
                    "target_concepts": ", ".join(self.profile.target_concepts),
                    "question": prompt,
                    "context": str(context),
                }
            )
            answer = response.content if hasattr(response, "content") else str(response)
        self.history.append({
            "stage": stage or context.get("validation_stage", ""),
            "question": prompt,
            "answer": str(answer).strip(),
        })
        return answer.strip()
