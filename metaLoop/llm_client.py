import json
import os

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .system_prompt import prompt


load_dotenv()


class LLMClient:
    def __init__(self):
        openai_model = os.getenv("OPENAI_MODEL", "gpt-5.3-chat-latest")
        llm = ChatOpenAI(model=openai_model, max_retries=2)
        self.chain = ChatPromptTemplate.from_messages([
            ("system", prompt),
            ("human", "{input}"),
        ]) | llm

    def invoke_text(self, user_content: str) -> str:
        response = self.chain.invoke({"input": user_content})
        return response.content if isinstance(response.content, str) else str(response.content)

    def invoke_json(self, user_content: str) -> dict:
        return json.loads(self.invoke_text(user_content))
