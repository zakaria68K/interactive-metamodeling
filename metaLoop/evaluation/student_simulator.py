import json
import os
from typing import List

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


load_dotenv()


class StudentRoleLLM:
    def __init__(self, metamodel_name: str):
        model_name = os.getenv("OPENAI_MODEL", "gpt-5.3-chat-latest")
        llm = ChatOpenAI(model=model_name, max_retries=2)
        self.metamodel_name = metamodel_name
        self.history: List[str] = []
        self.chain = ChatPromptTemplate.from_messages([
            (
                "system",
                "You simulate a non-expert student user. "
                "Answer only the user reply text, no explanations. "
                "For familiarity questions answer y or n. For agreement questions answer y or n. "
                "For background/feedback, keep it short and generic.",
            ),
            ("human", "{input}"),
        ]) | llm
        self._rejected_once = False

    def respond(self, prompt: str, context: dict) -> str:
        p = prompt.lower()
        if "familiar" in p:
            answer = "n"
        elif "agree" in p:
            if not self._rejected_once:
                self._rejected_once = True
                answer = "n"
            else:
                answer = "y"
        else:
            response = self.chain.invoke(
                {
                    "input": (
                        f"Metamodel: {self.metamodel_name}\n"
                        f"Question: {prompt}\n"
                        f"Context: {json.dumps(context, ensure_ascii=True)}\n"
                        "Give a short student-style answer."
                    ),
                }
            )
            answer = response.content if hasattr(response, "content") else str(response)
        self.history.append(answer)
        return answer.strip()
