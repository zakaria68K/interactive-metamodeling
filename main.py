from metaLoop.metamodeling_agent import MetamodelingAgent


def main() -> None:
    prompt = "define a metamodel for state machines"

    app = MetamodelingAgent().create_metamodeling_agent()
    result = app.invoke({"messages": [{"role": "user", "content": prompt}]})
    messages = result.get("messages", [])
    
    print(messages[-1].content if messages else "No response produced.")


if __name__ == "__main__":
    main()