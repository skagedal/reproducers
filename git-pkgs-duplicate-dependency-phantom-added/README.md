# git-pkgs: a dependency listed twice in one manifest shows up as added on a clean tree

**Status: reproduced minimally against git-pkgs 0.21.0, not yet filed.**

A crate listed under both `[dependencies]` and `[dev-dependencies]` in the
same `Cargo.toml` is a normal thing to write. git-pkgs stores it as one row,
the dev-dependency, and loses the runtime one. Parsing the working tree keeps
both, so `git pkgs diff` with nothing changed reports:

```
Added:
  + anyhow 1 (Cargo.toml)
```

It happens for npm too, with a package in both `dependencies` and
`devDependencies`, so it is not the Cargo parser: whatever writes the index
keys a dependency on manifest and name, and the second record overwrites the
first.

Proposed upstream issue text is at the bottom: [Issue draft](#issue-draft).

## How I hit this

The weekly dependency update in
[skagedal-tools](https://github.com/skagedal/skagedal-tools) puts the output
of `git pkgs diff` in its pull request. The first one listed five crates as
added under `Added:` while the diffstat showed that no `Cargo.toml` had
changed. Each of the five is declared twice in its crate's manifest, as a
dependency and a dev-dependency, mostly with `.workspace = true`. Workspace
inheritance makes no difference; the duplicate is enough.

The workaround there is to keep only lockfile entries and GitHub Actions
pins, which an update is all that moves anyway. It hides the symptom, not the
lost row.

## Reproducing

```sh
cd verify
./reproduce.sh
```

Exit 0 means the bug is still present, 1 means it looks fixed, 2 means the
setup is wrong (no `git-pkgs`, `git` or `jq` on PATH).

It needs no network. Everything happens in a throwaway git repository built
from `verify/fixture`, which is a single `Cargo.toml`.

## Issue draft

```markdown
Title: Dependency in both runtime and dev sections of one manifest is stored once, and `diff` reports it as added on a clean tree

## What happens

A `Cargo.toml` that lists the same crate as a dependency and a dev-dependency:

    [dependencies]
    anyhow = "1"

    [dev-dependencies]
    anyhow = "1"

After committing it and running `git pkgs init`, with a clean working tree:

    $ git pkgs list -f json | jq -c '.[] | {name, dependency_type}'
    {"name":"anyhow","dependency_type":"development"}

    $ git pkgs diff
    Added:
      + anyhow 1 (Cargo.toml)

    $ git pkgs diff -f json
    {"added":[{"name":"anyhow","ecosystem":"cargo","manifest_path":"Cargo.toml","manifest_kind":"manifest","dependency_type":"runtime","to_requirement":"1"}]}

The index holds one row, the development one. The working tree parses to two,
so the runtime one is reported as added, on every run, with nothing changed.

The same happens with npm, for a package in both `dependencies` and
`devDependencies` of one `package.json`, so it looks like the index keys a
dependency on manifest and name and the second record overwrites the first.

## Expected

`git pkgs diff` on a clean tree reports no changes, and `git pkgs list` has
both rows, one runtime and one development.

## Why it matters

Listing a crate in both sections is common: a library used at runtime and
again with different features in tests, or a workspace dependency inherited
in both places. In a real workspace I get one phantom addition per such crate
in every diff, which makes `diff` output unusable as-is for summarising an
update.

## Reproducer

https://github.com/skagedal/reproducers/tree/main/git-pkgs-duplicate-dependency-phantom-added

`verify/reproduce.sh` builds a throwaway repository from a single
`Cargo.toml`, prints what git-pkgs recorded and what `diff` reports. No
network.

## Version

git-pkgs 0.21.0
```
