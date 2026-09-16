from __future__ import annotations

import csv
import datetime
import json
import os
from pathlib import Path
from threading import Lock

from .quiz import DOMAINS

# ── Durable off-Space data collection ───────────────────────────────────────
# Hugging Face Spaces containers are ephemeral: anything written to local disk
# (the JSON files in user_profiles/ and session_logs/) is lost on restart,
# sleep, or redeploy. To not lose pre/post questionnaire scores during the
# study, every submission is also appended here and pushed to a private HF
# *Dataset* repo via CommitScheduler, which survives independently of the
# Space's own filesystem.
#
# Activated only when both HF_DATASET_REPO and HF_TOKEN are set (e.g. as
# Space secrets/variables). Without them, rows still accumulate in
# study_data/ on local disk exactly as before — nothing breaks locally or
# in this dev environment.

DATA_DIR = Path("study_data")
DATA_DIR.mkdir(exist_ok=True)
QUIZ_CSV_PATH = DATA_DIR / "quiz_log.csv"
SESSION_JSONL_PATH = DATA_DIR / "session_log.jsonl"

# Both domains' question banks share the same q1..q6 ids (their text/answers
# differ), so one fixed column layout covers either — the "domain" column
# says which bank a given row's q1..q6 refer to.
_QUESTION_IDS = [q["id"] for q in DOMAINS["bp"]["pre"]]
_QUIZ_FIELDNAMES = ["timestamp", "username", "domain", "phase", "score"] + _QUESTION_IDS

_local_lock = Lock()
_scheduler = None

_repo_id = os.getenv("HF_DATASET_REPO", "").strip()
_token = os.getenv("HF_TOKEN", "").strip()

if _repo_id and _token:
    from huggingface_hub import CommitScheduler

    _scheduler = CommitScheduler(
        repo_id=_repo_id,
        repo_type="dataset",
        folder_path=DATA_DIR,
        path_in_repo="study_data",
        token=_token,
        every=2,  # minutes; also force-pushed immediately after every write below
    )


def _write_locked(fn) -> None:
    if _scheduler is not None:
        with _scheduler.lock:
            fn()
        _scheduler.trigger()  # push now instead of waiting for the next timer tick
    else:
        with _local_lock:
            fn()


def log_quiz(username: str, domain: str, phase: str, responses: dict, score: int) -> None:
    """phase is 'pre' or 'post'; domain is one of DOMAINS' keys. Appends one row per submission; never overwrites."""
    row = {
        "timestamp": datetime.datetime.now().isoformat(),
        "username": username,
        "domain": domain,
        "phase": phase,
        "score": score,
    }
    for question_id in _QUESTION_IDS:
        value = responses.get(question_id, "")
        # Questions allow multiple selections (a CheckboxGroup), so the raw
        # value is a list — flatten it to a readable "; "-joined cell instead
        # of writing a Python list repr into the CSV.
        row[question_id] = "; ".join(value) if isinstance(value, (list, tuple)) else value

    def _write() -> None:
        is_new = not QUIZ_CSV_PATH.exists()
        with QUIZ_CSV_PATH.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_QUIZ_FIELDNAMES)
            if is_new:
                writer.writeheader()
            writer.writerow(row)

    _write_locked(_write)


def log_session(event: dict) -> None:
    """Freeform per-session record (interactive or one-shot completion)."""
    event = {"timestamp": datetime.datetime.now().isoformat(), **event}

    def _write() -> None:
        with SESSION_JSONL_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    _write_locked(_write)
