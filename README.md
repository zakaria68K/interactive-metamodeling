# MetaLoop

## Abstract

MetaLoop is a pipeline for metamodel construction from natural-language requirements. It operates through a conversation: the system asks the user targeted questions to identify domain concepts, then generates a metamodel incrementally, validating each part before moving to the next. The output is a JjScript metamodel ready for use in the Jjodel tool. The system is evaluated against three baseline approaches using simulated users across five domains, measuring how accurately each approach recovers the concepts the user intended.

---

## What the System Does

A metamodel defines the vocabulary and structure of a domain. Building one typically requires translating informal knowledge into a formal structure, which is a process that benefits from dialogue. MetaLoop automates this by combining two phases: elicitation and generation.

In the elicitation phase, the system asks the user whether they are familiar with the domain, then proposes an initial set of concepts and refines them through a short back-and-forth conversation. Each concept is confirmed, rejected, or adjusted by the user before anything is generated.

In the generation phase, the system takes the confirmed concepts one by one and generates a JjScript metamodel chunk for each. After generating a chunk, it runs an automated validation and optionally presents the result to the user for approval. Once all concepts are processed, the chunks are merged into the final metamodel.

The user can also attach a file such as a usage example, a test case, or a domain document. The system analyzes the file to detect concepts that were not raised during elicitation and offers them as additional candidates.

---

## Architecture

The pipeline is implemented as a LangGraph agent using Humans validation as tool. The state carries the conversation history, the current list of confirmed concepts, the generated chunks, and validation results at each step.

The `LLMClient` wraps two model roles: a main model for generation and a separate validator model, so the two do not share context during validation.

---

## JjScript

JjScript is the target language. It is a line-oriented script that creates classes, attributes, references, containments, and enumerations in Jjodel. The system generates only JjScript; it never produces JSON, XML, or plain-text descriptions of structure.

```jjscript
create class Order
create attribute status in Order type String
create class Customer
create reference placedBy in Order type Customer
create containment items in Order type OrderItem [0..*]
```

---

## Evaluation

The evaluation measures how well each approach recovers a user's intended concept set. Each test case consists of a domain prompt, a sample file, and a list of target concepts that a simulated user holds in mind. The simulated user is an LLM configured with a fixed persona, a bounded concept vocabulary, and instructions to reveal knowledge naturally across turns rather than all at once.

Five domains are covered: state machine, university course management, library lending, hospital appointments, and e-commerce order management. Each domain is repeated five times, for a total of 25 test cases. The metrics are precision, recall, and F1 on the recovered concept set.

Three approaches are compared:

**interactive** — the full MetaLoop pipeline. The agent elicits concepts through dialogue, then generates and validates the metamodel chunk by chunk. The sample file is passed as initial context.

**one_shot** — the prompt and file are sent to the LLM in a single call. The resulting metamodel text is then parsed to extract concepts. No iteration, no dialogue.

**generate_then_validate** — the metamodel is generated in one shot first, then the extracted concepts are presented to the simulated user for validation. If the user does not approve, the metamodel is refined based on their feedback. This repeats for up to three iterations.

The comparison addresses two questions: whether elicitation before generation outperforms generation alone, and whether iterative refinement after generation can close any gap.

---

## Running the Evaluation

```bash
# All three methods
python3 -m metaLoop.evaluation.main

# One method only
EVAL_METHODS=generate_then_validate python3 -m metaLoop.evaluation.main

# Limit to the first N profiles (for quick tests)
EVAL_LIMIT=5 EVAL_METHODS=one_shot python3 -m metaLoop.evaluation.main

# Multiple runs for averaging
EVAL_RUNS=3 python3 -m metaLoop.evaluation.main
```

Results are written to `metaLoop/evaluation/results/concept_eval_report.json`.

---

## Project Structure

```
metaLoop/
  metamodeling_agent.py       main agent, LangGraph graph construction
  elicitation.py              concept elicitation and user Q&A
  generation.py               JjScript chunk generation and validation
  llm_client.py               LLM wrappers for generation and validation roles
  state.py                    shared conversation state definition
  system_prompt.py            Jjodie system prompt and JjScript reference
  baselineApproaches/
    direct_generation.py          one-shot generation baseline
    without_elicitation.py        full pipeline without elicitation phase
    generate_then_validate.py     generate-first, validate-iteratively baseline
  evaluation/
    main.py                   evaluation runner and comparison logic
    datasets.py               domain configs and target concept lists
    user_simulator.py         simulated user LLM with persona constraints
    llm_extractor.py          concept extraction from generated metamodel text
    results/                  evaluation output reports
    sample_files/generated/   per-domain sample files used as attached context
```

---

## Requirements

Dependencies are listed in `requirements.txt`. The system uses OpenAI models for generation and validation, configured via the `OPENAI_MODEL` and `EVAL_SYSTEM_MODEL` environment variables. User simulation uses an Ollama-hosted model, configured via `EVAL_OLLAMA_MODEL` and `EVAL_OLLAMA_BASE_URL`.
