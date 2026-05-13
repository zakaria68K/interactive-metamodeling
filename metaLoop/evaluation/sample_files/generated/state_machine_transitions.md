The DoorLock StateMachine has an InitialState Booted and a FinalState Decommissioned.
States: Locked, Unlocked, Alarm. Region "AccessControl" contains Locked and Unlocked.
Transition from Locked to Unlocked is triggered by a BadgeScan Event via a Trigger named BadgeTrigger. Guard: badgeValid == true.
Transition from Locked to Alarm is triggered by ForcedEntry Event; Action: soundAlarm() executes on this Transition.
Transition from Alarm to Locked fires on ResetEvent Trigger after Guard: adminConfirmed == true.
StateMachine logs all Transitions through an Action attached to each one.
