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
# plain "which concept means X" lookups (rejected: too easy), a run of
# near-identical "what is the key difference between X and Y" questions
# (rejected: monotonous), and single-correct-answer multiple choice
# (rejected: doesn't distinguish "confidently right" from "guessed right").
#
# Every question now has exactly 4 options, with exactly 2 correct and 2
# incorrect — participants select every option they believe is true, not
# just one. Scoring is per-option (see _compute_form_score): +1 for each
# correct option selected, +1 for each incorrect option correctly left
# unselected, out of 4 possible points per question. Across each bank, each
# of the 4 letters (A-D) is the "correct" slot in exactly 3 of the 6
# questions and "incorrect" in the other 3, so position alone never signals
# the answer.
#
# Each bank still mixes three question shapes, two of each:
#   - "definition" — 2 true statements about a concept vs. 2 statements that
#     actually describe a different concept
#   - "difference" — 1 true statement about each of two concepts vs. those
#     same two statements with the concepts swapped
#   - "composition/association" — how one concept is composed of, or linked
#     to, other concepts, as a plain fact about the domain's structure
#     (never phrased as "once X is generated" or "before X can be linked
#     in" — that's the tool's process, not something true of the domain
#     itself). A whole/part relationship is described with "composed of" /
#     "a composing part of", never "contains" or "container".

# Business Process — 7 concepts: Process, Activity, Actor, Event, Gateway,
# SequenceFlow, DataObject.
BP_PRE_QUESTIONS = [
    {
        "id": "q1",
        "text": "Which of the following are true about a Gateway in this business process? (select all that apply)",
        "options": [
            "A. A Gateway is a decision point in the process where the flow can branch",
            "B. A Gateway can direct the process down more than one possible path depending on a condition",
            "C. A Gateway is the role or person who carries out a task in the process",
            "D. A Gateway is a record of information exchanged between activities",
        ],
        "answers": ["A", "B"],
    },
    {
        "id": "q2",
        "text": "Which of the following are true about an Event in this business process? (select all that apply)",
        "options": [
            "A. An Event is a task carried out as part of the process",
            "B. An Event marks a moment such as the start or end of the process",
            "C. An Event can trigger the beginning of a task without being a task itself",
            "D. An Event is a document consumed or produced while the process runs",
        ],
        "answers": ["B", "C"],
    },
    {
        "id": "q3",
        "text": "Which of the following correctly describe the difference between an Activity and an Actor? (select all that apply)",
        "options": [
            "A. An Activity is the role or person who performs a task",
            "B. An Actor is a task performed as part of the process",
            "C. An Activity is a task performed as part of the process",
            "D. An Actor is the role or person who performs an Activity",
        ],
        "answers": ["C", "D"],
    },
    {
        "id": "q4",
        "text": "Which of the following correctly describe the difference between the Process and an Activity? (select all that apply)",
        "options": [
            "A. The Process is the entire business process that Activities are a composing part of",
            "B. The Process happens after every Activity, and an Activity happens after the Process ends",
            "C. An Activity is one composing part of the overall Process",
            "D. The Process is a document, and an Activity is a person",
        ],
        "answers": ["A", "C"],
    },
    {
        "id": "q5",
        "text": "Which two of the following concepts is the Process composed of? (select all that apply)",
        "options": [
            "A. Actor",
            "B. Activity",
            "C. DataObject",
            "D. Event",
        ],
        "answers": ["B", "D"],
    },
    {
        "id": "q6",
        "text": "Which of the following are true about how an Actor relates to other concepts? (select all that apply)",
        "options": [
            "A. An Actor is linked to an Activity to indicate who performs it",
            "B. An Actor is linked to a DataObject to indicate who performs it",
            "C. An Actor is composed of the Process, Event, and Gateway concepts",
            "D. An Actor is the role or person responsible for carrying out a task",
        ],
        "answers": ["A", "D"],
    },
]

BP_POST_QUESTIONS = [
    {
        "id": "q1",
        "text": "Which of the following are true about a SequenceFlow in this business process? (select all that apply)",
        "options": [
            "A. A SequenceFlow defines the order in which activities, events, and gateways occur",
            "B. A SequenceFlow is the role or person responsible for carrying out a task",
            "C. A SequenceFlow connects one process element to the next in the flow",
            "D. A SequenceFlow is a piece of information consumed or produced while the process runs",
        ],
        "answers": ["A", "C"],
    },
    {
        "id": "q2",
        "text": "Which of the following are true about a DataObject in this business process? (select all that apply)",
        "options": [
            "A. A DataObject is a decision point where the flow can branch",
            "B. A DataObject is information that is produced or consumed as part of an activity",
            "C. A DataObject is a moment marking the start or end of the process",
            "D. A DataObject can be passed along the process without itself performing any task",
        ],
        "answers": ["B", "D"],
    },
    {
        "id": "q3",
        "text": "Which of the following correctly describe the difference between an Actor and a DataObject? (select all that apply)",
        "options": [
            "A. An Actor is the role or person responsible for an Activity",
            "B. A DataObject is information used or produced by an Activity",
            "C. An Actor is information used or produced by an Activity",
            "D. A DataObject is the role or person responsible for an Activity",
        ],
        "answers": ["A", "B"],
    },
    {
        "id": "q4",
        "text": "Which of the following correctly describe the difference between the Process and a Gateway? (select all that apply)",
        "options": [
            "A. The Process happens only once, while a Gateway can repeat indefinitely",
            "B. The Process is a document, and a Gateway is a role",
            "C. The Process is the whole business process that a Gateway is one decision point within",
            "D. A Gateway is just one decision point within the overall Process",
        ],
        "answers": ["C", "D"],
    },
    {
        "id": "q5",
        "text": "Which of the following are true about how a DataObject relates to other concepts? (select all that apply)",
        "options": [
            "A. A DataObject must be linked to an Activity to show it is produced or consumed as part of a task",
            "B. A DataObject must be linked to a Gateway to show it is produced or consumed as part of a task",
            "C. A DataObject must be linked to an Event to show it is produced or consumed as part of a task",
            "D. A DataObject can represent information used by more than one Activity",
        ],
        "answers": ["A", "D"],
    },
    {
        "id": "q6",
        "text": "Which of the following are true about how an Activity relates to other concepts, besides the Actor responsible for it? (select all that apply)",
        "options": [
            "A. An Activity is always linked to a Gateway to be valid",
            "B. An Activity can be linked to a DataObject that it produces or consumes",
            "C. An Activity is connected to other elements of the flow through SequenceFlow",
            "D. An Activity is composed of the Process, Event, and Actor concepts",
        ],
        "answers": ["B", "C"],
    },
]

# Car's Engine — 7 concepts: Engine, Cylinder, Piston, Valve, Sensor,
# FuelInjector, ECU.
ENGINE_PRE_QUESTIONS = [
    {
        "id": "q1",
        "text": "Which of the following are true about a Piston? (select all that apply)",
        "options": [
            "A. A Piston moves up and down inside a cylinder to compress the air-fuel mixture",
            "B. A Piston measures a physical quantity such as temperature or pressure",
            "C. A Piston opens and closes to let air or exhaust gases in and out of a cylinder",
            "D. A Piston transmits the force of combustion to the engine's mechanical output",
        ],
        "answers": ["A", "D"],
    },
    {
        "id": "q2",
        "text": "Which of the following are true about a Valve? (select all that apply)",
        "options": [
            "A. A Valve reads and processes sensor data to make control decisions",
            "B. A Valve is where combustion takes place",
            "C. A Valve opens and closes to let air or exhaust gases in and out of a cylinder",
            "D. A Valve controls the timing of gas flow into and out of the combustion chamber",
        ],
        "answers": ["C", "D"],
    },
    {
        "id": "q3",
        "text": "Which of the following correctly describe the difference between a Sensor and the ECU? (select all that apply)",
        "options": [
            "A. A Sensor injects fuel, and the ECU moves the Piston",
            "B. A Sensor measures a physical quantity like temperature or oxygen level",
            "C. The ECU reads sensor data and makes control decisions",
            "D. A Sensor and the ECU are two names for the same component",
        ],
        "answers": ["B", "C"],
    },
    {
        "id": "q4",
        "text": "Which of the following correctly describe the difference between a Cylinder and the Engine? (select all that apply)",
        "options": [
            "A. The Engine is the overall assembly composed of multiple Cylinders",
            "B. A Cylinder is one combustion chamber within the Engine",
            "C. The Engine only has one Cylinder, always",
            "D. The Engine is a Sensor, and a Cylinder is an ECU",
        ],
        "answers": ["A", "B"],
    },
    {
        "id": "q5",
        "text": "Which two of the following concepts is the Cylinder composed of? (select all that apply)",
        "options": [
            "A. Piston",
            "B. ECU",
            "C. FuelInjector",
            "D. Sensor",
        ],
        "answers": ["A", "C"],
    },
    {
        "id": "q6",
        "text": "Which of the following are true about how the ECU relates to other concepts? (select all that apply)",
        "options": [
            "A. The ECU only monitors or controls other ECUs",
            "B. The ECU monitors data coming from Sensors",
            "C. The ECU is a component that physically sprays fuel into the cylinder",
            "D. The ECU controls the behavior of FuelInjectors",
        ],
        "answers": ["B", "D"],
    },
]

ENGINE_POST_QUESTIONS = [
    {
        "id": "q1",
        "text": "Which of the following are true about the ECU? (select all that apply)",
        "options": [
            "A. The ECU physically sprays fuel into the cylinder",
            "B. The ECU opens and closes to control gas flow into a cylinder",
            "C. The ECU receives sensor data and decides how the engine should respond",
            "D. The ECU can adjust fuel delivery based on the conditions it detects",
        ],
        "answers": ["C", "D"],
    },
    {
        "id": "q2",
        "text": "Which of the following are true about a FuelInjector? (select all that apply)",
        "options": [
            "A. A FuelInjector physically sprays fuel into the cylinder",
            "B. A FuelInjector measures a physical condition such as oxygen level",
            "C. A FuelInjector moves up and down to compress the air-fuel mixture",
            "D. A FuelInjector releases fuel based on timing decided by the ECU",
        ],
        "answers": ["A", "D"],
    },
    {
        "id": "q3",
        "text": "Which of the following correctly describe the difference between the ECU and a FuelInjector? (select all that apply)",
        "options": [
            "A. The ECU sprays fuel, and the FuelInjector makes control decisions",
            "B. The ECU decides how much fuel to deliver and when",
            "C. The ECU and the FuelInjector are interchangeable names for the same part",
            "D. The FuelInjector is the component that physically sprays that fuel into the Cylinder",
        ],
        "answers": ["B", "D"],
    },
    {
        "id": "q4",
        "text": "Which of the following correctly describe the difference between a Piston and a Cylinder? (select all that apply)",
        "options": [
            "A. A Piston is the chamber, and a Cylinder moves inside it",
            "B. A Cylinder is composed of a Piston that moves up and down inside it",
            "C. A Piston is a composing part that moves within the Cylinder",
            "D. A Piston and a Cylinder are unrelated, appearing in different engines",
        ],
        "answers": ["B", "C"],
    },
    {
        "id": "q5",
        "text": "Which of the following are true about the Engine's composition? (select all that apply)",
        "options": [
            "A. The Engine is composed of multiple Cylinders",
            "B. The Engine's internal structure is composed of Cylinders along with components such as Sensors and the ECU",
            "C. The Engine is one of several components inside a single Cylinder",
            "D. The Engine and a Sensor are the same kind of component",
        ],
        "answers": ["A", "B"],
    },
    {
        "id": "q6",
        "text": "Which of the following are true about how a Sensor relates to other concepts? (select all that apply)",
        "options": [
            "A. A Sensor must be linked to the ECU so its readings can be used to adjust engine behavior",
            "B. A Sensor must be linked to a Piston so its readings can be used",
            "C. A Sensor provides data that supports the ECU's control decisions",
            "D. A Sensor must be linked to a Valve so its readings can be used",
        ],
        "answers": ["A", "C"],
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
        # Same 7 names the quiz banks above are calibrated against — passed to
        # both generation paths (see app.py) so what gets built actually
        # matches what the questionnaire asks about.
        "concepts": ["Process", "Activity", "Actor", "Event", "Gateway", "SequenceFlow", "DataObject"],
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
        "concepts": ["Engine", "Cylinder", "Piston", "Valve", "Sensor", "FuelInjector", "ECU"],
        "pre": ENGINE_PRE_QUESTIONS,
        "post": ENGINE_POST_QUESTIONS,
    },
}


def _compute_form_score(responses: dict[str, object], questions: list[dict]) -> int:
    """Per-option scoring: +1 for each correct option selected, +1 for each
    incorrect option correctly left unselected — 4 points max per question
    (2 correct options + 2 incorrect options). Returned as a 0-100 score,
    normalized by the maximum achievable points, to stay compatible with the
    rest of the app (profiles, CSV logs) which already store scores that way.
    """
    total_questions = len(questions)
    if total_questions == 0:
        return 0

    max_points = total_questions * 4
    points = 0
    for question in questions:
        raw = responses.get(question["id"]) or []
        selected = [raw] if isinstance(raw, str) else list(raw)
        selected_letters = {choice.strip()[0].upper() for choice in selected if choice.strip()}
        correct_letters = {letter.upper() for letter in question["answers"]}
        all_letters = {option.strip()[0].upper() for option in question["options"]}
        incorrect_letters = all_letters - correct_letters

        points += sum(1 for letter in correct_letters if letter in selected_letters)
        points += sum(1 for letter in incorrect_letters if letter not in selected_letters)

    return round((points / max_points) * 100)
