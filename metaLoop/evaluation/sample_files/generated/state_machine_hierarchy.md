SmartWatch StateMachine has two parallel Regions: WatchFaceRegion and ActivityRegion.
WatchFaceRegion States: TimeDisplay, NotificationDisplay.
ActivityRegion States: Idle, Tracking, Paused.
Event WristRaise triggers a Transition in WatchFaceRegion from Idle to TimeDisplay.
