VendingMachine: Idle State runs Action displayMenu on entry.
Event SelectItem triggers Transition from Idle to ItemSelected.
Guard: item stock > 0 must be true before the Dispensing Transition.
Action deductCredit executes during the payment Transition.
