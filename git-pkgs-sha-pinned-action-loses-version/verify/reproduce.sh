#!/usr/bin/env bash
#
# Reproduces: git-pkgs drops the version comment that sits beside a
# SHA-pinned GitHub Action, so the only human-readable version in the line
# never reaches its database, its JSON output or its purls.
#
# Everything happens in a throwaway git repository built from ./fixture, so
# this touches nothing outside $TMPDIR and needs no network: git-pkgs reads
# manifests and lockfiles off disk, and the fixture ships a Cargo.lock.
#
# The fixture is arranged as a comparison:
#
#   Cargo.toml                declared range, nothing resolved it
#   Cargo.lock                the same crate, resolved to an exact version
#   tag-pinned.yml            an action pinned by tag
#   sha-pinned.yml            the same action pinned by SHA, version in a comment
#
# Exits 0 if the bug reproduces, 1 if it appears fixed, 2 if the setup is wrong.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
FIXTURE="$HERE/fixture"

# actions/checkout v6.1.0 -> v7.0.1. A major bump, and the only place either
# version is written down is the trailing comment.
OLD_SHA="d23441a48e516b6c34aea4fa41551a30e30af803"
OLD_VERSION="v6.1.0"
NEW_SHA="3d3c42e5aac5ba805825da76410c181273ba90b1"
NEW_VERSION="v7.0.1"

fail() { printf 'setup problem: %s\n' "$1" >&2; exit 2; }

command -v git >/dev/null || fail "git is not on PATH"
command -v jq >/dev/null || fail "jq is not on PATH"
git pkgs --help >/dev/null 2>&1 || fail "git-pkgs is not installed (brew install git-pkgs)"
[[ -d "$FIXTURE" ]] || fail "no fixture directory next to this script"

printf '== versions ==\n'
git pkgs version 2>/dev/null || git pkgs --version 2>&1 | head -1

repo="$(mktemp -d)"
trap 'rm -rf "$repo"' EXIT
cp -R "$FIXTURE"/. "$repo"/
cd "$repo" || fail "could not enter the temp repo"
git init -q .
git add -A
git -c user.email=r@example.com -c user.name=Reproducer commit -qm "fixture" ||
    fail "could not commit the fixture"
git pkgs init --no-hooks -q || fail "git pkgs init failed"

listing="$(git pkgs list -f json)" || fail "git pkgs list failed"

printf '\n== what git-pkgs recorded ==\n'
printf '%s\n' "$listing" | jq -r '
    ["ECOSYSTEM", "NAME", "REQUIREMENT", "PURL", "FROM"],
    (.[] | [.ecosystem, .name, .requirement, .purl, .manifest_path])
    | @tsv' | column -t -s "$(printf '\t')"

# One row per thing being compared.
row() {
    printf '%s\n' "$listing" | jq -r --arg path "$1" --arg name "$2" \
        'first(.[] | select(.manifest_path == $path and .name == $name)) // empty'
}
sha_row="$(row ".github/workflows/sha-pinned.yml" "actions/checkout")"
tag_row="$(row ".github/workflows/tag-pinned.yml" "actions/checkout")"
lock_row="$(row "Cargo.lock" "anyhow")"
manifest_row="$(row "Cargo.toml" "anyhow")"

[[ -n "$sha_row" ]] || fail "git-pkgs did not record the SHA-pinned action at all"
[[ -n "$lock_row" ]] || fail "git-pkgs did not record the Cargo.lock entry"

field() { printf '%s\n' "$1" | jq -r --arg f "$2" '.[$f] // ""'; }

printf '\n== the same action, written two ways ==\n'
printf 'by tag   requirement=%-42s purl=%s\n' \
    "$(field "$tag_row" requirement)" "$(field "$tag_row" purl)"
printf 'by SHA   requirement=%-42s purl=%s\n' \
    "$(field "$sha_row" requirement)" "$(field "$sha_row" purl)"
printf 'the SHA-pinned line says "# %s"; that string appears in the record: %s\n' \
    "$OLD_VERSION" \
    "$(printf '%s' "$sha_row" | grep -q "$OLD_VERSION" && echo yes || echo no)"

printf '\n== a package manager that has both a declared and a resolved version ==\n'
printf 'declared (Cargo.toml)  requirement=%-12s purl=%s\n' \
    "$(field "$manifest_row" requirement)" "$(field "$manifest_row" purl)"
printf 'resolved (Cargo.lock)  requirement=%-12s purl=%s\n' \
    "$(field "$lock_row" requirement)" "$(field "$lock_row" purl)"

# Now the symptom as it is actually met: an update, seen through `diff`.
sed -i.bak "s/$OLD_SHA # $OLD_VERSION/$NEW_SHA # $NEW_VERSION/" \
    .github/workflows/sha-pinned.yml
rm -f .github/workflows/sha-pinned.yml.bak
grep -q "$NEW_SHA" .github/workflows/sha-pinned.yml ||
    fail "could not rewrite the pinned SHA in the fixture copy"

printf '\n== git pkgs diff after bumping that pin from %s to %s ==\n' \
    "$OLD_VERSION" "$NEW_VERSION"
diff_text="$(git pkgs diff --color never 2>&1)"
printf '%s\n' "$diff_text"
diff_json="$(git pkgs diff -f json 2>/dev/null)"

printf '\n== result ==\n'
rc=0

if printf '%s' "$sha_row" | grep -q "$OLD_VERSION"; then
    printf 'not reproduced: the version comment reached git pkgs list\n'
    rc=1
else
    printf 'REPRODUCED  git pkgs list keeps the SHA and drops "%s"\n' "$OLD_VERSION"
fi

if printf '%s' "$diff_json" | grep -q "$NEW_VERSION"; then
    printf 'not reproduced: the version comment reached git pkgs diff\n'
    rc=1
else
    printf 'REPRODUCED  git pkgs diff reports %s -> %s, with no sign that a\n' \
        "${OLD_SHA:0:12}..." "${NEW_SHA:0:12}..."
    printf '            major bound was crossed\n'
fi

case "$(field "$sha_row" purl)" in
    *@*) printf 'not reproduced: the purl carries a version\n'; rc=1 ;;
    *)   printf 'REPRODUCED  the purl is %s, with no version component\n' \
            "$(field "$sha_row" purl)" ;;
esac

printf 'CONTRAST    the tag-pinned copy of the same action keeps %s\n' \
    "$(field "$tag_row" requirement)"
printf 'CONTRAST    cargo resolved: purl %s\n' "$(field "$lock_row" purl)"
printf 'CONTRAST    cargo declared: requirement %s, version-less purl, which is\n' \
    "$(field "$manifest_row" requirement)"
printf '            correct, because a range is not a version\n'
exit $rc
