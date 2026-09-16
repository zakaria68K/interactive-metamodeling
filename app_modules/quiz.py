from __future__ import annotations

# Two study domains, each with a fixed domain-prompt description (so every
# participant in that domain builds the same metamodel, per User-study.md)
# and its own pre/post question bank. Pre and post ask different questions
# about the same underlying metamodeling concepts, per domain.
#
# Every question has exactly 3 options and, within each 6-question bank,
# correct answers are split evenly 2/2/2 across A/B/C. Questions test
# well-established, unambiguous metamodeling principles (containment vs.
# reference, redundant representation, opaque fields, typed references, why
# validate against a sample instance) — never a "what's the right
# cardinality/design here" question, since a domain can be modeled more than
# one valid way and that isn't a fair knowledge-gain measure.
# Each domain's underlying metamodel is capped at ~7 concepts to match the
# tool's concept-by-concept iteration.

BP_PRE_QUESTIONS = [
    {
        "id": "q1",
        "text": "In a business process metamodel, how should the relationship between an Activity and the Actor who performs it typically be modeled?",
        "options": [
            "A. As a containment reference, since the Actor only exists within that one Activity",
            "B. As a regular (non-containment) reference, since the Actor exists independently and may perform activities in other processes too",
            "C. As a copied attribute storing the actor's name as free text on the Activity",
        ],
        "answer": "B",
    },
    {
        "id": "q2",
        "text": "An Activity has both an attribute assignedActorName: String and a reference assignedTo: Actor meant to record the same person. What problem does this create?",
        "options": [
            "A. It's technically impossible to have both a string attribute and a reference on the same class",
            "B. The reference will always silently overwrite the attribute at runtime",
            "C. Two different mechanisms represent the same fact, so they can drift out of sync and it's unclear which one a tool should trust",
        ],
        "answer": "C",
    },
    {
        "id": "q3",
        "text": "Process has a containment reference to its Activities. What does this guarantee?",
        "options": [
            "A. Each Activity belongs to exactly one Process, which is responsible for its lifecycle — it cannot outlive or be shared outside its owning Process",
            "B. Activities can be freely shared and reused across multiple different Processes",
            "C. The Process can contain at most one Activity at a time",
        ],
        "answer": "A",
    },
    {
        "id": "q4",
        "text": "An Activity has a logic: String attribute holding free-text instructions for what it does. What's the main limitation for a tool that wants to analyze or execute the process?",
        "options": [
            "A. String attributes cannot store more than one sentence of text",
            "B. The logic is opaque — the tool can only treat it as raw text; it cannot parse, validate, or transform it",
            "C. It forces every Activity in the process to use identical instructions",
        ],
        "answer": "B",
    },
    {
        "id": "q5",
        "text": "After generating each concept chunk of a metamodel, the system validates it against a sample process instance. What's the purpose?",
        "options": [
            "A. To automatically publish the process model to a production workflow engine",
            "B. To measure how quickly the language model generated the chunk",
            "C. To check that the metamodel generated so far can represent a realistic example, catching missing classes or attributes before moving on",
        ],
        "answer": "C",
    },
    {
        "id": "q6",
        "text": "SequenceFlow's source/target are typed as the abstract class FlowNode (which Activity, Event, and Gateway inherit from), not as Object. What does this typing prevent?",
        "options": [
            "A. Connecting a SequenceFlow to something that isn't part of the process flow at all, such as a DataObject",
            "B. Having more than one SequenceFlow leave the same Gateway",
            "C. An Activity from having more than one incoming SequenceFlow",
        ],
        "answer": "A",
    },
]

BP_POST_QUESTIONS = [
    {
        "id": "q1",
        "text": "If Process referenced its Activities with a plain (non-containment) reference instead of containment, what risk does this introduce?",
        "options": [
            "A. Activities could exist independently of any Process, with no owner responsible for their lifecycle",
            "B. The Process would be limited to exactly one Activity",
            "C. Plain references cannot point to more than one Activity at a time",
        ],
        "answer": "A",
    },
    {
        "id": "q2",
        "text": "Activity has a nextActivity reference to the following Activity, and that Activity has a previousActivity reference pointing back. What issue can this bidirectional pair introduce?",
        "options": [
            "A. Bidirectional references are rejected by every metamodeling tool",
            "B. Navigation ambiguity and redundancy — both sides must be kept consistent, which is easy to get wrong",
            "C. It makes it impossible to ever remove an Activity from the process",
        ],
        "answer": "B",
    },
    {
        "id": "q3",
        "text": "A Gateway needs a branching rule. Why might that rule be modeled as its own Condition class with an expression attribute, rather than a plain String on Gateway?",
        "options": [
            "A. String attributes cannot hold logical expressions in most modeling frameworks",
            "B. It's purely a stylistic choice with no practical difference",
            "C. A separate class gives the condition its own identity, allows reuse, and makes it easier to attach extra metadata later",
        ],
        "answer": "C",
    },
    {
        "id": "q4",
        "text": "A DataObject may be produced by one Activity and later consumed by several others in the same Process. Why is this typically a reference, not containment?",
        "options": [
            "A. The DataObject's existence isn't tied to any single Activity — it can be shared and outlive the Activity that created it",
            "B. References are the only relationship type Gateways are allowed to have",
            "C. Containment references cannot be used between two Activities",
        ],
        "answer": "A",
    },
    {
        "id": "q5",
        "text": "Once the full process metamodel is generated, a final validation checks it against sample instances. What does this check primarily verify?",
        "options": [
            "A. That the model file is small enough to email",
            "B. That the complete metamodel is internally consistent and can represent a realistic end-to-end process, not just isolated chunks",
            "C. That every Activity has a unique color assigned for the diagram",
        ],
        "answer": "B",
    },
    {
        "id": "q6",
        "text": "SequenceFlow has both a conditionText: String attribute and a separate guard: Condition reference, both meant to capture the same branching rule. What should be done?",
        "options": [
            "A. Keep both, since redundant representations make the model more robust",
            "B. Delete the SequenceFlow class entirely",
            "C. Choose one representation and apply it consistently — either the attribute or the reference, not both",
        ],
        "answer": "C",
    },
]

ENGINE_PRE_QUESTIONS = [
    {
        "id": "q1",
        "text": "How should the relationship between the ECU and a Sensor it reads from typically be modeled?",
        "options": [
            "A. As a containment reference, since the Sensor cannot exist without the ECU",
            "B. As a regular (non-containment) reference, since the Sensor is a physical part of the Engine and doesn't depend on which ECU reads it",
            "C. As a duplicated copy of the sensor's readings stored as a string on the ECU",
        ],
        "answer": "B",
    },
    {
        "id": "q2",
        "text": "A FuelInjector has a controlLogic: String attribute holding raw controller code as text. What's the main limitation for a tool that needs to simulate or validate engine behavior?",
        "options": [
            "A. String attributes cannot store more than a few characters",
            "B. It forces every FuelInjector in the engine to run identical code",
            "C. The code is opaque — the tool can't parse, validate, or transform it without treating it as raw text",
        ],
        "answer": "C",
    },
    {
        "id": "q3",
        "text": "Engine has a containment reference to its Cylinders. What does this guarantee?",
        "options": [
            "A. Each Cylinder belongs to exactly one Engine, which owns its lifecycle — it cannot exist independently or be shared with another Engine",
            "B. Cylinders can be freely shared across multiple different Engines",
            "C. The Engine can contain at most one Cylinder",
        ],
        "answer": "A",
    },
    {
        "id": "q4",
        "text": "ECU has a monitors reference typed specifically as Sensor (not as Object). What does this prevent?",
        "options": [
            "A. The ECU from monitoring more than one Sensor at a time",
            "B. The ECU from being linked to something that isn't a Sensor at all, such as a FuelInjector or unrelated component",
            "C. Two different ECUs from monitoring the same Sensor",
        ],
        "answer": "B",
    },
    {
        "id": "q5",
        "text": "After generating each concept chunk of the engine metamodel, the system validates it against a sample engine instance. What's the purpose?",
        "options": [
            "A. To automatically order replacement parts for the engine",
            "B. To measure how fast the language model generated the chunk",
            "C. To check that the metamodel generated so far can represent a realistic engine configuration, catching missing classes or attributes early",
        ],
        "answer": "C",
    },
    {
        "id": "q6",
        "text": "Cylinder has both a pistonPositionMM: Number attribute and a piston: Piston reference, where the attribute duplicates information already available through Piston. What problem does this create?",
        "options": [
            "A. Two different mechanisms represent overlapping information, so they can drift out of sync and it's unclear which to trust",
            "B. It's technically impossible to have both an attribute and a reference on the same class",
            "C. The reference will always override the attribute automatically",
        ],
        "answer": "A",
    },
]

ENGINE_POST_QUESTIONS = [
    {
        "id": "q1",
        "text": "If Engine referenced its Cylinders with a plain (non-containment) reference instead of containment, what risk does this introduce?",
        "options": [
            "A. Cylinders could exist independently of any Engine, with no owner responsible for their lifecycle",
            "B. The Engine would be limited to exactly one Cylinder",
            "C. Plain references cannot point to more than one Cylinder at a time",
        ],
        "answer": "A",
    },
    {
        "id": "q2",
        "text": "Valve has a pairedValve reference to its counterpart valve in the same cylinder, and that Valve references back. What issue can this bidirectional pair introduce?",
        "options": [
            "A. Bidirectional references are forbidden in all metamodeling frameworks",
            "B. Navigation ambiguity and redundancy — both sides must be kept in sync, which is easy to get wrong",
            "C. It makes it impossible to ever remove a Valve from the Cylinder",
        ],
        "answer": "B",
    },
    {
        "id": "q3",
        "text": "FuelInjector needs a timing rule for when it fires. Why might that rule be modeled as its own InjectionTiming class with attributes, rather than a plain String on FuelInjector?",
        "options": [
            "A. String attributes cannot represent numeric timing values in most frameworks",
            "B. It's purely a stylistic choice with no practical difference",
            "C. A separate class gives the timing rule its own identity, allows reuse across injectors, and makes it easier to attach extra metadata later",
        ],
        "answer": "C",
    },
    {
        "id": "q4",
        "text": "Piston is contained in Cylinder rather than referenced. Why is containment the appropriate choice here?",
        "options": [
            "A. A Piston has no meaningful existence or function outside the specific Cylinder it operates in",
            "B. References are the only relationship type Cylinders are allowed to have",
            "C. Containment references cannot be used between two physical parts",
        ],
        "answer": "A",
    },
    {
        "id": "q5",
        "text": "Once the full engine metamodel is generated, a final validation checks it against sample instances. What does this check primarily verify?",
        "options": [
            "A. That the model file is small enough to email",
            "B. That the complete metamodel is internally consistent and can represent a realistic, fully assembled engine, not just isolated chunks",
            "C. That every Cylinder has a unique paint color assigned",
        ],
        "answer": "B",
    },
    {
        "id": "q6",
        "text": "ECU has both an injectorStatusText: String attribute and an injectors: [FuelInjector] reference, both meant to describe the same injectors and their state. What should be done?",
        "options": [
            "A. Keep both, since redundant representations make the model more robust",
            "B. Delete the ECU class entirely",
            "C. Choose one representation and apply it consistently — either the attribute or the reference, not both",
        ],
        "answer": "C",
    },
]

# Fixed domain-prompt text: every participant assigned to a domain builds the
# same metamodel (User-study.md calls for "a short natural language prompt
# provided by the researchers", not a free choice per participant).
DOMAINS = {
    "bp": {
        "label": "Business Process",
        "prompt": (
            "A company wants to manage its order-to-cash business process: how a "
            "customer order becomes a series of activities carried out by different "
            "roles, using and producing documents, until the order is fulfilled."
        ),
        "pre": BP_PRE_QUESTIONS,
        "post": BP_POST_QUESTIONS,
    },
    "engine": {
        "label": "Car's Engine",
        "prompt": (
            "A car manufacturer wants to describe the internal structure of a "
            "combustion engine: how cylinders, pistons, valves, fuel injectors, "
            "sensors, and the control unit relate to each other."
        ),
        "pre": ENGINE_PRE_QUESTIONS,
        "post": ENGINE_POST_QUESTIONS,
    },
}


def _compute_form_score(responses: dict[str, object], questions: list[dict]) -> int:
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
