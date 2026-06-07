import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama


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
        model_name = profile.model_name or os.getenv("EVAL_OLLAMA_MODEL", "gemma4:26b")
        base_url = os.getenv("EVAL_OLLAMA_BASE_URL", "https://ollama.kher.nl")
        llm = ChatOllama(model=model_name, base_url=base_url)
        self.profile = profile
        self.history: list[dict] = [
            {
                "stage": "__metadata__",
                "profile_id": profile.profile_id,
                "target_concepts_count": len(profile.target_concepts),
                "target_concepts": list(profile.target_concepts),
            }
        ]

        system_message = (
            "You simulate one specific user in a metamodel elicitation conversation.\n\n"

            "## Your Profile (read before every reply)\n"
            f"- Profile ID    : {profile.profile_id}\n"
            f"- Domain request: {profile.prompt}\n"
            f"- Your target concepts (your complete domain vocabulary — nothing more): "
            f"{', '.join(profile.target_concepts)}\n"

            "\n## Persona consistency\n"
            "You must consistently behave as the same user throughout the entire conversation. "
            "Maintain the same knowledge level, vocabulary, and perspective across turns.\n"
            "Do not contradict earlier statements or suddenly change your knowledge or preferences.\n"

            "\n## What you know\n"
            "You only know the concepts listed in your target concept list. "
            "Do not use concepts, terminology, relationships, or examples outside that list.\n"
            "If asked about unknown concepts, respond naturally with uncertainty or lack of familiarity.\n"
            "Stay aligned with your assigned knowledge boundaries throughout the conversation.\n"

            "\n## Conversational behavior\n"
            "Reveal your knowledge naturally during conversation rather than listing everything immediately.\n"
            "Only mention target concepts when they are relevant to the current question or discussion.\n"
            "Do not force concepts into unrelated answers.\n"
            "Internally keep track of which concepts have already appeared in the conversation.\n"
            "If a proposed concept is not part of your target concept list, reject it naturally or express unfamiliarity.\n"

            "\n## How to answer\n"
            "- Familiarity questions     : answer yes or no only.\n"
            "- Agreement questions       : say yes ONLY if the concept clearly matches one "
            "of your target concepts; say no otherwise, even if it sounds plausible.\n"
            "- Background/feedback questions: mention only concepts from your target list.\n"
            "- All replies: plain text, no markdown, no explanations.\n"
        )

        self.chain = ChatPromptTemplate.from_messages([
            ("system", system_message),
            (
                "human",
                "Question: {question}\n"
                "Conversation context: {context}\n\n"
                "Reply as this user.",
            ),
        ]) | llm

    def respond(self, prompt: str, context: dict) -> str:
        stage = context.get("stage", "")

        if stage == "familiarity":
            answer = "yes"
        elif context.get("validation_stage") == "challenge_selection":
            answer = "easy"
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
                    "question": prompt,
                    "context": str(context),
                }
            )
            answer = response.content if hasattr(response, "content") else str(response)

        self.history.append({
            "stage": stage or context.get("validation_stage", ""),
            "question": prompt,
            "answer": str(answer).strip(),
            "answer_length": len(str(answer).strip().split()),
        })
        return str(answer).strip()
