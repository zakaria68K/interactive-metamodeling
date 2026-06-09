#!/usr/bin/env python3
"""Organize files in this results folder into `organized/reports` and `organized/notes`.

This script is conservative: by default it will create symlinks at the original locations
pointing to the new organized locations so existing code that references the files keeps
working. Use `--copy` to keep copies instead of symlinks.

Usage:
  python3 organize_results.py [--dry-run] [--copy]

Be careful: running without `--dry-run` will move files.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).parent


def load_manifest() -> dict:
    path = ROOT / "index.json"
    if not path.exists():
        raise SystemExit("index.json not found in results folder")
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def organize(dry_run: bool = True, copy_instead_of_symlink: bool = False) -> None:
    manifest = load_manifest()
    files = manifest.get("files", [])

    target_base = ROOT / "organized"
    reports_dir = target_base / "reports"
    notes_dir = target_base / "notes"
    ensure_dir(reports_dir)
    ensure_dir(notes_dir)

    for item in files:
        rel = item.get("path")
        kind = item.get("type")
        src = ROOT / rel
        if not src.exists():
            print(f"SKIP (missing): {src}")
            continue

        dst_dir = reports_dir if kind == "reports" else notes_dir
        dst = dst_dir / src.name

        print(f"Processing: {src} -> {dst} (kind={kind})")
        if dry_run:
            continue

        # Move the file into organized location
        if dst.exists():
            print(f"  Destination exists, skipping move: {dst}")
        else:
            shutil.move(str(src), str(dst))
            print(f"  Moved to {dst}")

        # Create symlink or copy back to original path
        if copy_instead_of_symlink:
            shutil.copy2(str(dst), str(src))
            print(f"  Copied back to original location: {src}")
        else:
            try:
                src.symlink_to(dst)
                print(f"  Symlink created at original path -> {dst}")
            except FileExistsError:
                print(f"  Symlink already exists: {src}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Don't move files, only show actions")
    p.add_argument("--copy", action="store_true", help="Keep a copy at original path instead of symlink")
    args = p.parse_args()

    organize(dry_run=args.dry_run, copy_instead_of_symlink=args.copy)


if __name__ == "__main__":
    main()
