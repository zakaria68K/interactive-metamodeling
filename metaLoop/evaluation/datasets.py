"""
Evaluation dataset: domain configs with prompts and per-user target concept lists.
Imported by main.py and main_wikidata.py.
"""

DOMAIN_CONFIGS: dict[str, dict] = {
    "state_machine": {
        "prompt": "I want a state machine metamodel for interactive applications.",
        "users": [
            ("events", ["State", "Event", "Transition", "Trigger", "StateMachine", "Guard", "Action", "Region", "InitialState", "FinalState"]),
            ("transitions", ["State", "Transition", "Guard", "Action", "Event", "StateMachine", "Trigger", "Region", "InitialState", "FinalState"]),
            ("start_end", ["InitialState", "FinalState", "State", "Transition", "StateMachine", "Event", "Trigger", "Guard", "Action", "Region"]),
            ("workflow_container", ["StateMachine", "State", "Transition", "Region", "Event", "Trigger", "Guard", "Action", "InitialState", "FinalState"]),
            ("triggering", ["Trigger", "Event", "Transition", "State", "Guard", "Action", "Region", "InitialState", "FinalState", "StateMachine"]),
        ],
    },
    "university": {
        "prompt": "I want a university course management metamodel.",
        "users": [
            ("enrollment", ["Student", "Enrollment", "Course", "Semester", "Program", "Professor", "Department", "Assignment", "Grade", "Classroom"]),
            ("teaching", ["Professor", "Course", "Department", "Classroom", "Semester", "Student", "Enrollment", "Assignment", "Grade", "Program"]),
            ("programs", ["Program", "Student", "Course", "Department", "Professor", "Semester", "Assignment", "Grade", "Classroom", "Enrollment"]),
            ("departments", ["Department", "Professor", "Course", "Semester", "Classroom", "Student", "Enrollment", "Assignment", "Grade", "Program"]),
            ("grading", ["Grade", "Assignment", "Student", "Course", "Professor", "Department", "Semester", "Classroom", "Program", "Enrollment"]),
        ],
    },
    "library": {
        "prompt": "I want a library lending metamodel.",
        "users": [
            ("borrowing", ["Member", "Loan", "Book", "Copy", "Fine", "Reservation", "Librarian", "Library", "Category", "Author"]),
            ("catalog", ["Book", "Category", "Author", "Copy", "Library", "Member", "Loan", "Fine", "Reservation", "Librarian"]),
            ("authors", ["Book", "Author", "Category", "Library", "Copy", "Member", "Loan", "Fine", "Reservation", "Librarian"]),
            ("returns", ["Loan", "Fine", "Book", "Member", "Librarian", "Library", "Category", "Author", "Reservation", "Copy"]),
            ("reservations", ["Reservation", "Member", "Book", "Copy", "Librarian", "Library", "Category", "Author", "Loan", "Fine"]),
        ],
    },
    "hospital": {
        "prompt": "I want a hospital appointment management metamodel.",
        "users": [
            ("appointments", ["Patient", "Appointment", "Doctor", "Department", "MedicalRecord", "Diagnosis", "Prescription", "Treatment", "Room", "Nurse"]),
            ("doctors", ["Doctor", "Appointment", "Department", "Patient", "Diagnosis", "Prescription", "Treatment", "Room", "Nurse", "MedicalRecord"]),
            ("departments", ["Department", "Doctor", "Appointment", "Room", "Nurse", "Patient", "Diagnosis", "Prescription", "Treatment", "MedicalRecord"]),
            ("records", ["Patient", "MedicalRecord", "Diagnosis", "Prescription", "Treatment", "Doctor", "Appointment", "Department", "Room", "Nurse"]),
            ("prescriptions", ["Prescription", "Patient", "Doctor", "Appointment", "MedicalRecord", "Diagnosis", "Treatment", "Room", "Nurse", "Department"]),
        ],
    },
    "ecommerce": {
        "prompt": "I want an e-commerce order management metamodel.",
        "users": [
            ("orders", ["Order", "Product", "Customer", "OrderItem", "Payment", "Shipment", "Address", "Inventory", "Category", "Cart"]),
            ("shipping", ["Order", "Shipment", "Address", "Customer", "Inventory", "Product", "OrderItem", "Payment", "Category", "Cart"]),
            ("payments", ["Order", "Payment", "Customer", "Product", "OrderItem", "Shipment", "Address", "Inventory", "Category", "Cart"]),
            ("customers", ["Customer", "Address", "Cart", "Order", "Payment", "OrderItem", "Shipment", "Inventory", "Category", "Product"]),
            ("catalog", ["Product", "Category", "Inventory", "Cart", "OrderItem", "Order", "Payment", "Shipment", "Address", "Customer"]),
        ],
    },
}
