#!/usr/bin/env python3
"""Validate config.json against the live repos it points at.

HuB's whole job is fetching status_log.jsonl from the URLs in config.json. A
typo in an owner, repo, or branch field silently degrades the dashboard to an
amber "no data" tab, and nothing currently fails. This script is that check.

Run: python3 tools/validate_config.py
Exit 0 = every tracked repo resolves; 1 = at least one does not.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config.json"
REQUIRED = ("name", "owner", "repo", "branch")
RAW = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/status_log.jsonl"


def load_config(path):
    """Parse config.json and assert its shape before anything touches the network."""
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        print(f"FAIL: {path} does not exist")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"FAIL: {path} is not valid JSON: {exc}")
        sys.exit(1)

    repos = data.get("repos")
    if not isinstance(repos, list) or not repos:
        print("FAIL: config.json must have a non-empty 'repos' array")
        sys.exit(1)

    for i, entry in enumerate(repos):
        missing = [k for k in REQUIRED if not entry.get(k)]
        if missing:
            print(f"FAIL: repos[{i}] ({entry.get('name', '?')}) missing {missing}")
            sys.exit(1)
    return repos


def check(entry):
    """Return (ok, detail) for one tracked repo: does its status_log.jsonl resolve?"""
    url = RAW.format(**entry)
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"network error: {exc.reason}"

    lines = [ln for ln in body.splitlines() if ln.strip()]
    if not lines:
        return False, "status_log.jsonl is empty"
    try:
        json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        return False, f"last line is not valid JSON: {exc}"
    return True, f"{len(lines)} entries"


def main():
    repos = load_config(CONFIG)
    failed = 0
    for entry in repos:
        ok, detail = check(entry)
        status = "ok  " if ok else "FAIL"
        target = f"{entry['owner']}/{entry['repo']}@{entry['branch']}"
        print(f"  [{status}] {entry['name']:8} {target:28} {detail}")
        if not ok:
            failed += 1

    print(f"\n{len(repos) - failed}/{len(repos)} tracked repos resolve")
    if failed:
        print("FAIL: at least one tracked repo does not resolve")
        sys.exit(1)


if __name__ == "__main__":
    main()