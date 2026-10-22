# Follow-ups for the SUSE Security product docs

Open questions and known issues found while building this repository from
the upstream community repository. Remove an item when it is done.

## Values to confirm

- **Admission controller image tags.** In `admission-controller/version-1.39`,
  `{release-tag}` (`v1.38.2`) is the upstream tag. The product file assumes the
  product image tags are the same. `{default-policy-server-image-tag}` uses it
  to build the `dp.apps.rancher.io` image reference. If the product image tags
  have no leading `v`, add a separate image tag attribute.
- **Release tags and chart versions.** The product `variables.adoc` of every
  component dev version copies `{release-tag}` and `{chart-version}` from
  upstream. Confirm that the product versions are the same. The updatecli job
  that bumps them upstream writes only to `community-specific/variables.adoc`.
  `scripts/sync.py` copies the new values to the product files.
- **Network Enforcer chart.** `{network-enforcer-helm-chart}` is a guess,
  `oci://dp.apps.rancher.io/charts/suse-security-network-enforcer`. No page
  uses it at the moment.

## Content

- **Contribution guide.** The product `contribution-guide-intro.adoc` sends
  contributors to the upstream project. Review the wording and the rest of the
  contribution guide pages for the product build. The `{docs-repo-*}`
  attributes point to the upstream `kubewarden/docs` repository and team.
  Before PR 960, the product build pointed to
  `rancher/kubewarden-product-docs` and the `rancher/teams/docs` team.
- **Verifying images.** `admission-controller` `tutorials/verifying-kubewarden.adoc`
  hard codes the `ghcr.io/kubewarden` images and chart. In the product build it
  verifies the community artifacts.
- **Parameterization passes.** The shared pages still hard code community
  values that the product build needs to differ: registries, Helm charts and
  `helm repo add` commands, namespaces, URLs, and names. Approximate counts in
  the English pages of the latest and dev versions:

  | Pattern | AC 1.38 | AC 1.39 | VS 0.13 | VS 0.14 | RTE 0.10 | RTE 0.11 | NE 0.3 | NE 0.4 | KW 1.0 |
  |---|---|---|---|---|---|---|---|---|---|
  | `ghcr.io/kubewarden` | 129 | 119 | 9 | 9 | 1 | 10 | 9 | 9 | 0 |
  | `charts.kubewarden.io` | 12 | 12 | 3 | 3 | 0 | 1 | 2 | 2 | 0 |
  | `helm repo add` | 14 | 14 | 4 | 4 | 2 | 2 | 2 | 2 | 0 |
  | `kubewarden` namespace | 46 | 46 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
  | `github.com/kubewarden` | 137 | 138 | 19 | 19 | 4 | 15 | 13 | 13 | 1 |
  | `Kubewarden` as a name | 27 | 27 | 1 | 1 | 0 | 1 | 1 | 1 | 0 |

  Many hits are correct community references, for example source code links
  and policy images. Approach:

  1. Do one component at a time, in the dev version, starting with
     `admission-controller` 1.39. The promotion carries the changes to later
     versions. Do not change older versions.
  2. For each pass, list every hit and sort it: parameterize, keep as
     community, or decide. Review the "decide" group.
  3. Make the changes upstream in `kubewarden/docs`. Use the attributes that
     exist, for example `{admc-namespace}`, `{default-oci-registry}`, and
     `{admc-chart-location}`. Add new attributes only when necessary, with a
     community and a product value.
  4. Build both sites and compare.

  The **Verifying images** item above and the **Runtime Enforcer quick
  start** item below are examples.
- **Personal paths in examples.** Four `admission-controller` tutorials have a
  local path from an author's workstation in their example commands and
  output, for example `-v /home/jhk/projects/suse/tmp/go-kw-demo:/src` and
  `Compiling demo v0.1.0 (/home/jhk/projects/suse/tmp/demo)`. Replace them
  upstream with a neutral path, for example `$PWD` or `/home/user/demo`:
  - `tutorials/writing-policies/go/02-scaffold.adoc`
  - `tutorials/writing-policies/go/10-raw-policies.adoc`
  - `tutorials/writing-policies/rust/03-define-policy-settings.adoc`
  - `tutorials/writing-policies/rust/05-mutation-policy.adoc`

  All versions from 1.28 to 1.39 have them, in English and in the
  translations. Fix the dev version upstream. The translations get the fix
  from the next translation run.
- **Runtime Enforcer quick start.** The quick start uses
  `helm repo add ... {runtime-enforcer-helm-chart}`. The product chart is an
  `oci://` reference, which `helm repo add` does not accept.

## Build and publishing

- **Sync: schedule.** The `Sync with kubewarden/docs` workflow runs
  `scripts/sync.py` on demand and opens a sync pull request. Add a
  `schedule:` trigger when the on-demand runs work well.
- **Sync: hardening.** [what-can-go-wrong.md](what-can-go-wrong.md) lists
  how the sync can fail or give a wrong result, and the changes that make it
  safer.
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
  When this repository goes live:
  - Replace the `kubewarden-product-docs`, `sbomscanner-product-docs`, and
    `runtime-enforcer-product-docs` sources with one source for this
    repository, with the same start paths as `remote-product-playbook.yml`.
  - It sets `build-type: product@` and the old `kw-build-type`. Check that no
    page overrides `build-type`.
  - It indexes with `index_latest_only: true`. This repository uses `false`.
