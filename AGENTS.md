# AGENTS.md — SUSE Security product docs

## Do the work upstream

This repository is a copy of the upstream community repository,
[kubewarden/docs](https://github.com/kubewarden/docs), plus a small product
layer. Make all content and structure changes in `kubewarden/docs`. Read the
`AGENTS.md` of that repository for the conventions. A script and a GitHub
Action copy the upstream changes to this repository. Do not edit a copied
file here. At the next sync, the local edit can stay in place without a
warning, or it can cause a merge conflict.

Change only the files in the list below.

For why this repository exists and the design choices behind it, see
[process-docs/PRODUCT-consideration.md](process-docs/PRODUCT-consideration.md).

## What belongs here

- Files in `product-specific/` directories, under `shared/` and under each
  component version. These files hold the product values and text. The
  shared pages include files from `{build-type}-specific/` directories. The
  product build sets `build-type: product`, so it uses the files in
  `product-specific/`. These files are:
  - `variables.adoc` in each component version, and `globals.adoc` and
    `<key>-variables.adoc` in `shared/`: product names, registries, Helm
    charts, namespaces and release tags. A `<key>-variables.adoc` file holds
    the values that are the same in all versions of one component. The keys
    are `admc`, `kw`, `ne`, `rte` and `sboms`.
  - Partials for passages that differ in the product build.
  - Pages, nav fragments, and images that exist only in the product build.
  - `shared/modules/en/partials/product-specific/suse-security-release-config.yml`:
    the SUSE Security releases and the component versions that each release
    pins. The selectors in `dsc-style-bundle` and the `release-url-layout`
    extension in `product-docs-common` read it.
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
  - `PRODUCT-consideration.md`: why this repository exists, how the SUSE
    Security releases work, and the design of the sync.
  - `follow-ups.md`: open questions and known issues.
  - `next-steps.md`: planned work, for example the installation pages and
    the switch of the published site to this repository.
  - `what-can-go-wrong.md`: how the sync can fail, and how it is reported.

An automated translation process writes the translations. The translations
are in the language modules, all modules other than `en`. Do not edit the
translations. Until a page is translated, its language module holds a copy
of the English page as a placeholder. The language `nav.adoc` lists the copy
in the same position as the English `nav.adoc`. Each page in a language
module also exists in the English module.

If a change could go upstream, make it upstream.

## Writing style

Write the product text to these standards. The product text is the pages
and partials in the `product-specific/` directories.

- The SUSE Style Guide. The AI prompts for it are in
  `product-docs-common/ai-prompts/suse-style-guide/`, a submodule of
  `product-docs-common`. To get them, run
  `git submodule update --init --recursive`. `Style-Guide-onefile.md` is the
  short version. The full guide is at
  <https://documentation.suse.com/style/current/>.
- ASD-STE100 Simplified Technical English (STE): one idea for each sentence,
  short sentences, active voice, simple words, and no phrasal verbs.

The most important rules:

- Use no serial comma: "learn, monitor and protect".
- Write H2 and H3 headings as natural-language questions where they fit, in
  sentence case, with no trademarks. Make sibling headings parallel.
- Start a page with a direct answer of 40 to 80 words. Do not start with
  "This page explains".
- Write `:description:` as one complete sentence of 120 to 155 characters,
  with no full stop at the end.
- Expand an acronym on first use.
- Give each section an explicit ID in the form of the ID that Asciidoctor
  generates from the title: an underscore, then the words of the title in
  lowercase with underscores between them. For example, the ID of
  `== What does each component do?` is `[#_what_does_each_component_do]`.
  The explicit ID is then the same as the generated ID, so links stay the
  same. Give tables and figures short IDs in the same form, with the prefixes
  `_tab_` and `_fig_`, for example `[#_tab_components]`. With a role, put the
  ID first: `[#_components.component-grid]`.
- Present SUSE Security as one integrated product, installed with one Helm
  chart. Do not write that the components can be used on their own. That is
  community messaging.

Upstream content follows the conventions of `kubewarden/docs`.

## Build and preview

```bash
# Build site locally (uses local filesystem sources)
make product-local

# Serve the built site
make preview

# Rebuild on file change and live-reload the browser (http://127.0.0.1:8080)
make dev
```

The build writes the site to `build/site/` and the log to `tmp/build.log`.
The playbooks set `build-type: product` and `attribute-missing: warn`. A
reference to an undefined attribute causes a `WARN (asciidoctor): skipping
reference to missing attribute` line in `tmp/build.log`.

The published site is built by
[rancher/product-docs-playbook](https://github.com/rancher/product-docs-playbook),
not by the playbooks in this repository.

### PDFs

`pdf-options.yml` activates the PDF build of `dsc-style-bundle/pdf/`. Refer
to `dsc-style-bundle/pdf/README.md`.

```bash
# Build the PDFs into build/pdf/ (and copy them into build/site/ if it exists)
make local-pdf

# Then build the site with the PDFs and the PDF links
make product-local
```

- The mode is `deliverable`. The preview workflow (`.github/workflows/preview.yml`)
  runs `make pdf` before `make product-remote`.
- There is one PDF for each language of the latest release: the landing
  pages, then each component. A component without a translation is in
  English.
- The first `make local-pdf` installs the tools and fonts in `tmp/pdf-tools/`.
- `site_url` is the preview site. Change it when the production site is
  published.
