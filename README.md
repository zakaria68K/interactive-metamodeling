# interactive-metamodeling

Interactive pipeline that transforms natural-language requirements into evolving metamodels through iterative questioning and validation.

## Wikidata Flow

The flow:

- After elicitation, the user has confirmed a set of concepts (e.g. [State, Transition, Event])
- Those confirmed concepts are used as seeds, each one is searched in Wikidata to get its QID
- SPARQL queries P279 (subclass-of) and P527 (has-part) neighbours for each QID
- The union of all returned labels is filtered
- This list is presented to the user, who picks exactly n concepts (where n = number of target concepts)
- The selected concepts replace the confirmed set and feed into decompose_concepts

## Goal

The goal was an ablation study: compare interactive (elicitation only) vs interactive_wikidata (elicitation + Wikidata suggestions) on the same 50-profile dataset, measuring whether the Wikidata step improves precision/recall/F1 on concept recovery.

## Results

The results were not usable:

- Searching bare concept names returns geographic or political entities (e.g. `"State"` -> sovereign state, Japan, Lebanon)
- When I triedd to add the name of the metamodel before the concept (nothing was returned). For example:
- `"state machine State"`: no results
- `"state machine Transition"`: no results
- The SPARQL endpoint times out quickly

Wikidata covers general knowledge. Software engineering concepts are not represented as entities in it. The P527 (has-part) top-down approach requires SPARQL, which is unreliable: The endpoint (query.wikidata.org) timed out on this network before returning any data.

## Why Not Just Rely on the LLM Knowing Wikidata

CommonCrawl has indexed Wikidata, so LLMs already have its content in their training data. Querying Wikidata at runtime to feed labels back to the LLM is redundant, the model already knows what Wikidata knows. But even if it weren't redundant, it would still not help: Wikidata does not contain software engineering concepts like `State`, `Transition`, or `Course` (as a university entity) with meaningful ontological relations. So the LLM knowing Wikidata does not give it the structured domain coverage we need.
