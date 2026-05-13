The OrderProcessing StateMachine contains two Regions: FulfillmentRegion and PaymentRegion, running concurrently.
FulfillmentRegion has States: AwaitingStock, Packing, Shipped. PaymentRegion has States: PaymentPending, PaymentConfirmed.
InitialState is OrderReceived; FinalState is OrderCompleted.
StockAvailable Event triggers AwaitingStock→Packing Transition via a Trigger named StockTrigger. Guard: warehouseCapacity > 0.
PaymentSuccess Event triggers PaymentPending→PaymentConfirmed Transition; Action: sendReceiptEmail() fires.
The StateMachine coordinates both Regions so OrderCompleted is only reached when both reach their end States.
