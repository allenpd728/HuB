# HuB — Agent Handoff

> **State correction (2026-09-19).** This repo was handed off with a
> `config.json` whose values did not match the source repos' actual state. The
> corrections below were verified against the GitHub API and are why
> `config.json` now reads as it does — don't "restore" the original values.
>
> | Original config | Verified reality | Fix applied |
> |---|---|---|
> | `Ephapse` / `main` | Repo is `ephapse` (lowercase) and **has no `main` branch** — only `dev`. | `repo: "ephapse"`, `branch: "dev"` |
> | `Maith` / `main` | Active development is on `dev`; `main` lags (16 ahead / 22 behind). Maith's `AGENTS.md` (DEC-036): "All development is on the single `dev` branch." | `branch: "dev"` |
> | `PleaNP` / `dev` | Correct as given. | unchanged |
> | — | `PM_STATUS_FRAMEWORK.md` existed in **no** tracked repo despite being cited as authoritative. | Added here, derived from what `index.html` actually consumes. |
> | — | No repo has a `status_log.jsonl` yet. | Expected — all tabs should show amber **empty**. Do not "fix". |
>
> Also verified: `philharmonic` is **private**, so it can never be tracked by this
> architecture (see §"Requirement: source repos must be public"). `muse` is public
> and active but is not tracked here; add it to `config.json` if wanted.

## What this repo is

HuB is a read-only, static dashboard aggregating `status_log.jsonl` from
Maith, PleaNP, and Ephapse (and any future research repo added to
`config.json`), rendering TRL maturity and Kanban flow metrics per repo.
Hosted on GitHub Pages. See PM_STATUS_FRAMEWORK.md (in Maith, or copied
here for reference) for what TRL and the flow metrics mean and where the
source data comes from.

## What this repo is not

- Not a place any repo's status data gets written. HuB only fetches and
  displays. Source repos own their own `status_log.jsonl` and write to it
  themselves via their own sweep extension.
- Not a build step, not a backend, not a database. Two static files
  (`index.html`, `config.json`) served by GitHub Pages. If this repo ever
  seems to need a server, that's a sign of scope creep — stop and check
  against this doc before adding one.
- Not authoritative. If HuB shows something a source repo's own issue
  tracker disagrees with, the source repo is correct — HuB is a mirror,
  reading data that can lag up to ~5 minutes behind a commit due to
  raw.githubusercontent.com's CDN cache.

## Architecture (why it's built this way)

- **`index.html`** fetches `config.json`, then for each listed repo,
  fetches `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/status_log.jsonl`
  directly, client-side, no backend.
- **Why raw.githubusercontent.com and not the GitHub API**: it's CDN-served,
  has no meaningful rate limit for this use, and sends permissive CORS
  headers so a static page can fetch it with no token. The GitHub API's
  60-request/hour unauthenticated limit would make this fragile for no
  benefit at this scale.
- **Why branch is a config value, not hardcoded**: PleaNP's active branch
  for its Circuits work is `dev`, not `main` — this has already caused a
  real mistake once (an agent assumed `main` and mis-planned against a
  17-line placeholder). `config.json` makes a branch change a one-line
  edit, not a code change.
- **Why this can never create cross-repo write conflicts**: HuB never
  writes to Maith, PleaNP, or Ephapse, and they never write to each
  other or to HuB. Each source repo's sweep only ever appends to its own
  file, on its own branch. Zero shared write surface, by construction —
  don't add one.

## Requirement: source repos must be public

`raw.githubusercontent.com` won't serve a private repo's contents to an
unauthenticated client-side fetch (e.g. `philharmonic` is private and therefore
cannot be tracked here), and a static page can't safely hold a personal access
token (visible to anyone via view-source). Confirm Maith, PleaNP, and Ephapse
stay public. If any repo ever needs to go private, the
fix is a scheduled GitHub Action *in that repo* copying its own
`status_log.jsonl` to a public location HuB can still read — never a token
embedded in HuB itself.

## `config.json` schema

```json
{
  "repos": [
    { "name": "Maith",   "owner": "allenpd728", "repo": "Maith",   "branch": "main" }
  ]
}
```

Adding a new tracked repo is an addition to this array, nothing else.
Changing a branch (e.g. if PleaNP's work moves off `dev`) is a one-field
edit here.

## Handling missing or broken source data (already built in, don't rebuild)

`index.html` already handles three states per repo, shown via a colored
dot on that repo's tab:
- **ok** (teal dot) — `status_log.jsonl` found and parsed.
- **empty** (amber dot) — repo reachable, file doesn't exist yet (404) or
  parsed to zero valid lines. This is the expected state for a
  freshly-kicked-off repo (e.g. Ephapse before its first sweep runs) — the
  page shows a message pointing at PM_STATUS_FRAMEWORK.md, not an error.
- **error** (rose dot) — fetch failed for another reason (repo went
  private, branch typo, network issue). Shows the HTTP status/detail.

Don't treat "empty" as a bug to fix in HuB — it's a correct signal that a
source repo hasn't wired up its sweep extension yet.

## Deployment

1. Repo settings → Pages → Deploy from a branch → `main`, `/ (root)`.
2. No build step. Confirm `index.html` and `config.json` are at repo
   root, not nested.
3. After enabling Pages, confirm the fetch actually resolves — open the
   page and check the tab dots go from grey (loading) to colored, not
   stuck grey (a stuck grey dot means the fetch itself failed silently;
   check browser console for a CORS or 404 detail).

## Single-branch policy

`main`, root, no exceptions — this repo is small enough that there's no
legitimate reason to diverge from Maith's own lesson (DEC-036, adopted
after parallel branches sprawled). Start here already following it.

## Immediate first issues

1. ~~Confirm `config.json`'s owner/repo/branch values are correct for all three
   source repos, and that all three are currently public.~~ **Done (2026-09-19).**
   See the state-correction table above: `ephapse`/`dev` and `Maith`/`dev` were
   wrong and are fixed. All three tracked repos are public.
2. **Enable GitHub Pages and confirm the dashboard loads**, showing the "empty"
   state correctly for all three repos (none has run its sweep extension yet —
   this is a valid, expected first-run state, not a failure to fix).
3. **Once any one source repo (Maith, PleaNP, or Ephapse) lands its sweep
   extension per `PM_STATUS_FRAMEWORK.md`**, confirm that repo's tab goes from
   amber (empty) to teal (ok) with real data — this is the actual end-to-end
   validation that the whole architecture works, more meaningful than anything
   that can be checked from HuB's side alone.

Do not add features (auth, write-back, alerting, a backend) before issue 3 has
been confirmed working with at least one real repo's real data.
