import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

sys.path.append(str(Path(__file__).resolve().parents[2]))
from metaLoop.system_prompt import prompt as system_prompt

load_dotenv()


def refine_metamodel(domain_prompt: str, current_metamodel: str, user_feedback: str) -> str:
    """Refine an existing metamodel based on user feedback."""
    model_name = os.getenv("EVAL_SYSTEM_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    llm = ChatOpenAI(model=model_name, max_retries=2)

    input_text = (
        f"Domain: {domain_prompt}\n\n"
        f"Current metamodel:\n{current_metamodel}\n\n"
        f"User feedback: {user_feedback}\n\n"
        "Refine the metamodel based on the user feedback. "
        "Keep what is correct, fix what is wrong, and add what is missing."
    )

    chain = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ]) | llm

    response = chain.invoke({"input": input_text})
    return response.content if isinstance(response.content, str) else str(response.content)
