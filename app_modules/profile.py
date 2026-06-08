from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from .quiz import _compute_form_score


def _load_user_profile(username: str) -> dict:
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", username.strip())
    file_path = Path("user_profiles") / f"{safe_name}.json"
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {"username": username, "created_at": datetime.datetime.now().isoformat()}


def _save_user_profile(name: str, pre_data: dict | None = None, post_data: dict | None = None) -> dict:
    username = (name or "").strip()
    if not username:
        raise ValueError("Username is required")

    profile = _load_user_profile(username)
    profile["username"] = username
    profile["updated_at"] = datetime.datetime.now().isoformat()
    if pre_data is not None:
        profile["pre_responses"] = pre_data
        profile["pre_score"] = _compute_form_score(pre_data)
        profile["pre_submitted_at"] = datetime.datetime.now().isoformat()
    if post_data is not None:
        profile["post_responses"] = post_data
        profile["post_score"] = _compute_form_score(post_data)
        profile["post_submitted_at"] = datetime.datetime.now().isoformat()

    out_dir = Path("user_profiles")
    out_dir.mkdir(exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", username)
    file_path = out_dir / f"{safe_name}.json"
    file_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    return profile
