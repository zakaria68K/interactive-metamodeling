"""
Evaluation dataset: domain configs mapping each domain to a golden .ecore metamodel.

Ground-truth concepts are derived at runtime by parsing the EClass names from the
referenced .ecore file — no hand-written concept lists.

Each domain entry has:
  prompt         : natural-language request fed to the agent / simulator
  metamodel_path : workspace-relative path to the golden .ecore file
  sample_suffix  : suffix used to locate the narrative sample file under
                   metaLoop/evaluation/sample_files/generated/<domain>_<suffix>.md
"""

DOMAIN_CONFIGS: dict[str, dict] = {
    "bpmn": {
        "prompt": "I want a metamodel for BPMN-like business process workflows.",
        "metamodel_path": "metaLoop/evaluation/metamodels/BPMN.ecore",
        "sample_suffix": "process",
    },
    "relational": {
        "prompt": "I want a metamodel for relational databases with tables, columns, and typed keys.",
        "metamodel_path": "metaLoop/evaluation/metamodels/Relational.ecore",
        "sample_suffix": "schema",
    },
    "km3": {
        "prompt": "I want a metamodel for describing metamodels (classifiers, packages, typed features, operations).",
        "metamodel_path": "metaLoop/evaluation/metamodels/KM3.ecore",
        "sample_suffix": "metamodel",
    },
    "measure": {
        "prompt": "I want a metamodel for software quality measurement with metrics and measure sets.",
        "metamodel_path": "metaLoop/evaluation/metamodels/Measure.ecore",
        "sample_suffix": "quality",
    },
    "mysql": {
        "prompt": "I want a metamodel for MySQL database schemas with tables, columns, and enum types.",
        "metamodel_path": "metaLoop/evaluation/metamodels/MySql.ecore",
        "sample_suffix": "database",
    },
    "rss": {
        "prompt": "I want a metamodel for RSS feed structures with channels, items, and media.",
        "metamodel_path": "metaLoop/evaluation/metamodels/RSS.ecore",
        "sample_suffix": "feed",
    },
}

