The VendingMachine StateMachine begins at InitialState Idle and ends at FinalState OutOfService.
States: Idle, SelectionMade, PaymentPending, Dispensing. These form a Region called SalesFlow.
CoinInserted Event triggers the Idle→PaymentPending Transition, controlled by a Trigger CoinTrigger.
Guard: coinAmount >= itemPrice must be true for the PaymentPending→Dispensing Transition.
An Action named DispenseItem runs on the Dispensing Transition. Another Action named ReturnChange finalizes it.
PowerCut Event causes a direct Transition to FinalState OutOfService from any State in the StateMachine.
