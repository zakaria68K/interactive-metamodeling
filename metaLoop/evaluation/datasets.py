"""
Evaluation dataset: domain configs with prompts and per-user target concept lists.
Imported by main.py and main_wikidata.py.
"""

DOMAIN_CONFIGS: dict[str, dict] = {
    "state_machine": {
        "prompt": "I want a state machine metamodel for interactive applications.",
        "users": [
            ("events", ["State", "Event", "Transition", "Trigger", "StateMachine"]),
            ("transitions", ["State", "Transition", "Guard", "Action", "Event"]),
            ("start_end", ["InitialState", "FinalState", "State", "Transition", "StateMachine"]),
            ("workflow_container", ["StateMachine", "State", "Transition", "Region", "Event"]),
            ("triggering", ["Trigger", "Event", "Transition", "State", "Guard"]),
            ("behavior", ["Action", "Transition", "Event", "State", "Guard"]),
            ("conditions", ["Guard", "Transition", "State", "Event", "Action"]),
            ("hierarchy", ["Region", "State", "StateMachine", "Transition", "Event"]),
            ("navigation", ["State", "Trigger", "Transition", "Action", "FinalState"]),
            ("teaching", ["State", "InitialState", "FinalState", "Transition", "Event"]),
        ],
    },
    "university": {
        "prompt": "I want a university course management metamodel.",
        "users": [
            ("enrollment", ["Student", "Enrollment", "Course", "Semester", "Program"]),
            ("teaching", ["Professor", "Course", "Department", "Classroom", "Semester"]),
            ("programs", ["Program", "Student", "Course", "Department", "Professor"]),
            ("departments", ["Department", "Professor", "Course", "Semester", "Classroom"]),
            ("grading", ["Grade", "Assignment", "Student", "Course", "Professor"]),
            ("semester_planning", ["Semester", "Course", "Classroom", "Professor", "Department"]),
            ("classrooms", ["Classroom", "Course", "Semester", "Professor", "Student"]),
            ("course_progress", ["Student", "Assignment", "Grade", "Course", "Program"]),
            ("offerings", ["Department", "Course", "Semester", "Professor", "Enrollment"]),
            ("advising", ["Student", "Program", "Professor", "Course", "Grade"]),
        ],
    },
    "library": {
        "prompt": "I want a library lending metamodel.",
        "users": [
            ("borrowing", ["Member", "Loan", "Book", "Copy", "Fine"]),
            ("catalog", ["Book", "Category", "Author", "Copy", "Library"]),
            ("authors", ["Book", "Author", "Category", "Library", "Copy"]),
            ("returns", ["Loan", "Fine", "Book", "Member", "Librarian"]),
            ("reservations", ["Reservation", "Member", "Book", "Copy", "Librarian"]),
            ("staff", ["Librarian", "Library", "Member", "Loan", "Reservation"]),
            ("copies", ["Copy", "Book", "Category", "Library", "Loan"]),
            ("availability", ["Book", "Copy", "Loan", "Member", "Reservation"]),
            ("membership", ["Member", "Library", "Loan", "Fine", "Reservation"]),
            ("circulation", ["Book", "Member", "Loan", "Copy", "Librarian"]),
        ],
    },
    "hospital": {
        "prompt": "I want a hospital appointment management metamodel.",
        "users": [
            ("appointments", ["Patient", "Appointment", "Doctor", "Department", "MedicalRecord"]),
            ("doctors", ["Doctor", "Appointment", "Department", "Patient", "Diagnosis"]),
            ("departments", ["Department", "Doctor", "Appointment", "Room", "Nurse"]),
            ("records", ["Patient", "MedicalRecord", "Diagnosis", "Prescription", "Treatment"]),
            ("prescriptions", ["Prescription", "Patient", "Doctor", "Appointment", "MedicalRecord"]),
            ("treatments", ["Treatment", "Diagnosis", "Patient", "Doctor", "Room"]),
            ("rooms", ["Room", "Patient", "Nurse", "Appointment", "Treatment"]),
            ("nursing", ["Nurse", "Patient", "Room", "Treatment", "MedicalRecord"]),
            ("consultations", ["Doctor", "Diagnosis", "Appointment", "Patient", "Prescription"]),
            ("care_flow", ["Patient", "Appointment", "Prescription", "Treatment", "MedicalRecord"]),
        ],
    },
    "ecommerce": {
        "prompt": "I want an e-commerce order management metamodel.",
        "users": [
            ("orders", ["Order", "Product", "Customer", "OrderItem", "Payment"]),
            ("shipping", ["Order", "Shipment", "Address", "Customer", "Inventory"]),
            ("payments", ["Order", "Payment", "Customer", "Product", "OrderItem"]),
            ("customers", ["Customer", "Address", "Cart", "Order", "Payment"]),
            ("catalog", ["Product", "Category", "Inventory", "Cart", "OrderItem"]),
            ("cart", ["Cart", "Product", "Customer", "OrderItem", "Order"]),
            ("line_items", ["Order", "OrderItem", "Product", "Payment", "Shipment"]),
            ("stock", ["Inventory", "Product", "Category", "OrderItem", "Shipment"]),
            ("checkout", ["Customer", "Cart", "Payment", "Order", "Address"]),
            ("fulfillment", ["Order", "Shipment", "Inventory", "Product", "OrderItem"]),
        ],
    },
}
