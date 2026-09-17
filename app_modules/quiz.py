from __future__ import annotations

# Two study domains, each with a fixed domain-prompt description (so every
# participant in that domain builds the same metamodel, per User-study.md)
# and its own pre/post question bank. Pre and post ask different questions
# about the same underlying concepts, per domain.
#
# Each domain is fixed to exactly 7 target concepts (matching the tool's
# concept-by-concept iteration). Earlier drafts of this file tried MDE-theory
# questions (rejected: answerable by a good modeler without ever using the
# tool), "spot the flaw in this generated class" questions (rejected: the
# flaw is hypothetical, not guaranteed to appear in any given generation),
# and plain "which concept means X" lookups (rejected: too easy — many of
# these concept names are self-explanatory).
#
# Each 6-question bank now mixes two question shapes:
#   - "distinguish" — what separates two similar concepts from each other
#   - "relationship" — how one concept connects to / depends on / contains
#     another, phrased around the fact that this only becomes clear once the
#     metamodel is actually built concept by concept (you can't know it from
#     the domain prompt alone)
# Phrasing is varied within and across banks so the same template doesn't
# repeat six times in a row. Every question still has exactly 3 options with
# a fixed, unambiguous answer from the 7-concept map — never a design choice
# or something specific to one session's generation — and each bank splits
# correct answers evenly 2/2/2 across A/B/C.

# Business Process — 7 concepts: Process, Activity, Actor, Event, Gateway,
# SequenceFlow, DataObject.
BP_PRE_QUESTIONS = [
    {
        "id": "q1",
        "text": "What is the key difference between a Gateway and an Event in this process model?",
        "options": [
            "A. A Gateway is a decision point where the flow can branch; an Event marks a moment such as the start or end of the process",
            "B. A Gateway produces a document; an Event assigns an Actor",
            "C. A Gateway can only appear once per process; an Event can appear multiple times",
        ],
        "answer": "A",
    },
    {
        "id": "q2",
        "text": "When the tool builds the Actor concept, which existing concept does it connect Actor to, in order to say who performs which work?",
        "options": [
            "A. DataObject",
            "B. Activity",
            "C. Event",
        ],
        "answer": "B",
    },
    {
        "id": "q3",
        "text": "What is the key difference between an Activity and an Actor in this process model?",
        "options": [
            "A. An Activity always follows a Gateway; an Actor always precedes a SequenceFlow",
            "B. An Activity is a document; an Actor is a decision point",
            "C. An Activity is a task performed as part of the process; an Actor is the role or person who performs it",
        ],
        "answer": "C",
    },
    {
        "id": "q4",
        "text": "A SequenceFlow needs a source and a target. Which kinds of concepts can those be?",
        "options": [
            "A. Activities, Events, or Gateways",
            "B. Only Actors",
            "C. Only DataObjects",
        ],
        "answer": "A",
    },
    {
        "id": "q5",
        "text": "What is the key difference between the Process and an Activity?",
        "options": [
            "A. The Process happens after every Activity; an Activity happens after the Process ends",
            "B. The Process is the overall container for the whole model; an Activity is one task within it",
            "C. The Process is a document; an Activity is a person",
        ],
        "answer": "B",
    },
    {
        "id": "q6",
        "text": "Which concept sits at the top of the containment chain, owning every Activity, Event, and Gateway once they're generated?",
        "options": [
            "A. SequenceFlow",
            "B. Actor",
            "C. Process",
        ],
        "answer": "C",
    },
]

BP_POST_QUESTIONS = [
    {
        "id": "q1",
        "text": "What is the key difference between a SequenceFlow and a DataObject?",
        "options": [
            "A. A SequenceFlow defines the order activities happen in; a DataObject represents information passed along the way, not the order itself",
            "B. A SequenceFlow is a role; a DataObject is a decision point",
            "C. A SequenceFlow only appears at the start of the process; a DataObject only appears at the end",
        ],
        "answer": "A",
    },
    {
        "id": "q2",
        "text": "Once a DataObject concept is generated, which other concept must already exist for the DataObject to be linked as something it's produced or consumed by?",
        "options": [
            "A. Gateway",
            "B. Event",
            "C. Activity",
        ],
        "answer": "C",
    },
    {
        "id": "q3",
        "text": "What is the key difference between an Actor and a DataObject?",
        "options": [
            "A. An Actor always follows a SequenceFlow; a DataObject always precedes a Gateway",
            "B. An Actor is a decision point; a DataObject is a moment in time",
            "C. An Actor is the role or person responsible for an Activity; a DataObject is information used or produced by an Activity",
        ],
        "answer": "C",
    },
    {
        "id": "q4",
        "text": "A Gateway needs to connect to other elements to fit into the process flow. Which kinds of concepts can it connect to via SequenceFlow?",
        "options": [
            "A. Activities, Events, or other Gateways",
            "B. Only DataObjects",
            "C. Only Actors",
        ],
        "answer": "A",
    },
    {
        "id": "q5",
        "text": "What is the key difference between the Process and a Gateway?",
        "options": [
            "A. The Process happens only once; a Gateway can repeat indefinitely",
            "B. The Process is the container for the entire model; a Gateway is just one decision point within it",
            "C. The Process is a document; a Gateway is a role",
        ],
        "answer": "B",
    },
    {
        "id": "q6",
        "text": "Which concept represents something an Activity is linked to, other than the Actor responsible for it?",
        "options": [
            "A. Gateway",
            "B. DataObject",
            "C. Event",
        ],
        "answer": "B",
    },
]

# Car's Engine — 7 concepts: Engine, Cylinder, Piston, Valve, Sensor,
# FuelInjector, ECU.
ENGINE_PRE_QUESTIONS = [
    {
        "id": "q1",
        "text": "What is the key difference between a Piston and a Valve inside a Cylinder?",
        "options": [
            "A. The Piston moves up and down to compress the air-fuel mixture; the Valve opens and closes to let air or exhaust gases in and out",
            "B. The Piston reads sensor data; the Valve injects fuel",
            "C. The Piston is controlled by the ECU only; the Valve is controlled by the FuelInjector only",
        ],
        "answer": "A",
    },
    {
        "id": "q2",
        "text": "Before a FuelInjector concept can be linked into the engine metamodel, which concept must already exist to contain it?",
        "options": [
            "A. ECU",
            "B. Sensor",
            "C. Cylinder",
        ],
        "answer": "C",
    },
    {
        "id": "q3",
        "text": "What is the key difference between a Sensor and the ECU?",
        "options": [
            "A. A Sensor injects fuel; the ECU moves the Piston",
            "B. A Sensor measures a physical quantity like temperature; the ECU reads that data and makes control decisions",
            "C. A Sensor is contained in the FuelInjector; the ECU is contained in the Valve",
        ],
        "answer": "B",
    },
    {
        "id": "q4",
        "text": "Which concepts does the ECU directly monitor or control in this engine model?",
        "options": [
            "A. Sensors and FuelInjectors",
            "B. Only the Engine itself, nothing more specific",
            "C. Only other ECUs",
        ],
        "answer": "A",
    },
    {
        "id": "q5",
        "text": "What is the key difference between a Cylinder and the Engine?",
        "options": [
            "A. The Engine only has one Cylinder, always",
            "B. The Engine is the overall assembly that contains multiple Cylinders; a Cylinder is one combustion chamber within it",
            "C. The Engine is a Sensor; a Cylinder is an ECU",
        ],
        "answer": "B",
    },
    {
        "id": "q6",
        "text": "As the metamodel is generated concept by concept, which single concept ends up being the container for the Piston, the Valve, and the FuelInjector alike?",
        "options": [
            "A. ECU",
            "B. Sensor",
            "C. Cylinder",
        ],
        "answer": "C",
    },
]

ENGINE_POST_QUESTIONS = [
    {
        "id": "q1",
        "text": "What is the key difference between a Valve and a Sensor?",
        "options": [
            "A. A Valve controls the physical flow of gases in and out of a Cylinder; a Sensor measures a condition like temperature or oxygen level",
            "B. A Valve reads data; a Sensor sprays fuel",
            "C. A Valve is a type of ECU; a Sensor is a type of FuelInjector",
        ],
        "answer": "A",
    },
    {
        "id": "q2",
        "text": "Which component reads data from a Sensor in order to adjust engine behavior?",
        "options": [
            "A. The ECU",
            "B. A Valve",
            "C. A Piston",
        ],
        "answer": "A",
    },
    {
        "id": "q3",
        "text": "What is the key difference between the ECU and a FuelInjector?",
        "options": [
            "A. The ECU sprays fuel; the FuelInjector makes control decisions",
            "B. The ECU decides how much fuel to deliver and when; the FuelInjector is the component that physically sprays that fuel into the Cylinder",
            "C. The ECU and the FuelInjector are interchangeable names for the same part",
        ],
        "answer": "B",
    },
    {
        "id": "q4",
        "text": "Once the Sensor concept exists in the metamodel, which concept does it need to be linked to so its readings can actually be used?",
        "options": [
            "A. Piston",
            "B. ECU",
            "C. Valve",
        ],
        "answer": "B",
    },
    {
        "id": "q5",
        "text": "What is the key difference between a Piston and a Cylinder?",
        "options": [
            "A. A Piston is the chamber; a Cylinder moves inside it",
            "B. A Piston and a Cylinder are unrelated, appearing in different engines",
            "C. A Cylinder is the chamber that houses a Piston, which moves up and down inside it",
        ],
        "answer": "C",
    },
    {
        "id": "q6",
        "text": "Which single concept, once generated, becomes the container that every Cylinder in the engine belongs to?",
        "options": [
            "A. Sensor",
            "B. ECU",
            "C. Engine",
        ],
        "answer": "C",
    },
]

# Fixed domain-prompt text: every participant assigned to a domain builds the
# same metamodel (User-study.md calls for "a short natural language prompt
# provided by the researchers", not a free choice per participant). Each
# prompt is worded to clearly imply all 7 target concepts for that domain,
# so the metamodel actually built has something to say about each of them.
DOMAINS = {
    "bp": {
        "label": "Business Process",
        "prompt": (
            "A company wants to manage its order-to-cash business process: starting "
            "when a customer order is received and ending when it is fulfilled, the "
            "process runs through a sequence of activities carried out by different "
            "roles, includes decision points where the flow can branch, and produces "
            "or consumes documents along the way."
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