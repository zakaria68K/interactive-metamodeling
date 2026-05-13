Traffic Light Controller – Design Notes

When the system powers up, the light begins at red. A 30-second timer then fires and the light switches to green; after 45 seconds it moves to yellow, then back to red. Each switch writes a timestamped entry to the audit log.

The red/green/yellow cycle runs as a self-contained group. A separate path also exists: if the system receives an emergency-vehicle signal, the light immediately goes dark regardless of where in the cycle it is. Before allowing the green-from-red switch, the system checks that no emergency override is currently active — if one is, the switch is suppressed.

Once the light enters "shutdown" mode it stays there permanently. No further cycling occurs until a technician physically restarts the hardware.
