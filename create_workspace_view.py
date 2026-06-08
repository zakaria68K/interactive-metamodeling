#!/usr/bin/env python3
"""Create an `organized_workspace` symlinked view of the project for easier browsing.

This script is non-destructive: by default it only prints the actions (--dry-run).
Use `--apply` to actually create directories and symlinks.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

ROOT = Path(__file__).parent
VIEW = ROOT / "organized_workspace"


DEFAULT_ITEMS: List[Path] = [
    ROOT / "app.py",
    ROOT / "main.py",
    ROOT / "README.md",
    ROOT / "requirements.txt",
    ROOT / "Dockerfile",
    ROOT / "app_modules",
    ROOT / "metaLoop",
    ROOT / "session_logs",
    ROOT / "metaLoop" / "evaluation" / "results",
]


def plan_create(items: List[Path]) -> List[tuple[Path, Path]]:
    ops: List[tuple[Path, Path]] = []
    for p in items:
        if not p.exists():
            continue
        target = VIEW / p.name
        ops.append((p, target))
    return ops


def show_plan(ops: List[tuple[Path, Path]]) -> None:
    if not ops:
        print("No items found to link.")
        return
    print("Planned symlinks:")
    for src, dst in ops:
        print(f"  {dst} -> {src}")


def apply_plan(ops: List[tuple[Path, Path]]) -> None:
    VIEW.mkdir(exist_ok=True)
    for src, dst in ops:
        if dst.exists() or dst.is_symlink():
            print(f"Skipping existing: {dst}")
            continue
        try:
            dst.symlink_to(src)
            print(f"Created: {dst} -> {src}")
        except Exception as e:
            print(f"FAILED to create {dst}: {e}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Show what would be created")
    p.add_argument("--apply", action="store_true", help="Create the symlinked view")
    args = p.parse_args()

    ops = plan_create(DEFAULT_ITEMS)
    show_plan(ops)
    if args.apply:
        apply_plan(ops)


if __name__ == "__main__":
    main()
