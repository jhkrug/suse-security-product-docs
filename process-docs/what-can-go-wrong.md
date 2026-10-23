# What can go wrong with the sync

How the sync with the upstream
[kubewarden/docs](https://github.com/kubewarden/docs) can fail or give a
wrong result, and how you find out. The sync is `scripts/sync.py` and the
`Sync with kubewarden/docs` workflow, `.github/workflows/sync.yml`. See
[PRODUCT-consideration.md](PRODUCT-consideration.md) for how they work.

Most problems are loud: the run fails, or the sync pull request is a draft.
The risks are the cases where the run is green but the result is wrong or
incomplete, and the fact that a failed run reaches only one person.

## How a problem shows

| What happens | Where it shows |
|---|---|
| The script or a step fails: `sync.py` exits 1, a git or push error, a Python traceback | The run fails. GitHub emails only the person who started it. For a scheduled run, it emails the person who last changed the schedule. No issue, no team notification. |
| `apply` lists work for a person, or the build has errors or missing attributes | The pull request is a draft. Its body starts with "Why this pull request is a draft": one bullet for each item and build problem. The body also has a build report: the FATAL, ERROR, and WARN counts, the missing attributes, and each entry with its file. |
| The workflow may not create the pull request | The run fails with an error annotation. The run summary has the compare link. |
| A sync pull request for the same upstream commit is already open | The run does nothing and says so in the summary, so that fixes pushed to the branch stay. |
| A newer sync pull request is opened | The workflow closes the older sync pull requests with a comment that links to the new one. Their branches stay. |
| Informational report sections: "Local differences", "Product layer", "Upstream tooling to review", "Stale translations" | Only in the pull request body. They do not make it a draft. "Upstream build changes" does. |

## Upstream changes

| Upstream change | Effect | Visible |
|---|---|---|
| `main` renamed, repository moved, or history rewritten | The fetch fails, or `base is not an ancestor of head` | Loud: the run fails |
| A shared page includes a new `{build-type}-specific/` partial | The report lists "create product-specific/…". The build logs a missing include | Loud: draft |
| A new attribute in a `community-specific/` file | Reported when no product-specific file or shared partial defines it. A removed attribute that a product file still defines is listed | Loud: draft |
| An attribute renamed that translated pages still use | Fixed when the English line differs only in the attribute names. Otherwise the build shows a missing attribute | Mostly loud |
| A new component version | Copied. Its `antora.yml` gets the product `title:` of the version before it, and its product layer is copied from that version. The release tags are bumped in the copy | Loud: draft, to review the copied values |
| A new component, a new `docs/<component>/` | Copied. The report asks for a product layer and title, and for each playbook whose `start_paths` do not include it | Loud: draft |
| An old version deleted | The English and language files go. The product-specific files stay and can break the build | Loud (build), or orphan files |
| A page moved and changed so much that git sees a delete and an add | Rename detection uses a 40% similarity threshold, so most moves are seen. Otherwise the translations are kept, not deleted, and the report suggests the new page with the same file name | Loud: draft |
| Build changes: `package.json`, the lockfile, `Makefile`, `.gitmodules`, the `docs-common` submodule, playbooks, `ui/` | Listed under "Upstream build changes". For a `docs-common` bump, the report compares it with `product-docs-common` | Loud: draft |
| Other tooling changes: `AGENTS.md`, `.github/`, `updatecli/`, `scripts/` | Listed under "Upstream tooling to review" | Informational |
| Product release tags that differ from upstream, for example without the leading `v` | The upstream value goes into the product `variables.adoc`. See [follow-ups.md](follow-ups.md) | Silent: wrong value |
| A merge that is clean as text but wrong in meaning | Listed under "Merged" | Needs review |

## Changes in this repository

| Change | Effect |
|---|---|
| A local edit to a copied file, which `AGENTS.md` does not allow | Later upstream changes merge with it. A clean merge keeps the edit without a warning. A conflict keeps the local file and makes the pull request a draft. |
| A person pushes fixes to an open sync branch, and the workflow runs again | The run sees the open pull request and does nothing. |
| An older sync pull request is still open when upstream moves on | The next run opens a new pull request and closes the older one. Fixes pushed to the older branch must be carried over by hand; the closing comment says so. |
| `.upstream-ref` moved forward without a sync | The upstream changes in between are never applied. They show only under "Local differences". |
| `.upstream-ref` not updated after a manual sync | Harmless. The next run lists those files under "Already applied". |
| The Makefile or playbook stops writing `tmp/build.log` | `scripts/build-report.sh` reports that the log is missing or empty and the pull request is a draft. |
| The Makefile or playbook changes the log format | `scripts/build-report.sh` counts the Antora levels in `--log-format=pretty`, for example `] ERROR (`. With another format it finds nothing and passes. |
| The `make product-local` exit status | `tee` hides the Antora exit status, so the counts in the log are the real check. |
| Hand edits to the language copies of the variables partials | `apply` and `copies` overwrite them. This is intended. |
| The translation process changes the same files while a sync pull request is open | Normal merge conflicts in the pull request. |
| The organization stops workflows from creating pull requests, limits the token, or adds rules for `sync/*` branches | The run fails. |
| Runner image changes (Ubuntu 26), Node.js, or npm problems | Usually a failed build, so a draft. |

## Hardening

Done:

- The run fails when the pull request cannot be created.
- The run does nothing when a sync pull request for the same upstream commit
  is open, and it closes the sync pull requests that a new one replaces.
- `scripts/build-report.sh` checks the build log.
- `scripts/sync.py` gives new component versions the product title, reports
  new components, upstream build changes, translated pages deleted upstream,
  and attributes added to or removed from `community-specific/` files.

To do:

1. For scheduled runs, open or update an issue when a run fails, so that the
   team sees it.
