from __future__ import annotations

import datetime
import json
import re
from pathlib import Path


def _load_user_profile(username: str) -> dict:
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", username.strip())
    file_path = Path("user_profiles") / f"{safe_name}.json"
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {"username": username, "created_at": datetime.datetime.now().isoformat()}


def _save_user_profile(
    name: str,
    pre_data: dict | None = None,
    pre_score: int | None = None,
    post_data: dict | None = None,
    post_score: int | None = None,
    extra: dict | None = None,
) -> dict:
    # Scoring isn't computed here: which question bank (and therefore which
    # answers are correct) applies depends on the participant's study domain,
    # which this module has no reason to know about — the caller (app.py,
    # which does know the domain) computes the score and passes it in.
    username = (name or "").strip()
    if not username:
        raise ValueError("Username is required")

    profile = _load_user_profile(username)
    profile["username"] = username
    profile["updated_at"] = datetime.datetime.now().isoformat()
    if pre_data is not None:
        profile["pre_responses"] = pre_data
        profile["pre_score"] = pre_score
        profile["pre_submitted_at"] = datetime.datetime.now().isoformat()
    if post_data is not None:
        profile["post_responses"] = post_data
        profile["post_score"] = post_score
        profile["post_submitted_at"] = datetime.datetime.now().isoformat()
    if extra:
        profile.update(extra)

    out_dir = Path("user_profiles")
    out_dir.mkdir(exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", username)
    file_path = out_dir / f"{safe_name}.json"
    file_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    return profile
