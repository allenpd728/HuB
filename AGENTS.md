# AGENTS.md — HuB

Repository-specific context for agents working in this repo.

## What this repo is

A static GitHub Pages dashboard. `index.html` and `config.json` at the repo
root; no build step. It fetches `status_log.jsonl` from each tracked repo over
`raw.githubusercontent.com` and renders one tab per entry.

## Hard constraints (do not break these)

- **The page cannot call the GitHub API.** It has no backend and no credentials,
  and the unauthenticated budget is 60 requests/hour *per visitor IP* — one page
  load that fetched issue comments would spend about a third of it and break the
  page for everyone behind a shared address. Anything the dashboard displays must
  be precomputed into a `status_log.jsonl` by a scheduled job.
- **Only public repos can be tracked.** `raw.githubusercontent.com` serves
  private repos as 404 to an unauthenticated fetch. Do not add a private repo to
  `config.json`.
- **An absent field is a true statement; a zero is often a false one.** This is
  the rule the sweeps follow and the page follows. Render an unmeasured field as
  an em dash (`—`), never as `0`. See `renderStats`/`renderAutomation` and
  `portfolio-ops/METRIC_CONTRACT.md` (private) rule 4.
- **`config.json` wins over any doc.** README tables are snapshots; read the live
  value from `config.json`. The branch field is whatever branch the source repo's
  sweep writes to, which is not necessarily its default branch.
- **Escape every fetched value.** All log content is untrusted. Pass it through
  `esc()` on the way into a template. A field added without `esc()` is an XSS
  hole; see `SECURITY.md`.

## Conventions

- Every check must be shown to fail. `tools/validate_config.py --self-test` and
  `automation_sweep.py --selftest` both run in CI. A check that cannot fail is
  not a check. When adding one, verify it by mutation: break the logic, confirm
  the selftest reports FAIL, then restore.
- Sweeps append exactly one JSONL line, skip the append when the computed
  snapshot is unchanged (unless `--force`), and never rewrite existing lines.
- Workflows that push rebase-and-retry on rejection; never force-push, which
  would destroy a sibling's committed work.

## Environment note

Two credential variables exist in the agent environment and they are **different
tokens**:

- `GITHUB_TOKEN` — valid. Use this one.
- `GH_TOKEN` — stale, returns `401 Bad credentials`.

`gh` prefers `GH_TOKEN`, so any `gh` command fails with "Bad credentials" even
though a perfectly good token is present. This looks exactly like an expired
token and is not. Diagnose it by testing each variable independently:

```bash
env -u GH_TOKEN bash -c 'curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user'
env -u GITHUB_TOKEN bash -c 'curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/user'
```

The fix is to `unset GH_TOKEN` (or use `env -u GH_TOKEN`) before `gh` and
`git push`. `curl` with an explicit `Authorization` header and `git` with the
token in the remote URL both work already, which is why reads succeed while
`gh` fails. Reads of public repos also work fully unauthenticated, so
`automation_sweep.py --no-token` and `validate_config.py` run without any token.
