OrderProcessing StateMachine: InitialState is Draft, FinalState is Delivered.
Intermediate states: Confirmed, Shipped.
Draft transitions to Confirmed on PaymentReceived event.
Shipped transitions to the FinalState Delivered when the courier confirms delivery.
