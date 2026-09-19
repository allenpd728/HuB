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
otherwise rose. These thresholds are presentation only — they carry no
project-management meaning beyond "higher is further along".

## Where the data comes from

The sweep extension in each **source** repo is the writer. This is the only
sanctioned write path. HuB is a read-only mirror; if HuB and a source repo's own
tracker disagree, the source repo wins (HuB can also lag ~5 minutes behind a
commit because `raw.githubusercontent.com` is CDN-cached).

For the multi-agent workflow that produces these snapshots — run-ids, atomic
label claims, and stale-claim sweeps — see the source repos' own
`docs/MULTI_AGENT_WORKFLOW.md`.

## Not yet implemented

No tracked repo has landed its sweep extension yet, so no `status_log.jsonl`
exists and every HuB tab legitimately shows the **empty** (amber) state. That is
the correct first-run signal, not a bug. Do not add HuB-side fallbacks or seed
data to make the dashboard look populated.