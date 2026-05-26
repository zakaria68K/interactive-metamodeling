import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama


load_dotenv()

# ---------------------------------------------------------------------------
# Trait instruction libraries
# ---------------------------------------------------------------------------
# A Survey on LLM-based Conversational User Simulation:
#   Heterogeneous user traits (emotion, verbosity, strategy, competency) are
#   necessary to model realistic variation in user interaction behavior.
# PersonaLLM: Investigating the Ability of LLMs to Express Personality Traits:
#   Conditioning prompts on explicit trait descriptions preserves behavioral
#   consistency across turns.

_EMOTION_INSTRUCTIONS: dict[str, str] = {
    "anxious": (
        "You are uncertain and hesitant. You often second-guess yourself and seek reassurance. "
        "Use hedging phrases like 'I think', 'maybe', or 'I'm not sure' naturally in replies."
    ),
    "enthusiastic": (
        "You are genuinely excited about the topic. Show interest and energy. "
        "Use positive language and express engagement with the process."
    ),
    "calm": (
        "You are composed and objective. Respond in a measured, neutral tone without strong emotion."
    ),
    "frustrated": (
        "You are mildly frustrated when asked about concepts that don't fit your needs. "
        "Express polite impatience or mild skepticism when irrelevant concepts are proposed."
    ),
}

_VERBOSITY_INSTRUCTIONS: dict[str, str] = {
    "terse": (
        "Keep every reply as short as possible, one word or one short sentence. "
        "Never elaborate unless the question explicitly demands it."
    ),
    "moderate": (
        "Use normal conversational length. Add context only when it is directly relevant to the question."
    ),
    "verbose": (
        "Give detailed, elaborated replies. Add examples, context, or minor tangents "
        "even when not explicitly requested."
    ),
}

_STRATEGY_INSTRUCTIONS: dict[str, str] = {
    "confirmatory": (
        "Take a passive, reactive role. Wait for the agent to propose ideas and simply confirm "
        "or deny them. Do not volunteer concepts or information unless explicitly asked."
    ),
    "exploratory": (
        "Be curious and probe the agent with clarifying questions before or after answering. "
        "Explore the problem space by asking what terms mean or why something is proposed."
    ),
    "goal_directed": (
        "Be efficient and focused. When asked about a concept, answer directly and confidently "
        "without hedging or going off-topic. Do not volunteer concepts unprompted, only respond "
        "to what is explicitly asked, but do so clearly and without ambiguity."
    ),
}

_COMPETENCY_INSTRUCTIONS: dict[str, str] = {
    "novice": (
        "You have very limited domain knowledge. You know only the few basic core concepts you were given. "
        "You are unfamiliar with technical terminology beyond your list and cannot explain relationships."
    ),
    "intermediate": (
        "You have a reasonable understanding of the domain. You know most key concepts and can "
        "discuss them, but you may miss advanced or edge-case terms."
    ),
    "expert": (
        "You have deep domain expertise. You are confident about all your concepts, understand "
        "their relationships, and can explain them precisely and concisely."
    ),
}


@dataclass
class SimulatedUserProfile:
    profile_id: str
    prompt: str
    target_concepts: list[str]
    sample_file_path: str | None = None
    model_name: str | None = None
    # Behavioral traits — used to condition the simulator persona
    # Ref: "A Survey on LLM-based Conversational User Simulation" (heterogeneous trait modeling)
    emotion: str = "calm"        # anxious | enthusiastic | calm | frustrated
    verbosity: str = "moderate"  # terse | moderate | verbose
    strategy: str = "exploratory"  # confirmatory | exploratory | goal_directed
    competency: str = "intermediate"  # novice | intermediate | expert


class ProfileUserLLM:
    def __init__(self, profile: SimulatedUserProfile):
        model_name = profile.model_name or os.getenv("EVAL_OLLAMA_MODEL", "gemma4:26b")
        base_url = os.getenv("EVAL_OLLAMA_BASE_URL", "https://ollama.kher.nl")
        llm = ChatOllama(model=model_name, base_url=base_url)
        self.profile = profile
        # Seed history with a metadata entry for downstream plotting
        self.history: list[dict] = [
            {
                "stage": "__metadata__",
                "profile_id": profile.profile_id,
                "emotion": profile.emotion,
                "verbosity": profile.verbosity,
                "strategy": profile.strategy,
                "competency": profile.competency,
                "target_concepts_count": len(profile.target_concepts),
                "target_concepts": list(profile.target_concepts),
            }
        ]

        emotion_instr = _EMOTION_INSTRUCTIONS.get(profile.emotion, "")
        verbosity_instr = _VERBOSITY_INSTRUCTIONS.get(profile.verbosity, "")
        strategy_instr = _STRATEGY_INSTRUCTIONS.get(profile.strategy, "")
        competency_instr = _COMPETENCY_INSTRUCTIONS.get(profile.competency, "")

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
            f"{competency_instr}\n"
            "You only know the concepts listed in your target concept list. "
            "Do not use concepts, terminology, relationships, or examples outside that list.\n"
            "If asked about unknown concepts, respond naturally with uncertainty, confusion, "
            "or lack of familiarity.\n"
            "Stay aligned with your assigned knowledge boundaries throughout the conversation.\n"

            # "A Survey on LLM-based Conversational User Simulation"
            # Heterogeneous behavioral traits (emotion, verbosity, interaction strategy) are
            # necessary to cover the full diversity of real user populations.
            "\n## Your behavioral traits\n"
            f"- Emotion   ({profile.emotion})    : {emotion_instr}\n"
            f"- Verbosity ({profile.verbosity}) : {verbosity_instr}\n"
            f"- Strategy  ({profile.strategy})  : {strategy_instr}\n"
            "These traits define HOW you communicate. Apply them consistently in every reply.\n"

            "\n## Conversational behavior\n"
            # "User Simulation with Large Language Models for Evaluating Task-Oriented Dialogue"
            # The goal is realistic human-like interaction behavior rather than
            # artificially maximizing task success.
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
            "- All replies: plain text, no markdown, no explanations.\n"
            "  Apply your verbosity trait to calibrate reply length.\n"
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
            # novice users are not familiar with the domain; intermediate/expert are
            answer = "no" if self.profile.competency == "novice" else "yes"
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
            # Trait snapshot per turn — enables per-trait breakdown when plotting
            "emotion": self.profile.emotion,
            "verbosity": self.profile.verbosity,
            "strategy": self.profile.strategy,
            "competency": self.profile.competency,
            "answer_length": len(str(answer).strip().split()),
        })
        return answer.strip()
