from .system_prompt import prompt
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
import os
load_dotenv()


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


class MetamodelingAgent:
    def __init__(self):
        openai_model = os.getenv("OPENAI_MODEL", "gpt-5.3-chat-latest")
        self.model = ChatOpenAI(
            model=openai_model,
            temperature=0.1,
            max_retries=2
        )
        self.system_prompt = prompt
        self.llm = ChatOpenAI(model=openai_model)

    def _agent(self, state: State) -> State:
        messages = list(state.get("messages", []))
        llm_messages = messages
        if not messages or messages[0].type != "system": 
            llm_messages = [SystemMessage(content=self.system_prompt), *messages]

        response = self.llm.invoke(llm_messages)
        return {"messages": [response]}

    def create_metamodeling_agent(self):
        builder = StateGraph(State)
        builder.add_node("agent", self._agent)
        builder.add_edge(START, "agent")
        builder.add_edge("agent", END)
        return builder.compile()
