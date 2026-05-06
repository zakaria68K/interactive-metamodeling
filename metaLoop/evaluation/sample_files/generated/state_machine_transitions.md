ATM machine has states: Idle, CardInserted, PinEntry, Dispensing.
Transition from PinEntry to Dispensing has a Guard: pin is correct.
Action: dispense cash executes when the Dispensing transition fires.
Event: CardRemoved always transitions back to Idle from any state.
