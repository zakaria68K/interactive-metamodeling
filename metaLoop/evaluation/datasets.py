"""
Evaluation dataset: domain configs with prompts and per-user target concept lists.

Each domain has three simulated users that differ in competency, emotion, verbosity,
and interaction strategy — covering the trait space recommended by:
  - "A Survey on LLM-based Conversational User Simulation" (heterogeneous trait modeling)
  - "PersonaLLM: Investigating the Ability of LLMs to Express Personality Traits"

User tiers per domain
─────────────────────
  All three users share the same full target_concepts list for the domain.
  Differentiation is purely through behavioral traits:
  novice       : anxious, terse, confirmatory
  intermediate : enthusiastic, moderate, exploratory
  expert       : calm, verbose, goal_directed

All three users per domain share the same sample file (the most complete one for that
domain) so that input context is controlled and result differences reflect traits only.
"""

DOMAIN_CONFIGS: dict[str, dict] = {
    "state_machine": {
        "prompt": "I want a state machine metamodel for interactive applications.",
        "users": [
            {
                "role": "novice",
                "sample_suffix": "events",
                "target_concepts": ["State", "Event", "Transition", "Trigger", "StateMachine", "Guard", "Action", "Region", "InitialState", "FinalState"],
                "emotion": "anxious",
                "verbosity": "terse",
                "strategy": "confirmatory",
                "competency": "novice",
            },
            {
                "role": "intermediate",
                "sample_suffix": "events",
                "target_concepts": ["State", "Event", "Transition", "Trigger", "StateMachine", "Guard", "Action", "Region", "InitialState", "FinalState"],
                "emotion": "enthusiastic",
                "verbosity": "moderate",
                "strategy": "exploratory",
                "competency": "intermediate",
            },
            {
                "role": "expert",
                "sample_suffix": "events",
                "target_concepts": ["State", "Event", "Transition", "Trigger", "StateMachine", "Guard", "Action", "Region", "InitialState", "FinalState"],
                "emotion": "calm",
                "verbosity": "verbose",
                "strategy": "goal_directed",
                "competency": "expert",
            },
        ],
    },
    "university": {
        "prompt": "I want a university course management metamodel.",
        "users": [
            {
                "role": "novice",
                "sample_suffix": "enrollment",
                "target_concepts": ["Student", "Enrollment", "Course", "Semester", "Program", "Professor", "Department", "Assignment", "Grade", "Classroom"],
                "emotion": "anxious",
                "verbosity": "terse",
                "strategy": "confirmatory",
                "competency": "novice",
            },
            {
                "role": "intermediate",
                "sample_suffix": "enrollment",
                "target_concepts": ["Student", "Enrollment", "Course", "Semester", "Program", "Professor", "Department", "Assignment", "Grade", "Classroom"],
                "emotion": "enthusiastic",
                "verbosity": "moderate",
                "strategy": "exploratory",
                "competency": "intermediate",
            },
            {
                "role": "expert",
                "sample_suffix": "enrollment",
                "target_concepts": ["Student", "Enrollment", "Course", "Semester", "Program", "Professor", "Department", "Assignment", "Grade", "Classroom"],
                "emotion": "calm",
                "verbosity": "verbose",
                "strategy": "goal_directed",
                "competency": "expert",
            },
        ],
    },
    "library": {
        "prompt": "I want a library lending metamodel.",
        "users": [
            {
                "role": "novice",
                "sample_suffix": "reservations",
                "target_concepts": ["Member", "Loan", "Book", "Copy", "Fine", "Reservation", "Librarian", "Library", "Category", "Author"],
                "emotion": "anxious",
                "verbosity": "terse",
                "strategy": "confirmatory",
                "competency": "novice",
            },
            {
                "role": "intermediate",
                "sample_suffix": "reservations",
                "target_concepts": ["Member", "Loan", "Book", "Copy", "Fine", "Reservation", "Librarian", "Library", "Category", "Author"],
                "emotion": "enthusiastic",
                "verbosity": "moderate",
                "strategy": "exploratory",
                "competency": "intermediate",
            },
            {
                "role": "expert",
                "sample_suffix": "reservations",
                "target_concepts": ["Member", "Loan", "Book", "Copy", "Fine", "Reservation", "Librarian", "Library", "Category", "Author"],
                "emotion": "calm",
                "verbosity": "verbose",
                "strategy": "goal_directed",
                "competency": "expert",
            },
        ],
    },
    "hospital": {
        "prompt": "I want a hospital appointment management metamodel.",
        "users": [
            {
                "role": "novice",
                "sample_suffix": "appointments",
                "target_concepts": ["Patient", "Appointment", "Doctor", "Department", "MedicalRecord", "Diagnosis", "Prescription", "Treatment", "Room", "Nurse"],
                "emotion": "anxious",
                "verbosity": "terse",
                "strategy": "confirmatory",
                "competency": "novice",
            },
            {
                "role": "intermediate",
                "sample_suffix": "appointments",
                "target_concepts": ["Patient", "Appointment", "Doctor", "Department", "MedicalRecord", "Diagnosis", "Prescription", "Treatment", "Room", "Nurse"],
                "emotion": "enthusiastic",
                "verbosity": "moderate",
                "strategy": "exploratory",
                "competency": "intermediate",
            },
            {
                "role": "expert",
                "sample_suffix": "appointments",
                "target_concepts": ["Patient", "Appointment", "Doctor", "Department", "MedicalRecord", "Diagnosis", "Prescription", "Treatment", "Room", "Nurse"],
                "emotion": "calm",
                "verbosity": "verbose",
                "strategy": "goal_directed",
                "competency": "expert",
            },
        ],
    },
    "ecommerce": {
        "prompt": "I want an e-commerce order management metamodel.",
        "users": [
            {
                "role": "novice",
                "sample_suffix": "orders",
                "target_concepts": ["Order", "Product", "Customer", "OrderItem", "Payment", "Shipment", "Address", "Inventory", "Category", "Cart"],
                "emotion": "anxious",
                "verbosity": "terse",
                "strategy": "confirmatory",
                "competency": "novice",
            },
            {
                "role": "intermediate",
                "sample_suffix": "orders",
                "target_concepts": ["Order", "Product", "Customer", "OrderItem", "Payment", "Shipment", "Address", "Inventory", "Category", "Cart"],
                "emotion": "enthusiastic",
                "verbosity": "moderate",
                "strategy": "exploratory",
                "competency": "intermediate",
            },
            {
                "role": "expert",
                "sample_suffix": "orders",
                "target_concepts": ["Order", "Product", "Customer", "OrderItem", "Payment", "Shipment", "Address", "Inventory", "Category", "Cart"],
                "emotion": "calm",
                "verbosity": "verbose",
                "strategy": "goal_directed",
                "competency": "expert",
            },
        ],
    },
}

