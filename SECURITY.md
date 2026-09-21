# Security Policy

## Scope

HuB is a read-only static dashboard: two files (`index.html`, `config.json`)
served by GitHub Pages. It has no backend, no database, holds no credentials,
and accepts no user input or uploads. It fetches `status_log.jsonl` from four
public source repos client-side and renders it.

The realistic risk surface is therefore small, but not zero. The areas worth
attention:

- **Untrusted input rendering.** `index.html` renders values fetched from
  `raw.githubusercontent.com`. If those values were ever interpolated into HTML
  rather than text nodes, a crafted `status_log.jsonl` could inject script into
  the dashboard. Treat every fetched field as untrusted.
- **Tracked-repo configuration.** `config.json` determines which URLs the page
  fetches. A change here changes what the dashboard displays and where it
  fetches from.
- **Supply chain.** The page loads its renderer from a CDN. A compromised or
  unpinned dependency would execute in visitors' browsers.

## Supported versions

The dashboard is served from the `main` branch. Only the current `main` is
supported; there are no maintained release branches.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report it privately
via GitHub's [Report a vulnerability](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
flow on this repository, or by email to philip.d.allen@gmail.com.

Include the affected URL or file, what you observed, and the steps to reproduce.
Expect an initial response within a few days. This is a personal project
maintained on a best-effort basis, not a staffed product.