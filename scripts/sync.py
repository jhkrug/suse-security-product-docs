#!/usr/bin/env python3
"""Sync this repository with the upstream kubewarden/docs.

  scripts/sync.py plan   [options]   write the plan, change nothing
  scripts/sync.py apply  [options]   make the changes in the working tree
  scripts/sync.py copies             copy the English variables partials to
                                     the language modules

Both compare three trees:

- base: the upstream commit of the last sync, from .upstream-ref
- head: the upstream commit to sync to, by default the tip of main
- local: this repository, HEAD

The rules come from process-docs/PRODUCT-consideration.md and AGENTS.md:

- copy the upstream changes under docs/ and shared/, without
  community-specific/
- keep the product title: and the language nav: entries of antora.yml
- merge files changed upstream and here with git merge-file, or leave them
  for a person when the merge has conflicts
- in the translated component versions, follow the English changes in the
  language modules: add, refresh, move, or remove the English placeholders,
  copy the variables partials, update the language navs, and fix the paths
  of moved pages and images
- keep the language copies of the variables partials the same as the
  English files
- bump release-tag and chart-version in the product variables.adoc
- start the product-specific layer of a new component version from the
  previous version
- list what needs a person: conflicts, product files to write, upstream
  tooling changes, stale translations

apply stages its changes and updates .upstream-ref. It does not commit.
--attention FILE writes the items that need a person as Markdown bullets,
for the top of the sync pull request.

Exit status:
  plan:  0 no upstream changes, 2 upstream changes, 1 error
  apply: 0 applied (or nothing to do), 3 applied with manual follow-up, 1 error
"""

import argparse
import difflib
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

UPSTREAM_URL = "https://github.com/kubewarden/docs.git"
CONTENT_ROOTS = ("docs", "shared")
TOOLING_EXCLUDE = (".agents/", ".claude/", "archived-docs/", "tests/")
# Upstream files outside the content that affect a build like the product
# build. Changes to them need a person; other tooling changes are listed only.
BUILD_FILES = ("package.json", "package-lock.json", "Makefile", ".gitmodules", "docs-common")
BUILD_DIRS = ("ui/", "kw-community-docs-supp-files/")
PLAYBOOKS = ("local-product-playbook.yml", "remote-product-playbook.yml")
# Rename detection threshold. Lower than the git default of 50%, so that more
# pages that move and change are seen as moves, and their translations move.
RENAME_THRESHOLD = "-M40%"
MODULE_RE = re.compile(r"^(docs/[^/]+/[^/]+)/modules/([^/]+)/(.+)$")
VERSION_DIR_RE = re.compile(r"^(docs/[^/]+)/(version-[^/]+)/")
LANG_NAV_RE = re.compile(r"^\s*-\s*modules/(?!en/)[^/]+/nav\.adoc\s*$")
EN_NAV_RE = re.compile(r"^\s*-\s*modules/en/nav\.adoc\s*$")
XREF_RE = re.compile(r"xref:([^\[\s]+)\[")
ATTR_REF_RE = re.compile(r"\{([\w-]+)\}")

# Report sections, in output order: (name, intro, needs a person).
SECTIONS = [
    ("Apply", "Upstream changes to copy.", False),
    ("Merged", "Changed upstream and here. git merge-file merged them without conflicts. Review the result.", False),
    ("Conflicts", "Changed upstream and here, with merge conflicts. The local file is kept. Merge by hand.", True),
    ("Translations", "Language module changes that follow the English changes.", False),
    ("Release tags", "Product variables to bump.", False),
    ("Manual follow-up", "The script cannot do these.", True),
    ("Stale translations", "Translated pages whose English page changes. The translation process updates them.", False),
    ("Product layer", "Upstream changed community-specific files. The product counterparts exist. Check them.", False),
    ("Upstream build changes", "Not copied. They change how upstream builds. Check whether the product build needs the same change.", True),
    ("Upstream tooling to review", "Not copied. Other upstream files outside the content.", False),
    ("Already applied", None, False),
    ("Out-of-date language copies", "Language copies of variables partials that differ from the English file. apply and copies refresh them.", False),
    ("Local differences", "Differences from upstream at head, outside the product layer, the translations, and the product antora.yml lines.", False),
]
COLLAPSED = {"Already applied", "Local differences"}
# Labels of the sections that need a person, for the attention list.
ATTENTION_LABELS = {"Conflicts": "Conflict", "Manual follow-up": "Manual follow-up", "Upstream build changes": "Upstream build change"}


class Error(Exception):
    pass


# Git helpers -------------------------------------------------------------

def git(*args, binary=False, check=True, input=None):
    proc = subprocess.run(["git", *args], capture_output=True, input=input)
    if check and proc.returncode != 0:
        raise Error(f"git {' '.join(args)}: {proc.stderr.decode().strip()}")
    return proc.stdout if binary else proc.stdout.decode()


def rev_parse(rev):
    out = git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}", check=False).strip()
    return out


def tree(rev):
    """Map path -> (mode, blob id) for the content roots of rev."""
    out = git("ls-tree", "-r", "-z", "--full-tree", rev, "--", *CONTENT_ROOTS)
    entries = {}
    for item in out.split("\0"):
        if item:
            meta, path = item.split("\t", 1)
            mode, _, sha = meta.split()
            entries[path] = (mode, sha)
    return entries


def blob(rev, path):
    return git("show", f"{rev}:{path}", binary=True)


def text(rev, path):
    return blob(rev, path).decode()


def merge_file(local, base, other):
    """Three-way merge of byte strings. Return (merged bytes, clean)."""
    with tempfile.TemporaryDirectory() as tmp:
        names = []
        for name, data in (("local", local), ("base", base), ("other", other)):
            p = Path(tmp, name)
            p.write_bytes(data)
            names.append(str(p))
        proc = subprocess.run(["git", "merge-file", "-p", *names], capture_output=True)
        if proc.returncode < 0 or proc.returncode > 127:
            raise Error(f"git merge-file: {proc.stderr.decode().strip()}")
        return proc.stdout, proc.returncode == 0


# Path helpers ------------------------------------------------------------

def is_community(path):
    return "/community-specific/" in path


def is_product(path):
    return "/product-specific/" in path


def module_parts(path):
    """Return (version dir, module, rest) for a path in a module, or None."""
    m = MODULE_RE.match(path)
    return m.groups() if m else None


def to_lang(path, lang):
    vdir, _, rest = module_parts(path)
    return f"{vdir}/modules/{lang}/{rest}"


def is_variables_partial(rest):
    return rest == "partials/variables.adoc" or (rest.startswith("partials/") and rest.endswith("/variables.adoc"))


def version_key(vdir):
    return [int(x) if x.isdigit() else x for x in re.split(r"[.-]", vdir.rsplit("version-", 1)[1])]


def xrefs(nav_text):
    return set(XREF_RE.findall(nav_text))


def attr_renames(before, after):
    """Attribute renames between two versions of a page.

    Only lines that differ in nothing but their attribute references count.
    Return {old: new}, without names that map to more than one new name.
    """
    a, b = before.splitlines(), after.splitlines()
    found = defaultdict(set)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "replace" or i2 - i1 != j2 - j1:
            continue
        for old, new in zip(a[i1:i2], b[j1:j2]):
            if ATTR_REF_RE.sub("{}", old) != ATTR_REF_RE.sub("{}", new):
                continue
            for x, y in zip(ATTR_REF_RE.findall(old), ATTR_REF_RE.findall(new)):
                if x != y:
                    found[x].add(y)
    return {x: ys.pop() for x, ys in found.items() if len(ys) == 1}


def all_attrs(content):
    """Map name -> value for the attribute definitions in content."""
    found = {}
    for line in content.splitlines():
        m = re.match(r"^:([\w-]+):\s*(.*)$", line)
        if m:
            found[m.group(1)] = m.group(2).strip()
    return found


def attrs(content, names):
    found = {}
    for line in content.splitlines():
        m = re.match(r"^:([\w-]+):\s*(.*)$", line)
        if m and m.group(1) in names:
            found[m.group(1)] = m.group(2).strip()
    return found


# antora.yml --------------------------------------------------------------

def normalize_antora(content):
    """antora.yml without the lines the product sync keeps."""
    return "\n".join(
        line for line in content.splitlines()
        if not line.startswith("title:") and not LANG_NAV_RE.match(line)
    )


def product_antora(upstream, local):
    """Upstream antora.yml with the local title: and language nav: lines."""
    local_lines = local.splitlines()
    title = next((l for l in local_lines if l.startswith("title:")), None)
    lang_navs = [l for l in local_lines if LANG_NAV_RE.match(l)]
    out = []
    for line in upstream.splitlines():
        if line.startswith("title:") and title:
            line = title
        if LANG_NAV_RE.match(line):
            continue
        out.append(line)
        if EN_NAV_RE.match(line):
            out.extend(lang_navs)
    return "\n".join(out) + ("\n" if upstream.endswith("\n") else "")


# Plan --------------------------------------------------------------------

class Plan:
    def __init__(self, base, head, local):
        self.base, self.head, self.local = base, head, local
        self.u0, self.u1, self.lt = tree(base), tree(head), tree(local)
        # Version directory -> languages other than en, in the local tree.
        self.langs = defaultdict(set)
        for path in self.lt:
            parts = module_parts(path)
            if parts and parts[1] != "en":
                self.langs[parts[0]].add(parts[1])
        self.sections = defaultdict(list)
        self.added = set()
        self.planned = set()  # files apply creates by copying, for new versions
        self.new_vdirs = {}  # new version directory -> the version it copies from
        self._product_attrs = {}
        # Operations for apply, as (phase, op, args...). Lower phases run first.
        self.ops = []
        self.has_changes = False

    def add(self, section, line):
        self.sections[section].append(line)

    def op(self, phase, *args):
        self.ops.append((phase, *args))

    def local_blob(self, path):
        e = self.lt.get(path)
        return e and e[1]

    def u0_blob(self, path):
        e = self.u0.get(path)
        return e and e[1]

    def u1_blob(self, path):
        e = self.u1.get(path)
        return e and e[1]

    def changes(self):
        out = git("diff", "--name-status", "-z", RENAME_THRESHOLD, self.base, self.head, "--", *CONTENT_ROOTS)
        fields = out.split("\0")
        i = 0
        while i < len(fields) and fields[i]:
            status = fields[i]
            if status[0] in "RC":
                yield status[0], fields[i + 1], fields[i + 2]
                i += 3
            else:
                yield status[0], None, fields[i + 1]
                i += 2

    # Content changes -----------------------------------------------------

    def classify(self, status, old, path):
        """Plan one upstream change. Return what happens to the local file."""
        local, u0, u1 = self.local_blob(path), self.u0_blob(path), self.u1_blob(path)

        if status == "R":
            lold = self.local_blob(old)
            if local == u1 and lold is None:
                self.add("Already applied", f"`{old}` -> `{path}` (moved)")
                return "already"
            if lold == self.u0_blob(old) and local is None:
                self.op(1, "mv", old, path)
                if self.u0_blob(old) != u1:
                    self.op(2, "checkout", path)
                    self.add("Apply", f"move and update `{old}` -> `{path}`")
                else:
                    self.add("Apply", f"move `{old}` -> `{path}`")
                self.translations_move(old, path, changed=self.u0_blob(old) != u1, old_local=lold)
                return "moved"
            self.add("Conflicts", f"`{old}` -> `{path}`: moved upstream, changed or moved here")
            return "conflict"

        if status == "A":
            if local is None:
                self.op(2, "checkout", path)
                self.add("Apply", f"add `{path}`")
                self.translations_change(path, None)
                return "added"
            if local == u1:
                self.add("Already applied", f"`{path}` (added)")
                return "already"
            self.add("Conflicts", f"`{path}`: added upstream, exists here with other content")
            return "conflict"

        if status == "D":
            if local is None:
                self.add("Already applied", f"`{path}` (deleted)")
                return "already"
            if local == u0:
                self.op(2, "rm", path)
                self.add("Apply", f"delete `{path}`")
                self.translations_delete(path)
                return "deleted"
            self.add("Conflicts", f"`{path}`: deleted upstream, changed here")
            return "conflict"

        # M, T
        if local == u1:
            self.add("Already applied", f"`{path}`")
            return "already"
        if local == u0:
            self.op(2, "checkout", path)
            self.add("Apply", f"update `{path}`")
            self.translations_change(path, local)
            return "updated"
        if local is None:
            self.add("Conflicts", f"`{path}`: changed upstream, missing here (moved or deleted?)")
            return "conflict"
        if path.endswith("/antora.yml"):
            ltext, t0, t1 = text(self.local, path), text(self.base, path), text(self.head, path)
            if normalize_antora(ltext) == normalize_antora(t1):
                self.add("Already applied", f"`{path}` (apart from the product lines)")
                return "already"
            if normalize_antora(ltext) == normalize_antora(t0):
                self.op(2, "write", path, product_antora(t1, ltext).encode())
                self.add("Apply", f"update `{path}`, keep the product `title:` and language `nav:` entries")
                return "updated"
        merged, clean = merge_file(blob(self.local, path), blob(self.base, path), blob(self.head, path))
        if clean:
            self.op(2, "write", path, merged)
            self.add("Merged", f"`{path}`")
            self.translations_change(path, local, merged=merged)
            return "updated"
        self.add("Conflicts", f"`{path}`")
        return "conflict"

    # Translations --------------------------------------------------------

    def lang_targets(self, path):
        """Return (rest, languages) for an English module file in a translated version."""
        parts = module_parts(path)
        if not parts or parts[1] != "en":
            return None, ()
        vdir, _, rest = parts
        return rest, sorted(self.langs.get(vdir, ()))

    def translations_change(self, path, old_local, merged=None):
        """The English file at path is added or updated."""
        rest, langs = self.lang_targets(path)
        if not langs:
            return
        names = ", ".join(langs)
        if rest == "nav.adoc":
            before = xrefs(text(self.local, path)) if old_local else set()
            after_text = merged.decode() if merged is not None else text(self.head, path)
            self.nav_ops(path, langs, before, after_text)
            return
        if is_variables_partial(rest):
            for lang in langs:
                self.op(3, "copy", path, to_lang(path, lang))
            self.add("Translations", f"copy `{path}` to the {names} modules")
            return
        if not (rest.startswith("pages/") or rest.startswith("partials/")):
            return
        stale = []
        for lang in langs:
            lpath = to_lang(path, lang)
            lblob = self.local_blob(lpath)
            if lblob is None:
                self.op(3, "copy", path, lpath)
                self.add("Translations", f"add placeholder `{lpath}`")
            elif lblob == old_local:
                self.op(3, "copy", path, lpath)
                self.add("Translations", f"refresh placeholder `{lpath}`")
            else:
                stale.append(lang)
        if stale:
            self.add("Stale translations", f"`{path}`: translated in {', '.join(stale)}")
            if old_local:
                after = merged.decode() if merged is not None else text(self.head, path)
                renames = attr_renames(text(self.local, path), after)
                if renames:
                    for lang in stale:
                        self.op(4, "attr_rename", to_lang(path, lang), renames)
                    pairs = ", ".join(f"`{x}` -> `{y}`" for x, y in sorted(renames.items()))
                    self.add("Translations", f"rename attributes in the {', '.join(stale)} copies of `{path}`: {pairs}")

    def translations_delete(self, path):
        rest, langs = self.lang_targets(path)
        if not langs or not (rest.startswith("pages/") or rest.startswith("partials/")):
            return
        old_local = self.local_blob(path)
        vdir = module_parts(path)[0]
        name = path.rsplit("/", 1)[1]
        candidates = [p for p in self.added if p.startswith(f"{vdir}/modules/en/") and p.endswith("/" + name)]
        kept = []
        for lang in langs:
            lpath = to_lang(path, lang)
            lblob = self.local_blob(lpath)
            if lblob is None:
                continue
            if lblob == old_local:
                self.op(3, "rm", lpath)
                self.add("Translations", f"delete placeholder `{lpath}`")
            else:
                kept.append(lang)
        if kept:
            hint = f" If it moved, move the translations to the new path, for example `{candidates[0]}`." if candidates else " If it moved, move the translations to the new path."
            self.add("Manual follow-up", f"`{path}` is deleted upstream, but it is translated in {', '.join(kept)}. The translations are kept: delete them, or keep them for a moved page.{hint}")

    def translations_move(self, old, new, changed, old_local):
        rest, langs = self.lang_targets(old)
        if not langs:
            return
        new_rest = module_parts(new)[2]
        kind = rest.split("/", 1)[0]
        old_rel, new_rel = rest.split("/", 1)[1] if "/" in rest else rest, new_rest.split("/", 1)[1] if "/" in new_rest else new_rest
        stale = []
        for lang in langs:
            lold, lnew = to_lang(old, lang), to_lang(new, lang)
            vdir = module_parts(old)[0]
            moddir = f"{vdir}/modules/{lang}"
            if kind in ("pages", "partials") and lold in self.lt:
                self.op(1, "mv", lold, lnew)
                self.add("Translations", f"move `{lold}` -> `{lnew}`")
                if changed:
                    if self.local_blob(lold) == old_local:
                        self.op(3, "copy", new, lnew)
                    else:
                        stale.append(lang)
            if kind in ("pages", "partials", "images"):
                self.op(4, "rewrite", moddir, kind, old_rel, new_rel)
        if kind in ("pages", "partials", "images"):
            self.add("Translations", f"replace `{old_rel}` with `{new_rel}` in the {', '.join(langs)} {kind} references")
        if stale:
            self.add("Stale translations", f"`{new}`: translated in {', '.join(stale)}")

    def nav_ops(self, path, langs, before, after_text):
        after_lines = after_text.splitlines()
        after = xrefs(after_text)
        for x in sorted(before - after):
            for lang in langs:
                self.op(4, "nav_remove", to_lang(path, lang), x)
            self.add("Translations", f"remove `{x}` from the {', '.join(langs)} navs")
        for x in sorted(after - before):
            idx = next(i for i, l in enumerate(after_lines) if f"xref:{x}[" in l)
            prev = next((XREF_RE.search(l).group(1) for l in reversed(after_lines[:idx]) if XREF_RE.search(l)), None)
            nxt = next((XREF_RE.search(l).group(1) for l in after_lines[idx + 1:] if XREF_RE.search(l)), None)
            for lang in langs:
                self.op(4, "nav_add", to_lang(path, lang), after_lines[idx], prev, nxt)
            self.add("Translations", f"add `{x}` to the {', '.join(langs)} navs")

    # Release tags --------------------------------------------------------

    def release_bumps(self):
        names = ("release-tag", "chart-version")
        out = git("diff", "--name-only", "-z", self.base, self.head, "--", *CONTENT_ROOTS)
        for path in filter(None, out.split("\0")):
            if not (is_community(path) and path.endswith("/variables.adoc") and path in self.u1):
                continue
            old = attrs(text(self.base, path), names) if path in self.u0 else {}
            new = attrs(text(self.head, path), names)
            product = path.replace("/community-specific/", "/product-specific/")
            if product in self.planned:
                src = next(op[2] for op in self.ops if op[1] == "copy" and op[3] == product)
                current = attrs(text(self.local, src), names)
                for name in names:
                    if name in new and name in current and current[name] != new[name]:
                        self.op(4, "setattr", product, name, new[name])
                        self.add("Release tags", f"`{product}` (new version): set `{name}` from `{current[name]}` to `{new[name]}`")
                continue
            current = attrs(text(self.local, product), names) if product in self.lt else {}
            for name in names:
                if name not in new or old.get(name) == new[name]:
                    continue
                if product not in self.lt:
                    self.add("Manual follow-up", f"`{product}` is missing; upstream sets `{name}` to `{new[name]}`")
                elif current.get(name) == new[name]:
                    self.add("Already applied", f"`{product}` `{name}` is `{new[name]}`")
                elif name not in current:
                    self.add("Manual follow-up", f"`{product}` has no `{name}`; upstream sets it to `{new[name]}`")
                else:
                    self.op(4, "setattr", product, name, new[name])
                    note = "" if current[name] == old.get(name) else f" (upstream was `{old.get(name)}`)"
                    self.add("Release tags", f"`{product}`: set `{name}` from `{current[name]}` to `{new[name]}`{note}")

    # Attributes in community-specific files ------------------------------

    def product_attrs(self, path):
        """Attribute names the product build defines for the version of path, and where.

        Looks in the product-specific files and the shared partials, in English.
        The shared partials come from upstream, so it reads them as they are
        after the sync.
        """
        m = VERSION_DIR_RE.match(path)
        scopes = ("shared/",) + ((m.group(0),) if m else ())
        key = scopes[-1]
        if key not in self._product_attrs:
            found = {}
            for p in sorted(set(self.lt) | set(self.u1)):
                parts = module_parts(p)
                if not (p.startswith(scopes) and p.endswith(".adoc") and (parts is None or parts[1] == "en")):
                    continue
                if is_product(p) and p in self.lt:
                    content = text(self.local, p)
                elif "/partials/" in p and not is_community(p) and not is_product(p) and p in self.u1:
                    content = text(self.head, p)
                else:
                    continue
                for name in all_attrs(content):
                    found.setdefault(name, p)
            self._product_attrs[key] = found
        return self._product_attrs[key]

    def attribute_changes(self, status, old, path):
        if status == "D" or not path.endswith(".adoc"):
            return
        before_path = old if status == "R" else path
        before = all_attrs(text(self.base, before_path)) if before_path in self.u0 else {}
        after = all_attrs(text(self.head, path))
        product = path.replace("/community-specific/", "/product-specific/")
        defined = self.product_attrs(path)
        m = VERSION_DIR_RE.match(path)
        vdir = m.group(0).rstrip("/") if m else None
        if vdir in self.new_vdirs:
            # A new version: compare with the version it copies from.
            src_path = self.new_vdirs[vdir] + path[len(vdir):]
            before = all_attrs(text(self.head, src_path)) if src_path in self.u1 else {}
            defined = self.product_attrs(src_path)
        for name in sorted(set(after) - set(before)):
            if name in ("release-tag", "chart-version") or name in defined:
                continue
            self.add("Manual follow-up", f"upstream adds `:{name}:` to `{path}` (value `{after[name]}`): no product file defines it. Add it, for example to `{product}`")
        for name in sorted(set(before) - set(after)):
            if name in defined:
                self.add("Product layer", f"upstream removes `:{name}:` from `{path}`; `{defined[name]}` still defines it. Remove it if nothing uses it")

    # Product layer -------------------------------------------------------

    def product_layer(self, status, old, path):
        product = path.replace("/community-specific/", "/product-specific/")
        if product in self.planned:
            return  # a new version: the copied product layer is reviewed as a whole
        exists = product in self.lt
        if status == "D":
            if exists:
                self.add("Product layer", f"`{path}` deleted upstream: remove `{product}` if nothing includes it")
        elif status == "R":
            oldp = old.replace("/community-specific/", "/product-specific/")
            if oldp in self.lt and not exists:
                self.add("Manual follow-up", f"`{old}` moved upstream to `{path}`: move `{oldp}` too")
            elif not exists:
                self.add("Manual follow-up", f"`{path}` moved upstream: create `{product}`")
        elif not exists:
            self.add("Manual follow-up", f"`{path}` {'added' if status == 'A' else 'changed'} upstream: create `{product}`")
        elif not (status == "M" and path.endswith("/variables.adoc")):
            self.add("Product layer", f"`{path}` {'added' if status == 'A' else 'changed'} upstream: check `{product}`")

    # New component versions ----------------------------------------------

    def new_versions(self):
        def vdirs(entries):
            return {m.group(1) + "/" + m.group(2) for p in entries if (m := VERSION_DIR_RE.match(p))}
        local = vdirs(self.lt)
        for vdir in sorted(vdirs(self.u1) - local):
            comp = vdir.rsplit("/", 1)[0]
            older = sorted((v for v in local if v.startswith(comp + "/") and version_key(v) < version_key(vdir)), key=version_key)
            if not older:
                self.new_component(comp, vdir)
                continue
            src = older[-1]
            self.new_vdirs[vdir] = src
            files = sorted(p for p in self.lt if p.startswith(src + "/") and is_product(p) and module_parts(p) and module_parts(p)[1] == "en")
            for p in files:
                self.op(3, "copy", p, vdir + p[len(src):])
                self.planned.add(vdir + p[len(src):])
            self.add("Manual follow-up", f"`{vdir}` is new: its product-specific layer is copied from `{src}` ({len(files)} files). Review the values")
            self.product_title(vdir, src)

    def product_title(self, vdir, src):
        """Give a new component version the product title of the version before it."""
        path, src_path = f"{vdir}/antora.yml", f"{src}/antora.yml"
        if path not in self.u1 or src_path not in self.lt:
            return
        title = next((l for l in text(self.local, src_path).splitlines() if l.startswith("title:")), None)
        upstream = text(self.head, path)
        if not title or title in upstream.splitlines():
            return
        content = "\n".join(title if l.startswith("title:") else l for l in upstream.splitlines())
        self.op(3, "write", path, (content + ("\n" if upstream.endswith("\n") else "")).encode())
        self.add("Apply", f"set the product `{title}` in `{path}`, as in `{src_path}`")

    def new_component(self, comp, vdir):
        self.add("Manual follow-up", f"`{vdir}` is in a new component, `{comp}`: create its product-specific layer, and decide its product `title:`")
        pattern = f"{comp}/version-*"
        for playbook in PLAYBOOKS:
            if playbook in git("ls-tree", "--name-only", self.local).split() and pattern not in text(self.local, playbook):
                self.add("Manual follow-up", f"`{playbook}` does not build `{pattern}`: add it to `start_paths`, and to `product-docs-playbook`")

    # Tooling -------------------------------------------------------------

    def tooling(self):
        out = git("diff", "--name-status", self.base, self.head, "--", ".", *(f":!{r}" for r in CONTENT_ROOTS))
        for line in out.splitlines():
            status, path = line.split("\t", 1)
            if path.startswith(TOOLING_EXCLUDE):
                continue
            if path == "docs-common":
                self.add("Upstream build changes", self.docs_common())
            elif path in BUILD_FILES or path.startswith(BUILD_DIRS) or path.endswith("playbook.yml"):
                self.add("Upstream build changes", f"{status} `{path}`")
            else:
                self.add("Upstream tooling to review", f"{status} `{path}`")

    def docs_common(self):
        """Compare the upstream docs-common bump with product-docs-common."""
        def commit(rev, path):
            out = git("ls-tree", rev, "--", path).split()
            return out[2][:10] if len(out) > 2 else "none"
        old, new, ours = commit(self.base, "docs-common"), commit(self.head, "docs-common"), commit(self.local, "product-docs-common")
        note = "the same" if ours == new else f"`{ours}`; consider the same bump"
        return f"`docs-common` (rancher/product-docs-common) moves from `{old}` to `{new}`. `product-docs-common` here is {note}"

    # Checks on the local tree --------------------------------------------

    def language_copies(self):
        for path in sorted(self.lt):
            parts = module_parts(path)
            if not parts or parts[1] == "en" or not is_variables_partial(parts[2]):
                continue
            en = f"{parts[0]}/modules/en/{parts[2]}"
            if self.local_blob(en) != self.local_blob(path):
                self.add("Out-of-date language copies", f"`{path}` differs from `{en}`")

    def local_differences(self):
        """Files that will still differ from upstream head after the sync."""
        touched = {a for op in self.ops for a in op[2:4] if isinstance(a, str) and a.startswith(CONTENT_ROOTS)}
        conflicts = {line.split("`")[1] for line in self.sections.get("Conflicts", [])}
        groups = defaultdict(list)
        for path in sorted(set(self.lt) | set(self.u1)):
            if is_product(path) or is_community(path) or path in touched or path in conflicts:
                continue
            parts = module_parts(path)
            if parts and parts[1] != "en":
                continue
            local, u1 = self.local_blob(path), self.u1_blob(path)
            if local == u1:
                continue
            if path.endswith("/antora.yml") and local and u1 and normalize_antora(text(self.local, path)) == normalize_antora(text(self.head, path)):
                continue
            kind = "only here" if u1 is None else "missing here" if local is None else "changed here"
            m = VERSION_DIR_RE.match(path)
            groups[m.group(0).rstrip("/") if m else path.split("/", 1)[0]].append(f"{kind}: `{path}`")
        for group, items in groups.items():
            self.add("Local differences", (group, items))

    # Build ---------------------------------------------------------------

    def build(self):
        changes = list(self.changes())
        self.added = {path for status, _, path in changes if status == "A"}
        self.new_versions()
        for status, old, path in changes:
            if is_community(path) and (old is None or is_community(old)):
                self.has_changes = True
                self.product_layer(status, old, path)
                self.attribute_changes(status, old, path)
                continue
            self.has_changes = True
            self.classify(status, old, path)
        self.release_bumps()
        self.tooling()
        self.language_copies()
        self.local_differences()
        return self

    def needs_person(self):
        return any(self.sections.get(name) for name, _, manual in SECTIONS if manual)

    def attention(self):
        """One Markdown bullet for each item that needs a person."""
        return [
            f"- **{ATTENTION_LABELS.get(name, name)}:** {item}"
            for name, _, manual in SECTIONS if manual
            for item in self.sections.get(name, [])
        ]

    def branch(self):
        """Branch name for the sync, after the upstream head commit."""
        return f"sync/kubewarden-{self.head[:7]}"

    def render(self, title):
        short = lambda sha: sha[:10]
        log = git("log", "--format=- %h %s", f"{self.base}..{self.head}").strip()
        lines = [
            f"# {title}",
            "",
            f"- Upstream base (`.upstream-ref`): `{short(self.base)}`",
            f"- Upstream head: `{short(self.head)}`",
            f"- Local: `{short(self.local)}`",
        ]
        if self.has_changes:
            lines.append(f"- Branch: `{self.branch()}`")
        lines.append("")
        lines += ["## Upstream commits", "", log, ""] if log else ["No upstream changes.", ""]
        for name, intro, _ in SECTIONS:
            items = self.sections.get(name)
            if not items:
                continue
            lines += [f"## {name}", ""]
            if intro:
                lines += [intro, ""]
            if name == "Local differences":
                for group, entries in items:
                    lines += [f"<details><summary><code>{group}</code>: {len(entries)} files</summary>", ""]
                    lines += [f"- {e}" for e in entries] + ["", "</details>", ""]
            elif name in COLLAPSED:
                lines += [f"<details><summary>{len(items)} files</summary>", ""]
                lines += [f"- {item}" for item in items] + ["", "</details>", ""]
            else:
                lines += [f"- {item}" for item in items] + [""]
        return "\n".join(lines)


# Apply -------------------------------------------------------------------

def rewrite_refs(moddir, kind, old_rel, new_rel):
    """Replace references to a moved page, partial, or image in a language module."""
    prefix = {"pages": r"xref:", "partials": r"partial\$", "images": r"image::?"}[kind]
    pattern = re.compile(rf"({prefix}){re.escape(old_rel)}(?=[\[#\s])")
    for path in sorted(Path(moddir).rglob("*.adoc")):
        if path.is_symlink():
            continue
        content = path.read_text()
        new = pattern.sub(lambda m: m.group(1) + new_rel, content)
        if new != content:
            path.write_text(new)


def nav_remove(nav, target):
    p = Path(nav)
    if not p.exists():
        return True
    lines = p.read_text().splitlines(keepends=True)
    kept = [l for l in lines if f"xref:{target}[" not in l]
    p.write_text("".join(kept))
    return True


def nav_add(nav, line, prev, nxt):
    p = Path(nav)
    if not p.exists():
        return False
    target = XREF_RE.search(line).group(1)
    lines = p.read_text().splitlines(keepends=True)
    if any(f"xref:{target}[" in l for l in lines):
        return True
    for anchor, offset in ((prev, 1), (nxt, 0)):
        if anchor:
            idx = next((i for i, l in enumerate(lines) if f"xref:{anchor}[" in l), None)
            if idx is not None:
                lines.insert(idx + offset, line + "\n")
                p.write_text("".join(lines))
                return True
    return False


def attr_rename(path, renames):
    p = Path(path)
    content = p.read_text()
    p.write_text(ATTR_REF_RE.sub(lambda m: "{" + renames.get(m.group(1), m.group(1)) + "}", content))


def set_attr(path, name, value):
    p = Path(path)
    content = p.read_text()
    p.write_text(re.sub(rf"^:{re.escape(name)}:.*$", f":{name}: {value}", content, count=1, flags=re.M))


def copy_variables():
    """Make the language copies of the variables partials match English."""
    count = 0
    for lpath in sorted(Path("docs").glob("*/*/modules/*/partials/**/variables.adoc")):
        vdir, lang, rest = module_parts(lpath.as_posix())
        en = Path(vdir, "modules", "en", rest)
        if lang != "en" and en.exists() and en.read_bytes() != lpath.read_bytes():
            lpath.write_bytes(en.read_bytes())
            count += 1
    return count


def apply(plan, root):
    os.chdir(root)
    head = plan.head
    for op in sorted(plan.ops, key=lambda o: o[0]):
        kind, args = op[1], op[2:]
        if kind == "mv":
            src, dst = args
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            git("mv", src, dst)
        elif kind == "checkout":
            git("checkout", head, "--", args[0])
        elif kind == "rm":
            if Path(args[0]).exists() or Path(args[0]).is_symlink():
                git("rm", "-q", "--", args[0])
        elif kind == "write":
            path, data = args
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(data)
        elif kind == "copy":
            src, dst = args
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            Path(dst).write_bytes(Path(src).read_bytes())
        elif kind == "rewrite":
            rewrite_refs(*args)
        elif kind == "nav_remove":
            nav_remove(*args)
        elif kind == "nav_add":
            if not nav_add(*args):
                plan.add("Manual follow-up", f"add `{args[1].strip()}` to `{args[0]}`: no anchor found")
        elif kind == "attr_rename":
            attr_rename(*args)
        elif kind == "setattr":
            set_attr(*args)
        else:
            raise Error(f"unknown operation {kind}")
    copied = copy_variables()
    if copied:
        plan.add("Translations", f"refresh {copied} language copies of the variables partials")
    Path(".upstream-ref").write_text(head + "\n")
    git("add", "-A", "--", *CONTENT_ROOTS, ".upstream-ref")


# Main --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("command", choices=("plan", "apply", "copies"))
    parser.add_argument("--base", help="upstream commit of the last sync (default: .upstream-ref)")
    parser.add_argument("--head", default="main", help="upstream ref or commit to sync to (default: main)")
    parser.add_argument("--local", default="HEAD", help="local revision to compare (plan only, default: HEAD)")
    parser.add_argument("--upstream-url", default=UPSTREAM_URL, help=f"upstream repository (default: {UPSTREAM_URL})")
    parser.add_argument("--no-fetch", action="store_true", help="use objects already in the repository")
    parser.add_argument("--output", type=Path, help="write the report to this file instead of stdout")
    parser.add_argument("--attention", type=Path, help="write the items that need a person to this file, one Markdown bullet each")
    args = parser.parse_args()

    try:
        root = Path(git("rev-parse", "--show-toplevel").strip())
        if args.command == "copies":
            os.chdir(root)
            print(f"sync: refreshed {copy_variables()} language copies")
            return 0
        if args.command == "apply":
            if args.local != "HEAD":
                raise Error("apply works on HEAD only")
            if git("status", "--porcelain", "--untracked-files=no").strip():
                raise Error("the working tree has uncommitted changes")
        base = args.base or (root / ".upstream-ref").read_text().strip()
        head = args.head
        if not args.no_fetch:
            ref = "main" if re.fullmatch(r"[0-9a-f]{7,40}", head) else head
            git("fetch", "--quiet", "--no-tags", args.upstream_url, ref)
            if ref == head:
                head = "FETCH_HEAD"
        base, head, local = rev_parse(base), rev_parse(head), rev_parse(args.local)
        if not base or not head or not local:
            raise Error("cannot resolve the base, head, or local commit (try without --no-fetch)")
        if git("merge-base", base, head).strip() != base:
            raise Error(f"base {base[:10]} is not an ancestor of head {head[:10]}")
        plan = Plan(base, head, local).build()
        if args.command == "apply" and plan.has_changes:
            apply(plan, root)
            report = plan.render("Upstream sync")
        else:
            report = plan.render("Upstream sync plan")
    except (Error, OSError) as exc:
        print(f"sync: {exc}", file=sys.stderr)
        return 1

    if args.attention:
        items = plan.attention()
        args.attention.write_text("".join(f"{item}\n" for item in items))
    if args.output:
        args.output.write_text(report + "\n")
    else:
        print(report)
    if args.command == "plan":
        return 2 if plan.has_changes else 0
    return 3 if plan.needs_person() else 0


if __name__ == "__main__":
    sys.exit(main())
