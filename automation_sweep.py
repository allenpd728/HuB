#!/usr/bin/env python3
"""automation_sweep.py — append one automation-health snapshot to status_log.jsonl.

HuB is a read-only dashboard: it fetches `status_log.jsonl` over the public CDN
(raw.githubusercontent.com) and renders it client-side. It cannot call the
GitHub API itself. The unauthenticated budget is 60 requests/hour *per visitor
IP*, and one page load that fetched comments would spend about a third of it —
breaking the page for everyone behind a shared address. So anything the
dashboard shows must be precomputed into this file by a scheduled job.

This script is that job. It answers "is the agent automation actually working?"
from data that is already public:

  * run activity — run-ids appear verbatim in agent comments
    (`run=YYYYMMDD-HHMM-xxxx`) across the four source repos. A run-id encodes
    its own UTC start time, so activity needs no extra API call to date.
  * real WIP — `claims/N.claim` files, which are the actual lock. The published
    `flow.wip` counts the `status:claimed` *label* instead, so it reads 0 while
    work is in flight. This block reports the claim files as well.
  * stale claims — a claim file whose issue is already CLOSED. Nothing releases
    the lock when an issue closes, so these accumulate and will mislead any
    claim-counting reader.
  * last run — the most recent run-id seen, with its start time.

Deliberately absent: failure rate and idle rate. A failed run dies before it
comments, so it leaves no public trace; only runs that got far enough to write
a comment are visible. Those numbers need the automation API and a credential,
which a static public page cannot hold. An absent field is a true statement; a
guessed zero is not.

Design rules (same as the source repos' hub_sweep.py):
  * Append only. One added line per sweep; existing lines never rewritten.
  * Honest numbers only — omit what cannot be computed. A 401 is raised rather
    than silently reported as "zero runs".
  * No duplicate snapshots unless --force.

Usage:
    python3 automation_sweep.py --selftest
    python3 automation_sweep.py --dry-run
    python3 automation_sweep.py

Exit codes: 0 wrote (or dry-run printed) a snapshot; 1 a real error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

LOG_NAME = "status_log.jsonl"
API = "https://api.github.com"
OWNER = "philipdallen"
SOURCE_REPOS = ("ephapse", "PleaNP", "rubato", "Maith")

# A run-id is <YYYYMMDD>-<HHMM>-<4 random alphanumerics>, per the contract.
RUN_RE = re.compile(r"run=(\d{8})-(\d{4})-([a-z0-9]{4})")
CLAIM_FILE_RE = re.compile(r"(\d+)\.claim")


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_run(text: str) -> tuple[str, dt.datetime] | None:
    """Return (run_id, start_time_utc) for the first run-id in `text`.

    A run-id carries its own start time, so the comment's created_at is not
    needed to date it. Returns None when absent or not a valid timestamp.
    """
    m = RUN_RE.search(text or "")
    if not m:
        return None
    run_id = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    try:
        start = dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M")
    except ValueError:
        return None
    return run_id, start.replace(tzinfo=dt.timezone.utc)


def _get(url: str, token: str | None) -> tuple[int, object]:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "hub-automation-sweep")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return 404, None
        # Never let an auth or rate-limit failure look like "no activity".
        if exc.code in (401, 403):
            raise RuntimeError(
                f"HTTP {exc.code} from {url} — token rejected or rate limited; "
                f"refusing to publish a zero"
            ) from exc
        return exc.code, None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"GET {url} failed: {exc}") from exc


def fetch_runs(repo: str, token: str | None, since: dt.datetime) -> dict[str, dt.datetime]:
    """Distinct run-ids seen in this repo's comments since `since`."""
    runs: dict[str, dt.datetime] = {}
    page = 1
    while page <= 5:
        url = (f"{API}/repos/{OWNER}/{repo}/issues/comments"
               f"?per_page=100&page={page}&since={since.isoformat()}")
        status, body = _get(url, token)
        if status != 200 or not isinstance(body, list) or not body:
            break
        for c in body:
            parsed = parse_run(c.get("body") or "")
            if parsed and parsed[1] >= since:
                runs[parsed[0]] = parsed[1]
        if len(body) < 100:
            break
        page += 1
    return runs


def fetch_claims(repo: str, token: str | None) -> list[int] | None:
    """Issue numbers with a claim file. None when the repo has no claims/ dir,
    which is different from an empty one: absent mechanism vs zero claims."""
    status, body = _get(f"{API}/repos/{OWNER}/{repo}/contents/claims", token)
    if status == 404:
        return None
    if status != 200 or not isinstance(body, list):
        return None
    out = []
    for entry in body:
        m = CLAIM_FILE_RE.fullmatch(entry.get("name") or "")
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def issue_state(repo: str, number: int, token: str | None) -> str | None:
    status, body = _get(f"{API}/repos/{OWNER}/{repo}/issues/{number}", token)
    if status == 200 and isinstance(body, dict):
        return body.get("state")
    return None


def build_automation(runs_by_repo: dict[str, dict[str, dt.datetime]],
                     claims_by_repo: dict[str, list[int] | None],
                     states: dict[tuple[str, int], str | None],
                     now: dt.datetime) -> dict:
    """Pure aggregation. All inputs are already-fetched data."""
    all_runs: dict[str, dt.datetime] = {}
    for runs in runs_by_repo.values():
        for run_id, ts in runs.items():
            if run_id not in all_runs or ts < all_runs[run_id]:
                all_runs[run_id] = ts

    day = now - dt.timedelta(hours=24)
    week = now - dt.timedelta(days=7)

    active = sorted({repo for repo, runs in runs_by_repo.items()
                     if any(ts >= day for ts in runs.values())})

    # Only repos that actually have the claims/ mechanism are counted; a repo
    # without it would otherwise contribute a false zero.
    held = {repo: len(nums) for repo, nums in claims_by_repo.items() if nums is not None}

    stale = []
    for repo, nums in claims_by_repo.items():
        for n in nums or []:
            if states.get((repo, n)) == "closed":
                stale.append(f"{repo} #{n}")

    out: dict = {
        "runs_24h": sum(1 for ts in all_runs.values() if ts >= day),
        "runs_7d": sum(1 for ts in all_runs.values() if ts >= week),
        "claims_total": sum(held.values()),
        "stale_claims_total": len(stale),
    }
    if active:
        out["repos_active_24h"] = active
    if held:
        out["claims_held"] = held
    if stale:
        out["stale_claims"] = sorted(stale)
    if all_runs:
        last = max(all_runs, key=lambda r: all_runs[r])
        out["last_run_id"] = last
        out["last_run"] = all_runs[last].replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return out


def build_notes(automation: dict) -> str:
    parts = [f"automation: {automation['runs_24h']} run(s)/24h, "
             f"{automation['runs_7d']} run(s)/7d"]
    if automation.get("repos_active_24h"):
        parts.append("active: " + ", ".join(automation["repos_active_24h"]))
    if automation.get("claims_total"):
        parts.append(f"{automation['claims_total']} claim(s) held")
    if automation.get("stale_claims_total"):
        parts.append(f"{automation['stale_claims_total']} STALE claim(s) "
                     f"({', '.join(automation.get('stale_claims', []))})")
    if automation.get("last_run"):
        parts.append(f"last run {automation['last_run']}")
    return " | ".join(parts)


def build_snapshot(runs_by_repo, claims_by_repo, states, now=None) -> dict:
    now = now or utcnow()
    automation = build_automation(runs_by_repo, claims_by_repo, states, now)
    return {
        "timestamp": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "automation": automation,
        "notes": build_notes(automation),
    }


# --------------------------------------------------------------------------
# Appending (same shape as the source repos' hub_sweep.py)
# --------------------------------------------------------------------------

def read_last_snapshot(path: Path) -> dict | None:
    if not path.exists():
        return None
    last = None
    for line in path.read_text().splitlines():
        if line.strip():
            last = line
    if not last:
        return None
    try:
        return json.loads(last)
    except json.JSONDecodeError:
        return None


def should_append(snapshot: dict, previous: dict | None, force: bool) -> bool:
    if force or previous is None:
        return True
    return snapshot.get("automation") != previous.get("automation")


def append(path: Path, snapshot: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.exists() else ""
    separator = "" if (not existing or existing.endswith("\n")) else "\n"
    with path.open("a") as fh:
        fh.write(separator + json.dumps(snapshot, sort_keys=True) + "\n")


# --------------------------------------------------------------------------

def selftest() -> int:
    """Prove the pure logic can fail. A check that cannot fail is not a check."""
    cases: list[tuple[str, bool]] = []

    got = parse_run("claimed by openhands run=20260923-0523-ez4n at 2026-09-23T05:24Z.")
    cases.append(("parse_run reads a valid id", got is not None and got[0] == "20260923-0523-ez4n"))
    cases.append(("parse_run dates from the id itself",
                  got is not None and got[1] == dt.datetime(2026, 9, 23, 5, 23, tzinfo=dt.timezone.utc)))
    cases.append(("parse_run ignores text without an id", parse_run("no run id here") is None))
    cases.append(("parse_run rejects an out-of-range month", parse_run("run=20261399-0000-aaaa") is None))
    cases.append(("parse_run rejects a short suffix", parse_run("run=20260923-0523-ab") is None))

    now = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.timezone.utc)
    runs = {"ephapse": {"20260923-1000-aaaa": now - dt.timedelta(hours=2),
                        "20260920-1000-bbbb": now - dt.timedelta(days=3)}}
    claims = {"ephapse": [39, 45], "Maith": None}
    states = {("ephapse", 39): "closed", ("ephapse", 45): "open"}

    a = build_automation(runs, claims, states, now)
    cases.append(("runs_24h counts only the recent run", a["runs_24h"] == 1))
    cases.append(("runs_7d counts both", a["runs_7d"] == 2))
    cases.append(("claims_total counts claim files", a["claims_total"] == 2))
    cases.append(("stale_claims flags a closed issue's lock", a["stale_claims"] == ["ephapse #39"]))
    cases.append(("stale_claims spares an open issue's lock", "ephapse #45" not in a["stale_claims"]))
    cases.append(("a repo without claims/ is excluded, not zeroed", "Maith" not in a["claims_held"]))
    cases.append(("last_run picks the newest id", a["last_run_id"] == "20260923-1000-aaaa"))
    cases.append(("repos_active_24h lists the busy repo", a["repos_active_24h"] == ["ephapse"]))

    # No runs at all must not fabricate a last_run.
    b = build_automation({"ephapse": {}}, {"ephapse": None}, {}, now)
    cases.append(("no runs -> no last_run field", "last_run" not in b))
    cases.append(("no runs -> runs_24h is 0", b["runs_24h"] == 0))

    # Dedup: the same run id in two repos is one run.
    c = build_automation({"ephapse": {"20260923-1000-aaaa": now - dt.timedelta(hours=1)},
                          "Maith": {"20260923-1000-aaaa": now - dt.timedelta(hours=1)}},
                         {}, {}, now)
    cases.append(("a run id shared across repos counts once", c["runs_24h"] == 1))

    failed = [label for label, ok in cases if not ok]
    for label, ok in cases:
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")
    if failed:
        print(f"\nSELF-TEST FAILED: {len(failed)} case(s): {failed}")
        return 1
    print(f"\nSELF-TEST OK: {len(cases)}/{len(cases)} cases behave as required")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append an automation snapshot for HuB.")
    parser.add_argument("--file", default=None,
                        help=f"log path (default: repo root / {LOG_NAME})")
    parser.add_argument("--token-env", default="GITHUB_TOKEN",
                        help="env var holding a token (optional for public repos)")
    parser.add_argument("--no-token", action="store_true",
                        help="force unauthenticated reads")
    parser.add_argument("--repos", default=",".join(SOURCE_REPOS),
                        help="comma-separated repo names to scan")
    parser.add_argument("--dry-run", action="store_true", help="print; write nothing")
    parser.add_argument("--force", action="store_true", help="append even if unchanged")
    parser.add_argument("--selftest", action="store_true", help="prove the logic can fail")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    repo_root = Path(os.environ.get("HUB_REPO_ROOT", ".")).resolve()
    log_path = Path(args.file) if args.file else repo_root / LOG_NAME
    token = None if args.no_token else (os.environ.get(args.token_env) or None)
    repos = [r.strip() for r in args.repos.split(",") if r.strip()]

    now = utcnow()
    since = now - dt.timedelta(days=7)
    runs_by_repo: dict[str, dict[str, dt.datetime]] = {}
    claims_by_repo: dict[str, list[int] | None] = {}
    states: dict[tuple[str, int], str | None] = {}

    try:
        for repo in repos:
            runs_by_repo[repo] = fetch_runs(repo, token, since)
            nums = fetch_claims(repo, token)
            claims_by_repo[repo] = nums
            for n in nums or []:
                states[(repo, n)] = issue_state(repo, n, token)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    snapshot = build_snapshot(runs_by_repo, claims_by_repo, states, now)
    previous = read_last_snapshot(log_path)

    if args.dry_run:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        verb = "append" if should_append(snapshot, previous, args.force) else "skip (unchanged)"
        print(f"(dry-run: would {verb} to {log_path})")
        return 0

    if not should_append(snapshot, previous, args.force):
        print(f"unchanged since last snapshot; nothing appended to {log_path}")
        return 0

    append(log_path, snapshot)
    print(f"appended to {log_path}: {snapshot['notes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
