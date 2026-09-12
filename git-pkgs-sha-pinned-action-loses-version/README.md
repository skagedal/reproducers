# git-pkgs: a SHA-pinned GitHub Action loses its version comment

**Status: reproduced minimally against git-pkgs 0.20.0, not yet filed.**

git-pkgs records whatever follows `@` in a `uses:` line. For a tag that is
`v6`, which is also what a human wrote. For an action pinned to a commit SHA
it is the 40-character hash, and the version comment on the same line is
dropped on the floor:

```yaml
- uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6.1.0
```

Nothing downstream ever sees `v6.1.0`. Not the database, not
`git pkgs list -f json`, not `git pkgs diff`, not the purl. So an update from
v6.1.0 to v7.0.1 arrives as two opaque hashes, and no consumer can tell a
major bump from a patch.

The awkward part is that pinning to a SHA is the recommended supply-chain
practice, and every tool that does it ([pinact][pinact], Dependabot, Renovate)
writes the version in a trailing comment precisely because a bare hash tells a
reader nothing. The way of writing a workflow that security guidance asks for
is the one git-pkgs can say the least about.

Proposed upstream issue text is at the bottom: [Issue draft](#issue-draft).

[pinact]: https://github.com/suzuki-shunsuke/pinact

## How I hit this

After putting [pinact](https://github.com/suzuki-shunsuke/pinact) over my
repositories, `git pkgs diff` started listing every action bump as a change
between two hashes. My own formatter over `git pkgs diff --format=json` sorts
changes into major and minor, could not parse either hash as a version, and
filed them all under minor — including an `actions/checkout` v6 to v7 bump.
That formatter now has a third bucket for changes it cannot classify, which is
honest, but the underlying information is still missing.

## Reproducing

```sh
cd verify
./reproduce.sh
```

Exit 0 means the bug is still present, 1 means it looks fixed, 2 means the
setup is wrong (no `git-pkgs`, `git` or `jq` on PATH).

It needs no network and no credentials. Everything happens in a throwaway git
repository built from `verify/fixture`, which ships a committed `Cargo.lock`
so nothing has to resolve anything. git-pkgs only reads files off disk.

## What the fixture compares

The fixture is four dependency records chosen to sit next to each other:

| Written as | `requirement` | `purl` |
| --- | --- | --- |
| `Cargo.toml`, `anyhow = "1"` | `1` | `pkg:cargo/anyhow` |
| `Cargo.lock`, resolved | `1.0.104` | `pkg:cargo/anyhow@1.0.104?repository_url=…` |
| `uses: actions/checkout@v6` | `v6` | `pkg:githubactions/actions/checkout` |
| `uses: actions/checkout@d23441a4… # v6.1.0` | `d23441a48e516b6c34aea4fa41551a30e30af803` | `pkg:githubactions/actions/checkout` |

The cargo pair shows git-pkgs already models the distinction properly. A
declared range gets a version-less purl, which is right, because a range is
not a version. A resolved lockfile entry gets the version in the purl.

A SHA-pinned action carries both halves on one line: the SHA is the resolution
and the comment is the declaration. git-pkgs keeps the resolution and discards
the declaration, which is the half a person can read.

## Is this a purl bug?

No. Three reasons, in order of how conclusive they are:

1. git-pkgs emits `pkg:cargo/anyhow@1.0.104` from the same code, so whatever
   purl library it uses plainly accepts a version. A version is an optional
   component the producer supplies.
2. The version is already gone before any purl is constructed. It is lost in
   the workflow parser, at the point the `uses:` line is split on `@`.
3. purl is a serialization format with no opinion about where a version comes
   from. It cannot know that a YAML comment two characters to the right of a
   hash is the version of that hash.

One genuinely purl-adjacent thing did turn up, and it is a separate question
from this bug: `githubactions` is not a type defined in
[purl-spec](https://github.com/package-url/purl-spec). Its `types/` directory
has definitions for `github`, `cargo`, `npm` and some forty others, and no
`githubactions` among them. Worth raising on its own if at all; it has no
bearing on the dropped comment.

## Issue draft

```markdown
Title: GitHub Actions: keep the version comment next to a SHA-pinned `uses:`

## What happens now

git-pkgs records whatever follows `@` in a `uses:` line. For a tag that is
`v6`. For an action pinned to a commit SHA it is the 40-character hash, and
the version comment on the same line is dropped.

    - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6.1.0

`git pkgs list -f json`:

    {
      "name": "actions/checkout",
      "ecosystem": "github-actions",
      "purl": "pkg:githubactions/actions/checkout",
      "requirement": "d23441a48e516b6c34aea4fa41551a30e30af803"
    }

Bumping that pin to v7.0.1 and running `git pkgs diff`:

    Modified:
      ~ actions/checkout d23441a48e51… -> 3d3c42e5aac5… (.github/workflows/ci.yml)

A major bump, indistinguishable from a patch.

## Why it matters

Pinning actions to a commit SHA is the recommended supply-chain practice, and
every tool that does it (pinact, Dependabot, Renovate) writes the version in a
trailing comment, precisely because a bare hash tells a reader nothing. After
pinning, consumers of git-pkgs data lose the version entirely: diffs cannot be
classified, and the purl has no version component.

The comparison that makes this concrete is cargo, in the same repository:

| Written as | `requirement` | `purl` |
| --- | --- | --- |
| `Cargo.toml`, `anyhow = "1"` | `1` | `pkg:cargo/anyhow` |
| `Cargo.lock`, resolved | `1.0.104` | `pkg:cargo/anyhow@1.0.104?repository_url=…` |
| `uses: actions/checkout@v6` | `v6` | `pkg:githubactions/actions/checkout` |
| `uses: actions/checkout@d23441a4… # v6.1.0` | `d23441a4…` | `pkg:githubactions/actions/checkout` |

git-pkgs already models declared versus resolved correctly for cargo. A
SHA-pinned action carries both halves on a single line: the SHA is the
resolution, the comment is the declaration. Today the declaration is dropped.

## Proposal

Parse the trailing comment and keep it beside the SHA:

- `requirement` stays the SHA, which is what actually gets resolved
- a new field carries the comment, e.g. `declared_version`
- the purl gains that version when a comment is present, along the lines of
  `pkg:githubactions/actions/checkout@v7.0.1`, with the SHA as a qualifier

The comment is a claim rather than a verified fact, which is why pinact ships
`--verify-comment`. It should be surfaced as declared, not resolved, and
consumers can decide how far to trust it.

## Alternative considered

Resolving the SHA to a tag through the GitHub API would be authoritative, but
it needs a network call and a token to recover something the file already
states, and it fails for a SHA whose tag has since been deleted.

## Reproducer

https://github.com/skagedal/reproducers/tree/main/git-pkgs-sha-pinned-action-loses-version

`verify/reproduce.sh` builds a throwaway repository holding the four records
in the table above, prints them, bumps the pinned SHA and shows the resulting
diff. No network, no credentials.

## Version

git-pkgs 0.20.0
```
