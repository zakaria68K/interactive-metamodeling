MediaPlayer is a StateMachine containing two Regions: PlaybackRegion and ControlRegion.
PlaybackRegion has states: Playing, Paused, Stopped.
ControlRegion has states: VolumeActive, Muted.
The Play Event triggers the Stopped-to-Playing Transition inside PlaybackRegion.
