import json
import os
import re
import sys

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


load_dotenv()

# ConceptExtractor is a utility class to extract concepts from metamodel text using an LLM. It will be used in the one shot baseline approach.

class ConceptExtractor:
    def __init__(self):
        model_name = os.getenv("EVAL_SYSTEM_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        llm = ChatOpenAI(model=model_name, max_retries=2)
        self.chain = ChatPromptTemplate.from_messages([
            (
                "system",
                "Extract concepts from metamodel text and return strict raw JSON only. "
                "Format: {{\"concepts\": [\"...\", \"...\"]}}. "
                "One-shot example:\n"
                "metamodel: 'StateMachine'\n"
                "Output: {{\"concepts\":[\"State\",\"Transition\"]}}",
            ),
            ("human", "{input}"),
        ]) | llm

    def _parse_json(self, raw: str) -> dict:
        text = raw.strip()
        match = re.search(r"```(?:json)?\\s*(.*?)\\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def extract(self, metamodel_name: str, text) -> dict:
        prompt = f"Domain: {metamodel_name}\n\nText:\n{text}\n\nExtract concepts."
        response = self.chain.invoke({"input": prompt})
        raw = response.content if hasattr(response, "content") else str(response)
        parsed = self._parse_json(raw if isinstance(raw, str) else str(raw))
        parsed.setdefault("concepts", [])
        return parsed
