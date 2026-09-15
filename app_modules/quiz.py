from __future__ import annotations

import typing

QUIZ_QUESTIONS = [
    {
        "id": "q1",
        "text": "In a state machine metamodel, how is the starting point of execution typically represented?",
        "options": [
            "A. By a separate InitialState class that has no incoming transitions",
            "B. By adding a boolean attribute like isInitial directly on the State class",
            "C. By naming one state \"start\" — the name is enough to identify the entry point",
        ],
        "answer": "B",
    },
    {
        "id": "q2",
        "text": "A State has three action slots: entry, exit, and doActivity. When does the doActivity action execute?",
        "options": [
            "A. Only when the state is visited for the second time",
            "B. Once when the state is entered, then not again until the state is exited and re-entered",
            "C. Continuously while the system remains in that state",
        ],
        "answer": "C",
    },
    {
        "id": "q3",
        "text": "In a metamodel, what is the difference between a containment reference and a regular reference?",
        "options": [
            "A. A containment reference means the owned element cannot exist without its owner; a regular reference is a link between independent elements",
            "B. Containment references are only used for attributes like name or description",
            "C. There is no practical difference — both express the same relationship",
        ],
        "answer": "A",
    },
    {
        "id": "q4",
        "text": "A Transition class has both a trigger attribute of type String and a triggerEvent reference pointing to an Event class. What problem does this create?",
        "options": [
            "A. It is impossible to have both a String attribute and a reference in the same class",
            "B. Two different mechanisms represent the same concept, making it unclear which one to use and risking inconsistent models",
            "C. The triggerEvent reference will always override the trigger attribute at runtime",
        ],
        "answer": "B",
    },
    {
        "id": "q5",
        "text": "Which multiplicity is correct for the states reference in StateMachine, and why?",
        "options": [
            "A. [0..*] — a state machine may start with no states during construction",
            "B. [1..*] — a state machine must always contain at least one state to be meaningful",
            "C. [1..1] — a state machine has exactly one active state at any given moment",
        ],
        "answer": "B",
    },
    {
        "id": "q6",
        "text": "What does it mean when a Transition has no event and no guard set?",
        "options": [
            "A. The transition is incomplete and will be rejected by the metamodel validator",
            "B. It fires automatically once the source state finishes its internal activity",
            "C. It means the transition is disabled and will never fire",
        ],
        "answer": "B",
    },
    {
        "id": "q7",
        "text": "Why might a Guard be modeled as a separate class with an expression attribute, rather than just a String attribute directly on Transition?",
        "options": [
            "A. String attributes cannot hold logical expressions in most modeling frameworks",
            "B. A separate class gives the guard its own identity, allows reuse, and makes it easier to add metadata like a name or language later",
            "C. It is purely a visual convention — both designs behave identically",
        ],
        "answer": "B",
    },
    {
        "id": "q8",
        "text": "A State has a containment reference subStates pointing to other State instances. What kind of structure does this enable?",
        "options": [
            "A. It allows multiple state machines to share the same set of states",
            "B. It enables hierarchical (nested) states where a state can contain other states",
            "C. It creates a linked list of states that the machine visits in order",
        ],
        "answer": "B",
    },
    {
        "id": "q9",
        "text": "In a state machine metamodel, source and target on Transition are typed as State. What scenario does this prevent?",
        "options": [
            "A. Self-transitions where source and target are the same state",
            "B. Transitions that connect to pseudostates like junctions or choice nodes, which are not plain State instances",
            "C. Transitions that carry no event",
        ],
        "answer": "B",
    },
    {
        "id": "q10",
        "text": "A validator flags: 'redundancy between trigger attribute and triggerEvent reference.' What is the recommended fix?",
        "options": [
            "A. Remove the triggerEvent reference and keep only the String trigger attribute",
            "B. Remove the String trigger attribute and keep only the triggerEvent reference to the Event class",
            "C. Choose one representation and apply it consistently — either the attribute or the reference, not both",
        ],
        "answer": "C",
    },
    {
        "id": "q11",
        "text": "What is the purpose of entry and exit actions on a State?",
        "options": [
            "A. Entry actions execute when the state is entered regardless of which transition caused it; exit actions execute when the state is left regardless of which transition fires",
            "B. Entry actions execute only on the first visit; exit actions execute only on the last visit before the machine terminates",
            "C. They replace guards — entry actions check if entry is allowed, exit actions check if exit is allowed",
        ],
        "answer": "A",
    },
    {
        "id": "q12",
        "text": "A StateMachine uses a regular reference (not containment) to link to its State instances. What risk does this introduce?",
        "options": [
            "A. States could exist independently of any state machine, with no owner responsible for their lifecycle",
            "B. The state machine would be unable to have more than one state",
            "C. References are not supported for collections in metamodeling tools",
        ],
        "answer": "A",
    },
    {
        "id": "q13",
        "text": "In the metamodel, Action has a code attribute of type String. What is the main limitation of this for a tool that needs to execute or analyse the action?",
        "options": [
            "A. String attributes cannot store multi-line content",
            "B. The code is opaque — the tool cannot parse, validate, or transform it without treating it as raw uninterpreted text",
            "C. It forces every action to be written in the same programming language",
        ],
        "answer": "B",
    },
    {
        "id": "q14",
        "text": "A participant generates a metamodel where Guard has a relatedTransition reference back to Transition, and Transition already has a guard reference to Guard. What issue does this raise?",
        "options": [
            "A. A bidirectional reference between Guard and Transition can cause navigation ambiguity and should be carefully managed to avoid redundancy",
            "B. Bidirectional references are forbidden in all metamodeling frameworks",
            "C. There is no issue — bidirectional references are always the correct design",
        ],
        "answer": "A",
    },
    {
        "id": "q15",
        "text": "After generating each concept chunk, the system validates the metamodel against a sample instance. What is the purpose of this validation step?",
        "options": [
            "A. To check that the generated metamodel can actually represent a realistic example, catching missing classes or attributes before moving to the next concept",
            "B. To automatically deploy the metamodel to a production environment",
            "C. To measure how fast the language model generated the metamodel",
        ],
        "answer": "A",
    },
]


def _compute_form_score(responses: dict[str, object], questions: list[dict] = QUIZ_QUESTIONS) -> int:
    total = len(questions)
    if total == 0:
        return 0

    correct = 0
    for question in questions:
        raw = responses.get(question["id"]) or []
        selected = [raw] if isinstance(raw, str) else list(raw)
        letters = {choice.strip()[0].upper() for choice in selected if choice.strip()}
        if letters == {question["answer"].upper()}:
            correct += 1

    return round((correct / total) * 100)
