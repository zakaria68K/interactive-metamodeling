TrafficLightController is a StateMachine with three states: Red, Yellow, Green.
The TimerExpired event triggers the Red-to-Green transition.
The TimerExpired event also triggers Green-to-Yellow and Yellow-to-Red transitions.
Each state listens to a different Trigger interval before firing the next event.
