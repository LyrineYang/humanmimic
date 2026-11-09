#!/usr/bin/env python3
"""Verify the actual result/demo files included in a normal Git clone."""
import csv
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = root / "docs/migration-20261109/published-files.csv"
errors, count = [], 0
with manifest.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        path = root / row["path"]
        try:
            h = hashlib.sha256()
            with path.open("rb") as content:
                for block in iter(lambda: content.read(4 * 1024**2), b""):
                    h.update(block)
            if path.stat().st_size != int(row["bytes"]) or h.hexdigest() != row["sha256"]:
                raise ValueError("size or SHA-256 mismatch")
            count += 1
        except (OSError, ValueError) as exc:
            errors.append({"path": row["path"], "error": str(exc)})
print(json.dumps({"status": "passed" if not errors else "failed", "verified_files": count, "errors": errors}, indent=2))
raise SystemExit(bool(errors))
