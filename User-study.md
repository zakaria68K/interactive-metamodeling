# MetaLoop User Study

## Goal

Measure whether interacting with MetaLoop helps participants learn metamodeling concepts better than a one-shot generation approach.

---

## Design

**Between-subjects.** Participants are randomly assigned to one of two groups:

- **Test group** — builds a metamodel using MetaLoop (interactive, iterative, chunk-by-chunk)
- **Control group** — builds a metamodel using a one-shot LLM prompt (no iteration, no feedback loop)

Both groups work on the same domain: **[domain TBD, e.g., state machines]**, described in a short natural language prompt provided by the researchers.

---

## Participants

- Background: students with some exposure to MDE or software modeling
- No prior use of MetaLoop
- Recruited from ENSIAS
- Target: ~30 participants per group (60 total)

---

## Procedure

We can introduce a pre-knowledge assessment to establish a baseline for each participant.

### Phase 1 — Pre-test (before any interaction)
Participants answer a short quiz on metamodeling concepts (classes, references, multiplicities, containment, etc.).

- 6 questions, multiple choice, on 3 different aspects.
- ~5 minutes

### Phase 2 — Task
Participants receive a domain description and are asked to produce a metamodel.

- **Test group:** uses MetaLoop. They go through the full elicitation and chunk review workflow.
- **Control group:** uses a provided one-shot prompt template against the same LLM (gpt-4.1-mini). They receive the generated metamodel as-is.
- Time limit: 30 minutes

### Phase 3 — Post-test (after the task)
Same structure as the pre-test, different questions, same concepts.

- 6 questions, multiple choice, , on 3 different aspects.
- ~5 minutes

### Phase 4 — Usability questionnaire (test group only)
Short Likert-scale questionnaire on the interaction with MetaLoop.

- ~5 questions, 5-point scale
- Topics: clarity of explanations, usefulness of the feedback loop, confidence in the produced metamodel

---

## What We Measure

| Metric | How |
|---|---|
| Knowledge gain | Post-test score minus pre-test score |
| Group difference | Statistical comparison (BWS test or Mann-Whitney, depending on sample size) |
| Usability (test group) | Likert questionnaire |

- Knowledge gain is the primary metric. A significantly higher gain in the test group would indicate that the interactive process of MetaLoop helps participants internalize metamodeling concepts.

- The statistical test answers the following question: if MetaLoop made no difference at all, what is the probability of observing this gap between the two groups purely by chance? If that probability is below 5% (p < 0.05), the difference is considered statistically significant.

---

## Pilot Study (recommended, optional)

Run the protocol on 3–5 colleagues or fellow PhD students before the main study. Goal: validate that the pre/post-test questions are well-calibrated and unambiguous. Adjust questions if needed before recruiting the full sample.

---

## Materials Needed

- [ ] Domain description text (fixed for all participants)
- [ ] Pre-test questionnaire (6 questions)
- [ ] Post-test questionnaire (6 questions, different from pre-test)
- [ ] Usability questionnaire (test group only)
- [ ] One-shot prompt template (control group)
- [ ] Access to MetaLoop (test group)
- [ ] Consent form

---

## Notes for Supervisors

The design mirrors the SAM study (CHI 2025, Bodonhelyi et al.), adapted for a modeling tool rather than a video learning platform. The key adaptation is the definition of "knowledge gain": here it measures understanding of metamodeling concepts (not a subject taught via video), acquired as a side effect of producing a metamodel with or without interactive support.

The domain chosen for the task should be simple enough that participants with basic MDE background can engage with it, but structured enough to surface metamodeling decisions (references, multiplicities, inheritance).

---

## Notes for Participants

You will be asked to:
1. Answer a short quiz on modeling concepts.
2. Use a tool (or a prompt) to build a metamodel from a domain description we provide.
3. Answer the quiz again.
4. (Test group only) Fill in a short feedback form.

There are no right or wrong ways to use the tool. We are evaluating the tool, not you.

All data is collected anonymously.