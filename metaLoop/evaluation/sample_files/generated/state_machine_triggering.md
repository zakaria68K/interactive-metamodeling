The SmartHeater StateMachine has States: Off, Heating, Cooling, Standby grouped in a Region named TemperatureControl.
InitialState is Standby; FinalState is PoweredDown.
A TemperatureHigh Event activates a Trigger named OverheatTrigger, firing the Heating→Cooling Transition.
Guard on that Transition: currentTemp > 30. Action: activateFan() runs when the Transition fires.
A ScheduledEvent Trigger named NightTimer fires the Heating→Standby Transition each night at 22:00.
The whole system is coordinated by a StateMachine named HeaterController that responds to all Triggers.
