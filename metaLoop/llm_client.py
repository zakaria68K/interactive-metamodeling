import json
import os
import re

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
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

        validator_model = os.getenv("VALIDATOR_MODEL", "gemma4:26b")
        validator_base_url = os.getenv("VALIDATOR_BASE_URL", "https://ollama.kher.nl")
        validator_llm = ChatOllama(model=validator_model, base_url=validator_base_url)
        self.validator_chain = ChatPromptTemplate.from_messages([
            ("system", prompt),
            ("human", "{input}"),
        ]) | validator_llm

    @staticmethod
    def _extract_json_text(raw: str) -> str:
        text = raw.strip()
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        return match.group(1).strip() if match else text

    def invoke_text(self, user_content: str) -> str:
        response = self.chain.invoke({"input": user_content})
        return response.content if isinstance(response.content, str) else str(response.content)

    def invoke_json(self, user_content: str) -> dict:
        raw = self._extract_json_text(self.invoke_text(user_content))
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def invoke_text_validator(self, user_content: str) -> str:
        response = self.validator_chain.invoke({"input": user_content})
        return response.content if isinstance(response.content, str) else str(response.content)

    def invoke_json_validator(self, user_content: str) -> dict:
        raw = self._extract_json_text(self.invoke_text_validator(user_content))
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
