# PM Status Framework — `status_log.jsonl` schema

> This document defines the record schema HuB renders. `HUB_AGENT_HANDOFF.md`
> references this file as living "in Maith, or copied here for reference"; it was
> not present in any tracked repo when HuB was created, so this copy is derived
> from what `index.html` actually consumes and is now the canonical reference.
> If a source repo maintains its own copy, keep the field names in sync with this
> one — `index.html` reads the fields below by name.

## Purpose

Each tracked repo owns a `status_log.jsonl` at its repo root, on the branch named
in HuB's `config.json`. A per-repo **sweep extension** appends one snapshot object
per line, forever (append-only). HuB never writes this file; it only fetches and
displays it. See `HUB_AGENT_HANDOFF.md` §"What this repo is not".

## Record format

One JSON object per line (JSONL). Blank lines are ignored; a line that fails to
parse is silently dropped by the dashboard. Records are sorted client-side by
`timestamp`, so file order does not strictly matter — but append-only ordering is
the convention and is what keeps diffs readable.

```json
{"timestamp":"2026-09-19T19:00:00Z","trl":{"IR pipeline":4,"gates":2,"axiom search":1},"flow":{"wip":5,"blocked":1,"open_total":23,"blocked_ratio":0.043,"cycle_time_median_hours":18.5,"stale_reversions_since_last":0},"notes":"sweep: reclaimed 2 stale claims"}
```

### Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `timestamp` | string (ISO-8601, parseable by `new Date()`) | recommended | When the snapshot was taken. Used for ordering and the trend x-axis label (rendered as `MM-DD`). Missing/garbage timestamps collapse the ordering; always emit one. |
| `trl` | object: `{componentName: integer 0–9}` | optional | Technology-Readiness-Level per component. Rendered as bars; the **last** record's `trl` drives the per-component panel and the "TRL by component" card. |
| `flow` | object (see below) | optional | Kanban/flow metrics from the latest sweep. |
| `notes` | string | optional | Free-text note. Records that have `notes` populate the "Snapshot log" (last 12 shown, newest first). |

### `flow` object

| Key | Type | Meaning |
|---|---|---|
| `wip` | number | Work-in-progress count. |
| `blocked` | number | Blocked item count. |
| `open_total` | number | Total open items. |
| `blocked_ratio` | number 0–1 | Fraction blocked. Rendered as a percentage; coloured amber above `0.25`, rose above `0.40`. |
| `cycle_time_median_hours` | number | Median cycle time, hours. |
| `stale_reversions_since_last` | number | Reversions discovered by the stale-claim sweep since the previous snapshot. Coloured amber when `> 0`. |

Any absent `flow` key falls back to `0` in the rendered stat grid. The trend chart
plots, per record, the **mean of that record's `trl` values** against `0–9`, and
`blocked_ratio` against `0–1`.

### TRL rendering bands

`index.html` colours a TRL bar by value: `>= 6` teal, `>= 4` blue, `>= 2` amber,
otherwise rose. These thresholds are presentation only — they are a glanceable
cue, not a second definition. The meaning of a level is the table below.

## What TRL means here

TRL (Technology Readiness Level) is the standard 1–9 scale for how far a
technology is from a lab idea to routine operational use. It originated with NASA
for hardware and is widely applied to software. Applied to a research repo, the
"technology" is a **component**: a named capability the project intends to rely
on or hand to someone else — not the project as a whole, and not its research
hypothesis.

This scale is **adopted here by proposal** (2026-09-19) and is the semantic the
numbers are expected to carry. It is the piece the original handoff referenced as
defined in `PM_STATUS_FRAMEWORK.md` but which existed nowhere; this table is that
definition. Adjust it deliberately if it does not fit — but change it *here*, so
every repo reads the same meaning.

| Level | Name | What it means in a research repo |
|---|---|---|
| 1 | Principles observed | The idea is written down and motivated. No code. |
| 2 | Concept formulated | Scope and approach specified: what it does, its inputs and outputs, where it lives. Still no working code. |
| 3 | Proof of concept | A minimal prototype runs on a synthetic or toy case. Shows the mechanism works, not that it is correct on real inputs. |
| 4 | Validated in lab | Works on real project inputs in the dev environment; known-answer tests pass on a small case. |
| 5 | Validated in its own environment | Passes the repo's actual CI gates and fixtures, and is reproducible by a second agent from a clean checkout. |
| 6 | Demonstrated at intended scale | Runs end-to-end on the full intended corpus or input set, not a subset. |
| 7 | Used by a consumer | Something outside the component's own tests depends on it: a sibling module, another repo, or a human using its output for its real purpose. |
| 8 | Complete and qualified | All gates green, no known defects, documented, and frozen — changes are deliberate revisions rather than churn. |
| 9 | Proven in operation | Sustained real use producing results, with routine maintenance instead of active development. |

### Rules that keep the number honest

- **Rate the weakest real capability, not the best demo.** A component is only as
  ready as its least-ready load-bearing part.
- **A component can go down.** If a regression invalidates a claimed property,
  lower the number. A monotonic TRL is a warning sign, not a goal.
- **TRL is about the component's readiness, not the project's confidence in its
  hypothesis.** A well-built tool for testing a hypothesis that turned out false
  can still be TRL 8. Say so.
- **It is a judgement, not a measurement.** Do not invent decimals or derive it
  from issue counts — that is exactly why the sweep refuses to compute it.
- **Prefer several honest components over one vague aggregate.** `"project": 5` is
  not a useful entry.
- **Not every component needs a level.** Omit anything you would not defend.

### Relationship to ladders the repos already keep

Some repos already track per-deliverable status in their own docs — PleaNP's rung
table, Maith's hypothesis grid, ephapse's `claims/`. **Those remain
authoritative.** TRL is a coarse, hand-maintained summary for a cross-repo
dashboard, and it must not become a second tracker:

- Where a repo's own doc and HuB disagree, **the repo's own doc wins** — the same
  rule that already applies to `flow` metrics.
- Name TRL components after **capabilities you would hand to someone else**, not
  after internal tasks. That keeps the two axes genuinely different: a rung table
  says *what is in scope and in what order*; a TRL level says *how usable that
  piece is right now*.
- Update a level when the piece's **reusability** changes, not when a task moves
  label. If a task transition would change nothing for a consumer, it should not
  change the number.

### Who updates it, and when

TRL is set by a human who knows the project — typically the maintainer — and
reviewed at the same cadence as the repo's own status doc. It is **not** an agent
task and should not be changed by an automated sweep; the sweep only copies the
committed values into the next snapshot.

Mechanically: commit `status/trl.json` at the repo root on the tracked branch.
A change appears in the dashboard after the next sweep (up to 30 minutes, plus the
CDN's ~5 minutes). Each source repo's `docs/HUB_STATUS_LOG.md` lists that repo's
candidate components and carries a `status/trl.json.template` to start from —
rename the template to `trl.json` once real levels are set. Until then the field
is simply absent and HuB shows "No TRL entries", which is the correct state for a
repo that has not made the judgement yet.

## Where the data comes from

The sweep extension in each **source** repo is the writer. This is the only
sanctioned write path. HuB is a read-only mirror; if HuB and a source repo's own
tracker disagree, the source repo wins (HuB can also lag ~5 minutes behind a
commit because `raw.githubusercontent.com` is CDN-cached).

For the multi-agent workflow that produces these snapshots — run-ids, atomic
label claims, and stale-claim sweeps — see the source repos' own
`docs/MULTI_AGENT_WORKFLOW.md`.

## Current state

All four tracked repos (Maith, PleaNP, ephapse, muse) have the sweep extension
and the scheduled `hub_sweep` workflow installed on their tracked and default
branches, so `status_log.jsonl` exists and is appended to automatically. All four
dashboard tabs show real `flow` data.

`trl` is intentionally absent everywhere: no repo has committed `status/trl.json`
yet, so HuB shows "No TRL entries". That is the correct state for a repo that has
not made the human judgement described above — not a bug, and not something to
backfill with estimates.