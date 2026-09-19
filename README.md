# HuB — Repo Status

A read-only, static dashboard that aggregates each tracked repo's
`status_log.jsonl` and renders TRL maturity and Kanban flow metrics per repo.
Two files (`index.html`, `config.json`) served by GitHub Pages. No build step,
no backend, no database.

This is a **mirror**: it only fetches and displays. Source repos own their own
`status_log.jsonl` and write it themselves. See
[`HUB_AGENT_HANDOFF.md`](HUB_AGENT_HANDOFF.md) for the architecture and its
rationale, and [`PM_STATUS_FRAMEWORK.md`](PM_STATUS_FRAMEWORK.md) for the record
schema every source repo must match.

## Tracked repos

`config.json` currently tracks three public repos, all on their active `dev`
branch:

| Repo | Owner / repo | Branch |
|---|---|---|
| Maith | `allenpd728/Maith` | `dev` |
| PleaNP | `allenpd728/PleaNP` | `dev` |
| Ephapse | `allenpd728/ephapse` | `dev` |
| Muse | `allenpd728/muse` | `dev` |

Adding a repo is one addition to the `repos` array. Note that
`raw.githubusercontent.com` only serves **public** repos to an unauthenticated
client-side fetch, so a private repo cannot be added.

## Deployment

1. Repo settings → Pages → Deploy from a branch → `main`, `/ (root)`.
2. No build step. `index.html` and `config.json` live at the repo root.
3. Open the page and confirm each tab's dot resolves from grey (loading) to a
   colour: teal = data found, amber = no `status_log.jsonl` yet (expected today),
   rose = fetch error (repo private, branch typo, network).

## Current state

All four source repos have the sweep extension (`tooling/hub_sweep.py`, or
`tools/hub_sweep.py` in muse) and the scheduled `hub_sweep` workflow installed
on their `dev` and default branches. All four dashboard tabs render **teal
(ok)** with real data. The workflow is idempotent: on a run with no change it
appends nothing.