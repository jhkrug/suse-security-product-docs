# Next steps for the SUSE Security product docs

Planned work for the product build. Open questions and known issues are in
[follow-ups.md](follow-ups.md). Remove an item when it is done.

## How releases work

SUSE Security releases pin one version of each component.
[`suse-security-release-config.yml`](../shared/modules/en/partials/product-specific/suse-security-release-config.yml)
lists them. Two tools read it:

- The `productreleases` helper in `dsc-style-bundle`: the "Component /
  version" selector shows the SUSE Security releases and a dropdown with the
  components of the current release. The page version menu shows the
  releases.
- The `release-url-layout` extension in `product-docs-common`: it publishes
  each release at `/suse-security/<release>/<lang>/`, for example
  `/suse-security/6.0.0/en/admission-controller/introduction.html`. It builds
  only the component versions that a release pins, and one landing page for
  each release. Its
  [README](https://github.com/rancher/product-docs-common/blob/main/extensions/release-url-layout/README.md)
  describes the configuration and the rules.

The landing page sets `release-version` and `release-<component>-version`.
The product partials `landing-components.adoc`, `landing-nav.adoc`, and
`landing-release-refs.adoc` in `docs/kw/version-1.0/modules/en/partials/product-specific/`
use them to link to the component versions of the release.

## Installation

None of this goes into the community docs. Use the product facilities:
product-only pages and nav entries in `product-specific/` directories,
`{build-type}-specific` partials with an include point upstream when a shared
page must differ, and the release config.

1. **SUSE Security production installation.** A page that installs SUSE
   Security with the umbrella Helm chart that is being developed.
   - Put it in the landing component, under
     `docs/kw/version-1.0/modules/en/pages/product-specific/`, and link it
     from the product `landing-nav.adoc`, which this repository owns.
   - If the chart version differs for each release, add it to the release
     config. The extension and the helper check the config strictly, so the
     new key needs a change in both. The extension can then set it as a
     `release-*` attribute on the landing page of each release.
2. **Remove the per-component installation instructions.** The umbrella
   installation replaces them in the product build. The pages come from
   upstream, and the community build still needs them.
   - Add `{build-type}-specific` include points upstream where the install
     steps are, so that the community partial keeps the steps and the product
     partial points to the umbrella installation. The nav entries need the
     same treatment.
   - Decide whether the product build keeps short pages that point to the
     umbrella installation, or leaves the pages out.
3. **Admission Controller only, Rancher Prime.** A product-only installation
   of Admission Controller on its own, for Rancher Prime. A page in
   Admission Controller's `product-specific/` pages and a product nav entry.
   If it replaces install steps on a shared page, use the include points from
   item 2.

## Publishing

4. **Switch the published site to this repository.** `rancher/product-docs-playbook`
   builds the published site. When this repository goes live:
   1. Remove the demo release 5.9.9 from the release config.
   2. In `product-docs-playbook-remote.yml` and `product-docs-playbook-local.yml`:
      - Replace the `kubewarden-product-docs`, `sbomscanner-product-docs`,
        and `runtime-enforcer-product-docs` sources with one source for this
        repository, with the start paths of `remote-product-playbook.yml`.
      - Register `./product-docs-common/extensions/release-url-layout/release-url-layout.js`
        before `vlp.js`, as in `remote-product-playbook.yml`.
   3. Bump the `dsc-style-bundle` and `product-docs-common` submodules of
      `product-docs-playbook` to versions with the release support:
      dsc-style-bundle #90, #91, and #92, and product-docs-common #104.
   4. Build the site with and without the change, and compare. On
      2026-10-28 a build with this repository in place of the old sources was
      clean: no new warnings, and no broken relative links in the SUSE
      Security pages. A build with only the submodule bumps was identical to
      the published site, apart from expected markup.

   See also **Mermaid diagrams in the publishing playbook** and
   **Publishing playbook** in [follow-ups.md](follow-ups.md).

## Decisions

5. **Redirects from the old URLs.** The old per-component URLs, for example
   `/admission-controller/1.38/...` and `/vulnerability-scanner/0.12.0/...`,
   stop working when the published site switches. The decision for now is no
   redirects: SUSE Security is a new product. The extension could add them
   later without a change to the release config.
6. **The old product repositories.** Archive `kubewarden-product-docs`,
   `sbomscanner-product-docs`, and `runtime-enforcer-product-docs` after the
   published site switches?
