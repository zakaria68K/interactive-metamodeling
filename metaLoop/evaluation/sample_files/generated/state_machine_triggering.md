SmartHeater Controller – Behaviour Notes

When powered on, the heater enters a standby mode. It begins heating the room until the sensor reads above 30 °C, at which point the fan activates automatically and the system switches to a cooling mode. The fan kick-off is exactly what happens when that temperature threshold is crossed.

Every night at 22:00 a scheduled signal fires and returns the heater to standby, regardless of what mode it is currently in. The heating, cooling, and standby modes all belong to the main temperature-management group that this controller oversees.

When the user taps "power off" in the app, the system enters a permanently off mode. After that, no sensor readings or scheduled signals are acted on until the device is manually restarted.
