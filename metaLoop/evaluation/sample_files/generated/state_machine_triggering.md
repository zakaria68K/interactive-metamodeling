LoginFlow: Idle state, triggered by SubmitButton click Event.
Trigger fires only when the password field is non-empty (Guard).
Event LoginSuccess moves state from Authenticating to Dashboard.
Event LoginFailure moves state from Authenticating back to Idle.
