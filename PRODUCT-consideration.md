# Product considerations

Why this repository exists, how it relates to the upstream community
repository, and the design choices behind it.

## The concept

There is one set of documentation. The upstream community repository,
[kubewarden/docs](https://github.com/kubewarden/docs), is the single source of
truth. It belongs to the Kubewarden CNCF open-source project.

This repository is downstream. It receives all the upstream content and
builds the SUSE Security product documentation from it.

The two are separate only because of community and product concerns:

- **CNCF.** A vendor neutral CNCF project does not want product content in its
  repository.
- **SUSE.** SUSE Security is a fully supported, licensed product that comes
  from the project. Its documentation names the product, its registries, its
  Helm charts, and its support.
- **Third parties.** Anybody can take the project code and documentation and
  use them as they want, including this product documentation. If the product
  documentation were in the community repository, a third party that offers
  support could ask for its offering to be documented there too. A separate
  product repository prevents this.

## Current design: copy and sync

The product repository is a copy of the upstream repository plus a small
product layer.

- A script and a GitHub Action (not written yet) copy the upstream content to
  this repository. They copy everything except the `community-specific/`
  directories.
- The product layer is in `product-specific/` directories. The shared pages
  include build specific content with `{build-type}-specific/`. The playbooks
  set `build-type: product`, so the product build uses the product files.
- A few other differences from upstream are also kept by the sync. `AGENTS.md`
  lists them:
  - the `title:` of some `antora.yml` files, for example
    `Vulnerability Scanner` for `sbom-scanner`, and `SUSE Security` for `kw`
  - the language navs in the `nav:` list of the translated component versions
- The translations exist only in this repository. The automated translation
  process writes them. Until a page is translated, its language module holds
  a copy of the English page as a placeholder.

The published site is built by
[rancher/product-docs-playbook](https://github.com/rancher/product-docs-playbook)
from this repository, together with the other SUSE product repositories. The
playbooks in this repository are for local builds and previews.

### What the sync must do

- Copy the upstream content, except `community-specific/`.
- Keep the product layer and the other differences listed in `AGENTS.md`.
- Bump `{release-tag}` and `{chart-version}` in the product `variables.adoc`
  of each component dev version. Upstream, updatecli bumps them only in
  `community-specific/variables.adoc`.
- For the translated component versions, copy new English pages into the
  language modules as placeholders, add them to the language navs, and remove
  pages that no longer exist in English.

`follow-ups.adoc` tracks the open items.

### Why copy and sync

The product side receives all the upstream content, but it is likely to need
its own configuration. For example, a SUSE Security release can be a set of
supported component versions:

| SUSE Security | Admission Controller | Vulnerability Scanner | Runtime Enforcer | Network Enforcer |
|---|---|---|---|---|
| 1.0 (example) | 1.38 | 0.13 | ... | ... |

A copy gives this flexibility. The product repository decides which upstream
content it takes and when, and the sync pull request is a review point before
upstream changes reach the product documentation.

## Alternative: an overlay

Antora can combine content from more than one source into the same component
version. When two sources define the same `name@version`, Antora puts their
files together. For the component version properties (`title`, `nav`,
`start_page`, and others), the source that is listed later wins. See
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

This repository would then hold only the `product-specific/` files, the
translations, a small `antora.yml` for each component version (with the product
`title` and the `nav` list), and the build files.

| | Copy and sync | Overlay |
|---|---|---|
| Sync script and GitHub Action | Needed | Not needed for the content. The placeholder logic for translations stays |
| Drift between the repositories | Possible | None for the shared content |
| Review point before upstream changes reach the product | Yes, the sync pull request | No, unless the playbook pins upstream to a tag or a branch |
| `community-specific/` content from upstream | The sync leaves it out | It gets into the build. An extension must remove it |
| Self contained product repository | Yes | No, the build needs upstream |
| Product release configuration | Easy | Possible, but less direct |
| Risks | Errors in the sync | A file in both sources stops the build. The overlay must be the later source |

We keep copy and sync for now, because of its flexibility for product release
configuration. The overlay is an option to look at again later. Before a
decision, test it with a local playbook that uses both sources.
