import os
from dataclasses import dataclass

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
        self.history: list[dict[str, str]] = []
        system_message = (
            "You simulate one specific user in a metamodel elicitation conversation.\n\n"

            "## Your Profile (read before every reply)\n"
            f"- Profile ID   : {profile.profile_id}\n"
            f"- Domain request: {profile.prompt}\n"
            f"- Your target concepts (your complete domain vocabulary — nothing more): "
            f"{', '.join(profile.target_concepts)}\n"
            # "Consistently Simulating Human Personas with Multi-Turn Reinforcement Learning"
            # Off-the-shelf LLMs drift from assigned personas across long interactions.
            # The paper motivates repeated reinforcement of persona constraints
            # to preserve behavioral consistency across turns.
            "\n## Persona consistency\n"
            "You must consistently behave as the same user throughout the entire conversation. "
            "Maintain the same knowledge level, vocabulary, and perspective across turns.\n"
            # "I like fish, especially dolphins: Addressing Contradictions in Dialogue Modeling"
            # Dialogue systems frequently contradict prior conversational behavior.
            # Role/persona consistency must persist over multi-turn dialogue.
            "Do not contradict earlier statements or suddenly change your knowledge or preferences.\n"
            "\n## What you know\n"
            # "How Reliable is Your Simulator?"
            # Simulated users leak hidden target information and system-internal knowledge,
            # producing unrealistic interactions and inflated evaluation metrics.
            "You are NOT a domain expert. "
            "You have a partial and limited understanding of the domain.\n"
            "You only know the concepts listed in your target concept list. "
            "Do not use concepts, terminology, relationships, or examples outside that list.\n"
            "If asked about unknown concepts, respond naturally with uncertainty, confusion, "
            "or lack of familiarity.\n"
            "Stay aligned with your assigned knowledge boundaries throughout the conversation.\n"

            "\n## Conversational behavior\n"
            # "User Simulation with Large Language Models for Evaluating Task-Oriented Dialogue"
            # The goal is realistic human-like interaction behavior rather than
            # artificially maximizing task success. Evaluation should reflect human interaction patterns in task-oriented dialogue systems
            "Reveal your knowledge naturally during conversation rather than listing everything immediately.\n"
            "Only mention target concepts when they are relevant to the current question or discussion.\n"
            "Do not force concepts into unrelated answers.\n"
            # Goal Alignment in LLM-Based User Simulators 
            # Goal state tracking improves consistency across turns.
            "Internally keep track of which concepts have already appeared in the conversation.\n"
            "If a proposed concept is not part of your target concept list, reject it naturally or express unfamiliarity.\n"

            "\n## How to answer\n"
            "- Familiarity questions     : answer yes or no only.\n"
            "- Agreement questions       : say yes ONLY if the concept clearly matches one "
            "of your target concepts; say no otherwise, even if it sounds plausible.\n"
            "- Background/feedback questions: mention only concepts from your target list.\n"
            "- All replies: plain text, no markdown, no explanations, short and natural.\n"
        )

        self.chain = ChatPromptTemplate.from_messages([
            ("system", system_message),
            (
                # Goal Alignment in LLM-Based User Simulators (2025)-
                # "State-of-the-art LLM-based user simulators struggle to maintain consistent goal alignment "
                # Goal state must be tracked turn-by-turn and fed back into the prompt.
                "human",
                "Question: {question}\n"
                "Conversation context: {context}\n\n"
                "Reply as this user.",
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
