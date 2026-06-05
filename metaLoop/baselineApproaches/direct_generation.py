import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


sys.path.append(str(Path(__file__).resolve().parents[2]))
from metaLoop.system_prompt import prompt

#TODO: If interaction budgets, retries, and context windows are not normalized, comparisons are not fair. So maybe we should consider using a local LLM

load_dotenv()


def generate_direct(user_prompt: str, file_content: str = "", previous_result: str = "") -> str:
    model_name = os.getenv("EVAL_SYSTEM_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    llm = ChatOpenAI(model=model_name, max_retries=2)
    input_text = user_prompt
    if file_content:
        input_text += (
            f"\n\n--- Attached file (usage example) ---\n{file_content}"
        )
    if previous_result:
        input_text += (
            f"\n\n--- Previous generation (use as a starting point and improve upon it) ---\n{previous_result}"
        )
    chain = ChatPromptTemplate.from_messages([
        ("system", prompt),
        ("human", "{input}"),
    ]) | llm
    response = chain.invoke({"input": input_text})
    return response.content if isinstance(response.content, str) else str(response.content)


def main() -> None:
    user_prompt = " ".join(sys.argv[1:]).strip() or input("Prompt: ").strip()
    if not user_prompt:
        print("No prompt provided.")
        return
    print(generate_direct(user_prompt))


if __name__ == "__main__":
    main()
