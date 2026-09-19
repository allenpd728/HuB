# Workflow handoff — install these four files, one per source repo

The sweep scripts are already committed and pushed to each source repo's `dev`
branch. These four workflow files were **not** pushed: the token available to
the agent has only the `repo` scope, and GitHub rejects any push or API write
that creates or updates a file under `.github/workflows/` without the
`workflow` scope. The rejection was verified both ways (see
`HUB_AGENT_HANDOFF.md` §"Write scope limit"). Installing them needs a token or
a UI session with `workflow` scope.

## Install (2 steps per repo)

For each repo `R` in {Maith, PleaNP, ephapse, muse}:

1. Copy `hub_sweep.yml.R` to `.github/workflows/hub_sweep.yml` in that repo,
   on the `dev` branch.
2. Commit and push.

With a suitably scoped token, from a clone on `dev`:

```bash
mkdir -p .github/workflows
cp /path/to/workflows-handoff/hub_sweep.yml.Maith .github/workflows/hub_sweep.yml
git add .github/workflows/hub_sweep.yml
git commit -m "ci(hub): schedule the status_log sweep"
git push origin dev
```

Or via the GitHub web UI: **Add file → Create new file** at
`.github/workflows/hub_sweep.yml`, paste the contents, commit to `dev`.

## Why the file differs per repo

Only in the script path (the repo layout differs):

| Repo | `hub_sweep.yml.<repo>` runs |
|---|---|
| Maith | `python3 tooling/hub_sweep.py` |
| PleaNP | `python3 tooling/hub_sweep.py` |
| ephapse | `python3 tooling/hub_sweep.py` |
| muse | `python3 tools/hub_sweep.py` |

## What it does

Every 30 minutes (and on manual dispatch) it appends one snapshot to that
repo's own `status_log.jsonl` on `dev` and pushes it. It is idempotent: if
nothing changed, it appends nothing and pushes nothing. It uses the repo's own
default `GITHUB_TOKEN` (read-only issues + push to the same repo) — no shared
secret, and no write to any other repo.

Pushing a snapshot triggers that repo's CI once. That is expected but not
desirable per-run, so the commit message carries `[skip ci]`; if a repo's CI
does not honour that, consider adding `paths-ignore: [status_log.jsonl]` to its
own CI trigger instead.

## Verify after installing

1. Actions tab → `hub_sweep` → **Run workflow** to trigger one manually.
2. Confirm `status_log.jsonl` gains a line and the run is green.
3. Open <https://allenpd728.github.io/HuB/> — that repo's tab dot should be
   **teal** (was amber). Teal here is the end-to-end proof: the sweep wrote
   data and HuB read it.

Both the sweep and the dashboard have also been verified locally/offline: the
sweep against live issue data for all four repos, and the dashboard rendering
the resulting records.