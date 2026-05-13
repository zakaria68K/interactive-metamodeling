The TrafficLight StateMachine starts in the InitialState called PowerOn. It has States: Red, Green, Yellow, and a FinalState called Shutdown.
The TimerExpired Event triggers the Red→Green Transition via a Trigger named RedTimer. A Guard checks that emergencyMode is false before allowing it.
An Action named LogChange executes when any Transition fires, writing to the audit log.
Red, Green, and Yellow belong to a Region named NormalOperation within the StateMachine.
A ManualOverride Event can trigger a direct Transition from any State to Shutdown, bypassing the Guard.
