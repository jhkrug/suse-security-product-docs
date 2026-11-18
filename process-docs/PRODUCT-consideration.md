# Product considerations

Why this repository exists, how it relates to the upstream community
repository, and the design choices behind it.

## The concept

There is one set of documentation. The upstream community repository,
[kubewarden/docs](https://github.com/kubewarden/docs), is the single source of
truth. It belongs to the Kubewarden CNCF open-source project.

This repository is downstream. It receives all the upstream content and
builds the SUSE Security product documentation from it.

The two repositories are separate only because of community and product
concerns:

- **CNCF.** A vendor-neutral CNCF project does not want product content in its
  repository.
- **SUSE.** SUSE Security is a fully supported, licensed product that comes
  from the project. Its documentation names the product, its registries, its
  Helm charts and its support.
- **Third parties.** Anybody can take the project code and documentation and
  use them as they want, including this product documentation. If the product
  documentation were in the community repository, a third party that offers
  support could ask for its offering to be documented there too. A separate
  product repository prevents this.

## How SUSE Security releases work

A SUSE Security release pins one version of each component.
[`suse-security.yml`](../shared/modules/ROOT/partials/releases/suse-security.yml)
lists the releases. Three tools read this file:

- The `productreleases` helper in `dsc-style-bundle`. The "Component /
  version" selector shows the SUSE Security releases, and a dropdown with the
  components of the current release. The page version menu shows the
  releases.
- The `release-url-layout` extension in `product-docs-common`. It publishes
  each release at `/suse-security/<release>/<lang>/`, for example
  `/suse-security/6.0.0/en/admission-controller/introduction.html`. It builds
  only the component versions that a release pins, and one landing page for
  each release. Its
  [README](https://github.com/rancher/product-docs-common/blob/main/extensions/release-url-layout/README.md)
  describes the configuration and the rules.
- The PDF build in `dsc-style-bundle`. It makes one PDF for each selected
  release and language. `product: suse-security` in `pdf-options.yml`
  selects the file.

The landing page sets the attributes `release-version` and
`release-<component>-version`. These product partials in
`docs/kw/version-1.0/modules/en/partials/product-specific/` use them to link
to the component versions of the release:

- `landing-components.adoc`
- `landing-nav.adoc`
- `landing-release-refs.adoc`

## Current design: copy and sync

The product repository is a copy of the upstream repository plus a small
product layer.

- `scripts/sync.py` and the `Sync with kubewarden/docs` workflow copy the
  upstream content to this repository. They copy the content under `docs/`
  and `shared/`, except the `community-specific/` directories. They do not
  copy the upstream tooling, for example `scripts/`, `.github/` and
  `updatecli/`. Each repository has its own tooling.
- The product layer is in `product-specific/` directories. The shared pages
  include build-specific content from `{build-type}-specific/` directories.
  The playbooks set `build-type: product`, so the product build uses the
  product files.
- The sync also keeps a few other differences from upstream. `AGENTS.md`
  lists them:
  - the `title:` of some `antora.yml` files, for example
    `Vulnerability Scanner` for `sbom-scanner`, and `SUSE Security` for `kw`
  - the language navs in the `nav:` list of the translated component versions
- The translations exist only in this repository. An automated translation
  process writes them. Until a page is translated, its language module holds
  a copy of the English page as a placeholder.

[rancher/product-docs-playbook](https://github.com/rancher/product-docs-playbook)
builds the published site from this repository and the other SUSE product
repositories. The playbooks in this repository are for local builds and
previews.

### What the sync must do

- Copy the upstream content under `docs/` and `shared/`, except
  `community-specific/`. Leave out the upstream tooling.
- Keep the product layer and the other differences listed in `AGENTS.md`.
- Bump `{release-tag}` and `{chart-version}` in the product `variables.adoc`
  of each component dev version. Upstream, updatecli bumps them only in
  `community-specific/variables.adoc`.
- For the translated component versions, copy new English pages into the
  language modules as placeholders, and add them to the language navs.
  Remove the pages that no longer exist in English.

[follow-ups.md](follow-ups.md) tracks the open items.

### Sync script

`scripts/sync.py` does the sync. `.upstream-ref` holds the upstream commit
of the last sync. The script compares the upstream changes since that commit
with this repository. It has three commands:

- `plan` writes a Markdown plan and changes nothing.
- `apply` makes the changes in the working tree, stages them and updates
  `.upstream-ref`. It does not commit. It writes the same report as `plan`.
  The report can be the body of the sync pull request.
- `copies` copies the English variables partials to the language modules.
  Run it after you change a product `variables.adoc`.

```bash
scripts/sync.py plan --output tmp/plan.md
scripts/sync.py apply --output tmp/sync.md
```

`apply` does these steps:

- It copies the upstream changes.
- It keeps the product lines of `antora.yml`.
- It merges the files changed upstream and here with `git merge-file`.
- It applies the English changes to the language modules. When upstream
  renames an attribute and the English line has no other change, it renames
  the attribute in the translated pages too.
- It bumps the release tags.
- It gives a new component version the product `title:` and a copy of the
  product layer of the version before it.

`apply` leaves the other work for a person and lists it in the report:

- merge conflicts
- product files and attributes to write
- new components
- upstream build changes
- translated pages deleted upstream
- stale translations

A translated page can still use a renamed attribute when the English line
has other changes too. The build log shows it as a missing attribute.

Exit status:

- `plan` returns 0 when there are no upstream changes, and 2 when there are.
- `apply` returns 0 when it is done, and 3 when the report lists work for a
  person.

### Sync workflow

The `Sync with kubewarden/docs` workflow, `.github/workflows/sync.yml`, runs
the script on demand. Start it from the Actions tab or with
`gh workflow run sync.yml`. The workflow does these steps:

1. It plans the sync. When there are no upstream changes, it stops.
2. When a sync pull request for the same upstream commit is open, it stops.
3. It applies the changes on a `sync/kubewarden-<sha>` branch.
4. It builds the site with `make product-local`.
5. `scripts/build-report.sh` writes a build report: the FATAL, ERROR and
   WARN counts of the build log, the missing attributes, and each entry
   with its file.
6. It opens a pull request with the sync report and the build report.
7. It closes the older sync pull requests that the new one replaces.

The pull request is a draft when the report lists work for a person, or
when the build has errors or missing attributes. The body of a draft starts
with "Why this pull request is a draft", with one bullet for each item.
`sync.py --attention` and `build-report.sh` write these bullets.

The `plan_only` input writes the plan to the run summary. It creates no
branch and no pull request.

[what-can-go-wrong.md](what-can-go-wrong.md) describes how the sync can fail
or give a wrong result, and how you find out.

### Why copy and sync

The product side receives all the upstream content, but it needs its own
configuration. For example, a SUSE Security release is a set of supported
component versions. See
[How SUSE Security releases work](#how-suse-security-releases-work).

A copy gives this flexibility. The product repository decides which upstream
content it takes and when. The sync pull request is a review point before
upstream changes reach the product documentation.

## Alternative: an overlay

Antora can combine content from more than one source into the same component
version. When two sources define the same `name@version`, Antora puts their
files together. For the component version properties (`title`, `nav`,
`start_page` and others), the source that is listed later wins. See
`buildAggregate` in `@antora/content-aggregator`.

So the product playbook could build directly from upstream, with this
repository as an overlay that holds only the product layer:

```yaml
content:
  sources:
    - url: https://github.com/kubewarden/docs.git
      start_paths: [shared, docs/*/version-*]
    - url: https://github.com/rancher/suse-security-product-docs.git
      start_paths: [shared, docs/*/version-*]
```

This repository would then hold only these files:

- the `product-specific/` files
- the translations
- a small `antora.yml` for each component version, with the product `title`
  and the `nav` list
- the build files

| | Copy and sync | Overlay |
|---|---|---|
| Sync script and GitHub Action | Needed | Not needed for the content. The placeholder logic for translations stays |
| Drift between the repositories | Possible | None for the shared content |
| Review point before upstream changes reach the product | Yes, the sync pull request | No, unless the playbook pins upstream to a tag or a branch |
| `community-specific/` content from upstream | The sync leaves it out | It gets into the build. An extension must remove it |
| Self-contained product repository | Yes | No, the build needs upstream |
| Product release configuration | Easy | Possible, but less direct |
| Risks | Errors in the sync | A file in both sources stops the build. The overlay must be the later source |

We keep copy and sync for now, because it gives more flexibility for the
product release configuration. We can look at the overlay again later.
Before a decision, test it with a local playbook that uses both sources.
