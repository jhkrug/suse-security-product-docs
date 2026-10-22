# AGENTS.md — SUSE Security product docs

## Do the work upstream

This repository is a copy of the upstream community repository,
[kubewarden/docs](https://github.com/kubewarden/docs), plus a small product
layer. Make all content and structure changes in `kubewarden/docs`. Read the
`AGENTS.md` of that repository for the conventions. A script and a GitHub
Action copy the upstream changes to this repository and overwrite local edits
to the copied files.

Do not change files here unless they are in the list below.

For why this repository exists and the design choices behind it, see
[process-docs/PRODUCT-consideration.md](process-docs/PRODUCT-consideration.md).

## What belongs here

- Files in `product-specific/` directories, under `shared/` and under each
  component version. These hold the product values and text that the shared
  pages include with `{build-type}-specific/`:
  - `variables.adoc`, `globals.adoc`, and the component wrappers
    `<key>-variables.adoc`: product names, registries, Helm charts,
    namespaces, release tags.
  - Partials for passages that differ in the product build.
  - Pages, nav fragments, and images that exist only in the product build.
- The `title:` of these `antora.yml` files. The sync keeps them:
  - `docs/sbom-scanner/version-*/antora.yml`: `Vulnerability Scanner`
  - `docs/kw/version-*/antora.yml`: `SUSE Security`
- The language navs in the `nav:` list of the `antora.yml` of each translated
  component version, for example `modules/de/nav.adoc`. The sync keeps them.
- Build files: the `local-product-playbook.yml` and
  `remote-product-playbook.yml` playbooks, `Makefile`, `package.json`,
  `package-lock.json`, `.gitmodules`, and the `dsc-style-bundle` and
  `product-docs-common` submodules.
- `scripts/` and `.github/`: tooling and workflows for this repository, for
  example the sync script. Upstream has its own `scripts/` and `.github/`
  for the community repository. The sync does not copy them.
- `.upstream-ref`: the upstream commit of the last sync. A sync commit
  updates it. `scripts/sync.py` syncs from it.
- `process-docs/`: notes about this repository and its processes:
  - `PRODUCT-consideration.md`: why this repository exists, and the design
    of the sync.
  - `follow-ups.md`: open questions and known issues.
  - `what-can-go-wrong.md`: how the sync can fail, and how it is reported.

The automated translation process writes the localized content, the language
modules other than `en`. Do not edit the translations. Until a page is
translated, its language module holds a copy of the English page as a
placeholder, and the language `nav.adoc` lists it in the English position. A
language module holds no page that the English module does not have.

If a change could go upstream, make it upstream.

## Build and preview

```bash
# Build site locally (uses local filesystem sources)
make product-local

# Serve the built site
make preview

# Rebuild on file change and live-reload the browser (http://127.0.0.1:8080)
make dev
```

Build output lands in `build/site/`. Logs are written to `tmp/build.log`.
The playbooks set `build-type: product` and `attribute-missing: warn`. A
reference to an undefined attribute causes a `WARN (asciidoctor): skipping
reference to missing attribute` line in `tmp/build.log`.

The published site is built by
[rancher/product-docs-playbook](https://github.com/rancher/product-docs-playbook),
not by the playbooks in this repository.
