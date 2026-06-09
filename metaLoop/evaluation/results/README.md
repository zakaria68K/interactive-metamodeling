This folder contains evaluation outputs, reports and raw responses produced during experiments.

Goal
----
Make the folder easier to navigate while keeping the original file paths available for existing scripts.

What I added
-------------
- `index.json` — a simple manifest that categorizes files in this folder.
- `organize_results.py` — a safe script to move files into `organized/` subfolders and create symlinks at the original locations so code that expects the original paths keeps working.

How it works (recommended)
--------------------------
1. Inspect `index.json` to confirm the desired categorization.
2. Run the organizer to move files into `organized/reports` and `organized/notes` and create symlinks:

```bash
python3 metaLoop/evaluation/results/organize_results.py --dry-run
python3 metaLoop/evaluation/results/organize_results.py
```

Notes and safety
----------------
- By default the script performs a dry-run when `--dry-run` is passed and will not modify files.
- The script creates POSIX symlinks at the original file paths pointing to the new locations. This keeps existing code working.
- If your environment or deployment system does not support symlinks, run the script with `--copy` to leave copies at both locations.

If you want me to actually run the organizer now, tell me and I'll execute it (I will not move files without your consent).
