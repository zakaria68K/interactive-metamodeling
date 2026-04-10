import os
import sys
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from metaLoop.system_prompt import prompt


load_dotenv()


def generate_direct(user_prompt: str) -> str:
    model_name = os.getenv("OPENAI_MODEL", "gpt-5.3-chat-latest")
    llm = ChatOpenAI(model=model_name, max_retries=2)
    chain = ChatPromptTemplate.from_messages([
        ("system", prompt),
        ("human", "{input}"),
    ]) | llm
    response = chain.invoke({"input": user_prompt})
    return response.content if isinstance(response.content, str) else str(response.content)


def main() -> None:
    user_prompt = " ".join(sys.argv[1:]).strip() or input("Prompt: ").strip()
    if not user_prompt:
        print("No prompt provided.")
        return
    print(generate_direct(user_prompt))


if __name__ == "__main__":
    main()
