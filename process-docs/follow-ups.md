# Follow-ups for the SUSE Security product docs

Open questions and known issues found while building this repository from
the upstream community repository. Remove an item when it is done.

## Values to confirm

- **Admission controller image tags.** In `admission-controller/version-1.40`,
  the dev version, `{release-tag}` (`v1.39.0`) is the upstream tag. The
  product file assumes that the product image tags are the same.
  `{default-policy-server-image-tag}` uses `{release-tag}` to make the
  `dp.apps.rancher.io` image reference. If the product image tags
  have no leading `v`, add a separate image tag attribute.
- **Release tags and chart versions.** The product `variables.adoc` of every
  component dev version copies `{release-tag}` and `{chart-version}` from
  upstream. Confirm that the product versions are the same. Upstream, the
  updatecli job bumps them only in `community-specific/variables.adoc`.
  `scripts/sync.py` copies the new values to the product files.
- **Network Enforcer chart.** `{network-enforcer-helm-chart}` is a guess,
  `oci://dp.apps.rancher.io/charts/suse-security-network-enforcer`. No page
  uses it at the moment.
- **Hauler manifest signing identity.** `:hauler-manifest-cert-identity:` in
  the `admission-controller` 1.39 and 1.40 `variables.adoc` is an exact
  identity. It is correct because the signing workflow in `rancher/suse-security` signs only
  on `main`. If the workflow ever signs from tags or from a reusable
  workflow, change the identity. Use `--certificate-identity-regexp` with
  `--certificate-github-workflow-repository` and
  `--certificate-github-workflow-ref`, and add the values as attributes. Also
  state a minimum cosign version, after you test it with the real bundle.
- **Hauler manifest attachments.** The links to the manifest and the bundle in
  `airgap-hauler-download.adoc` stay broken until the first pull request of
  the `Update Hauler manifest` workflow is merged. Merge in this order: the
  first signed manifest pull request in `rancher/suse-security`, the copy
  workflow of this repository and its first pull request, which adds the
  attachments, and only then the docs pages that link the files. Until then, the English build logs
  two `target of xref not found` errors. When a sync refreshes the language
  placeholders, each language build logs the two errors, 14 in total. The
  script `scripts/build-report.sh` then makes the sync pull requests drafts.
- **Hauler example image names.** The example image names are now in the text
  of the upstream page `pages/howtos/airgap/02-hauler.adoc`, section
  "Generate the tarball file". They show `policy-server` and kyverno, for
  example. The product image names are different, for example
  `kubewarden-policy-server`. Decide if the page text needs a product version.
  The "Install" section of the same page also tells users to set the
  `PolicyServer` image to
  `<REGISTRY>/{default-oci-admcontroller-container-namespace}/policy-server:{release-tag}`.
  In the product build this name is wrong, because the product image is
  `kubewarden-policy-server` (see `{default-policy-server-image}`). This is a
  real error in a step that users follow, not only an example. Fix it
  upstream, for example with an attribute for the image name.
- **Hauler partials in new versions.** `scripts/sync.py` copies only the `en`
  product-specific files to a new component version (`new_versions`). The
  language placeholders `02-hauler.adoc` and `01-requirements.adoc` of the
  next version need
  `partials/product-specific/airgap-hauler-download.adoc` and
  `partials/product-specific/airgap-extra-requirements.adoc` in each language
  module. Without them, the build fails.
- **Air gap pages in the language modules.** The language modules are not
  changed yet. When a sync refreshes the language placeholders
  `02-hauler.adoc` and `01-requirements.adoc` to the new upstream pages, each
  language module needs `partials/product-specific/airgap-hauler-download.adoc`
  and `partials/product-specific/airgap-extra-requirements.adoc`, copies of
  the English files. Without them, the build fails. Run
  `scripts/sync.py copies`, so that the language variables get
  `:hauler-manifest-*:`. The translated `01-requirements.adoc` pages do not
  show the cosign item until they are translated again.

## Content

- **Contribution guide.** The product `contribution-guide-intro.adoc` sends
  contributors to the upstream project. Review the wording and the rest of the
  contribution guide pages for the product build. The `{docs-repo-*}`
  attributes point to the upstream `kubewarden/docs` repository and team.
  Before [kubewarden/docs#960](https://github.com/kubewarden/docs/pull/960),
  the product build pointed to
  `rancher/kubewarden-product-docs` and the `rancher/teams/docs` team.
- **Verifying images.** `admission-controller` `tutorials/verifying-kubewarden.adoc`
  hard codes the `ghcr.io/kubewarden` images and chart. In the product build it
  verifies the community artifacts.
- **Replace hard-coded community values.** The shared pages still hard code
  community values that must be different in the product build: registries,
  Helm charts and `helm repo add` commands, namespaces, URLs and names. The
  table gives approximate counts in the English pages of the latest and dev
  versions, counted on 2026-11-25. AC is Admission Controller, VS is
  Vulnerability Scanner, RTE is Runtime Enforcer, NE is Network Enforcer and
  KW is the SUSE Security landing component, `kw`.

  | Pattern | AC 1.38 | AC 1.40 | VS 0.13 | VS 1.0 | RTE 0.10 | RTE 0.12 | NE 0.3 | NE 0.5 | KW 1.0 |
  |---|---|---|---|---|---|---|---|---|---|
  | `ghcr.io/kubewarden` | 116 | 116 | 9 | 12 | 1 | 13 | 9 | 13 | 0 |
  | `charts.kubewarden.io` | 12 | 12 | 2 | 2 | 0 | 1 | 1 | 1 | 0 |
  | `helm repo add` | 14 | 14 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
  | `kubewarden` namespace | 46 | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
  | `github.com/kubewarden` | 138 | 136 | 19 | 15 | 4 | 15 | 13 | 10 | 1 |
  | `Kubewarden` as a name | 26 | 27 | 1 | 2 | 0 | 2 | 1 | 2 | 0 |

  Many hits are correct community references, for example source code links
  and policy images. Do the work in these steps:

  1. Do one component at a time, in the dev version, starting with
     `admission-controller` 1.40. The promotion carries the changes to later
     versions. Do not change older versions.
  2. For each pass, list every hit and sort it: parameterize, keep as
     community, or decide later. Review the "decide later" group.
  3. Make the changes upstream in `kubewarden/docs`. Use the attributes that
     exist, for example `{admc-namespace}`, `{default-oci-registry}` and
     `{admc-chart-location}`. Add new attributes only when necessary, with a
     community and a product value.
  4. Build both sites and compare.

  The **Verifying images** item above is an example.
- **Personal paths in examples.** Four `admission-controller` tutorials have a
  local path from an author's workstation in their example commands and
  output, for example `-v /home/jhk/projects/suse/tmp/go-kw-demo:/src` and
  `Compiling demo v0.1.0 (/home/jhk/projects/suse/tmp/demo)`. Replace them
  upstream with a neutral path, for example `$PWD` or `/home/user/demo`:
  - `tutorials/writing-policies/go/02-scaffold.adoc`
  - `tutorials/writing-policies/go/10-raw-policies.adoc`
  - `tutorials/writing-policies/rust/03-define-policy-settings.adoc`
  - `tutorials/writing-policies/rust/05-mutation-policy.adoc`

  All versions from 1.28 to 1.40 have them, in English and in the
  translations. Fix the dev version upstream. The translations get the fix
  from the next translation run.
- **Policy Server CLI translations.** The translation process damaged the
  passthrough markup in `admission-controller` `reference/policy-server-cli.adoc`.
  This occurred in all languages, in versions 1.34 to 1.39. Literal `+`
  characters showed in the inline code, for example
  `policy-server [+OPTIONS+]`. The translated pages were fixed by hand,
  because the fix changes only markup. The cause is the old English source
  (1.35 and earlier), which escapes each special character as `++[++`. The
  English pages of 1.36 and later use plain text. If a translation run from
  the old English source occurs again, examine the result for this damage.
- **SUSE Rancher Prime name.** The product partial
  `quick-start-installation.adoc` of `admission-controller` 1.38 and 1.40
  has "SUSE Rancher Prime" as literal text. Revisit it. If more pages use
  the name, add an attribute to the product `globals.adoc`.
- **Umbrella quick start.** The quick starts of the Vulnerability Scanner,
  the Runtime Enforcer and the Network Enforcer link to the SUSE Security
  quick start in `kw` (`pages/product-specific/quick-start.adoc`), which is a
  placeholder. Tell the author of that guide two things:
  - The product Network Enforcer quick start no longer shows the provider
    choice (Istio, Calico or Cilium). The SUSE Security guide must cover it.
  - The xref has no version. It goes to the SUSE Security page of the newest
    release, also from the pages of older releases.

## Build and publishing

- **Sync: schedule.** The `Sync with kubewarden/docs` workflow runs
  `scripts/sync.py` on demand and opens a sync pull request. Add a
  `schedule:` trigger when the on-demand runs work well.
- **Hauler manifest: schedule.** The `Update Hauler manifest` workflow runs
  on demand only. Its `schedule:` trigger is commented out. Enable it when
  the on-demand runs work well.
- **Sync: hardening.** [what-can-go-wrong.md](what-can-go-wrong.md) lists
  how the sync can fail or give a wrong result. It also lists the changes
  that make the sync safer.
- **Build errors in CI.** The sync workflow build report
  (`scripts/build-report.sh`) showed 0 errors for #73 and #75. A local build
  of the #75 branch had 3 errors and 12 warnings. The probable cause is
  `antora … | tee` in the `Makefile`: the pipe hides the exit status of
  Antora. Set `SHELL := bash` and `.SHELLFLAGS := -eo pipefail -c`, and
  upload `tmp/build.log` and `make.log` as workflow artifacts.
- **Versions that upstream renames or deletes.** `scripts/sync.py` does not
  delete a component version that upstream renamed or deleted. Upstream
  renamed `sbom-scanner` 0.14 to 1.0, so `docs/sbom-scanner/version-0.14`
  is a leftover. Delete it, and add a check to `sync.py`.
- **Preview deploy.** `.github/workflows/preview.yml` builds, uploads and
  deploys in one job. One run failed with "Found 0 artifact(s)"
  (actions/deploy-pages#451). If it occurs again, split the job as upstream
  kubewarden/docs#1035 does: a separate `deploy` job with `needs: build`. Do
  not run the full workflow again, because it uploads a second artifact.
- **Mermaid diagrams in the publishing playbook.**
  `@sntke/antora-mermaid-extension` applies `subs` to the wrong value, so
  diagrams with `[mermaid,subs="attributes"]` render as the word "attributes".
  rancher/product-docs-common#102 (block processor) and
  SUSEdoc/dsc-style-bundle#88 (mermaid loader) fix this, and this repository
  uses them. `product-docs-playbook` still uses the sntke extension. Bump its
  submodules, replace the extension with
  `./product-docs-common/extensions/mermaid-block/mermaid-block.js` under
  `asciidoc.extensions`, and remove the package.
- **Publishing playbook.** `product-docs-playbook` builds the published site.
  The switch to this repository is a planned step in
  [next-steps.md](next-steps.md). Before the switch, check these points:
  - The playbook sets `build-type: product@` and the old `kw-build-type`.
    The trailing `@` lets a page override the value. Check that no page
    overrides `build-type`.
  - The playbook indexes with `index_latest_only: true`. This repository uses
    `false`. Decide which value the published site needs.
