Smart Door Lock – Behaviour Spec

The lock starts in a ready-to-lock mode as soon as the device boots. A valid badge tap moves it to unlocked; if the badge is not recognised, nothing changes. A forced entry — physical breach detected by the sensor — immediately jumps the device into an alarm mode that sounds the siren.

An administrator can clear the alarm by confirming a reset on the control panel, which returns the device to its standard locked mode. Whenever the lock changes mode, the time and cause are appended to the security log.

The locked and unlocked modes form the normal-access zone of the device. A decommission command from the central server puts the lock in a permanent end-of-life mode where it ignores all further inputs and must be physically replaced.
