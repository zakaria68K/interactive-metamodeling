CheckoutWizard states: Step1Address, Step2Payment, Step3Confirm, FinalState Completed.
Trigger NextButton moves from Step1Address to Step2Payment.
Action validateAddress runs before the Step1-to-Step2 Transition can proceed.
Trigger ConfirmOrder moves Step3Confirm to the FinalState Completed.
