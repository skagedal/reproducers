#!/usr/bin/env bash
#
# Reproduces: a crate listed in both [dependencies] and [dev-dependencies] of
# one Cargo.toml is stored by git-pkgs as a single row, the dev-dependency,
# so `git pkgs diff` on a clean working tree reports the runtime dependency
# as added.
#
# Everything happens in a throwaway git repository built from ./fixture, so
# this touches nothing outside $TMPDIR and needs no network.
#
# Exits 0 if the bug reproduces, 1 if it appears fixed, 2 if the setup is wrong.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
FIXTURE="$HERE/fixture"

fail() { printf 'setup problem: %s\n' "$1" >&2; exit 2; }

command -v git >/dev/null || fail "git is not on PATH"
command -v jq >/dev/null || fail "jq is not on PATH"
git pkgs --help >/dev/null 2>&1 || fail "git-pkgs is not installed (brew install git-pkgs)"
[[ -d "$FIXTURE" ]] || fail "no fixture directory next to this script"

printf '== versions ==\n'
git pkgs --version 2>&1 | head -1

repo="$(mktemp -d)"
trap 'rm -rf "$repo"' EXIT
cp -R "$FIXTURE"/. "$repo"/
cd "$repo" || fail "could not enter the temp repo"
git init -q .
git add -A
git -c user.email=r@example.com -c user.name=Reproducer commit -qm "fixture" ||
    fail "could not commit the fixture"
git pkgs init --no-hooks -q || fail "git pkgs init failed"

printf '\n== Cargo.toml ==\n'
cat Cargo.toml

printf '\n== git status (should be empty) ==\n'
git status --short

printf '\n== git pkgs list -f json ==\n'
listing="$(git pkgs list -f json)" || fail "git pkgs list failed"
printf '%s\n' "$listing" | jq -c '.[] | {name, requirement, dependency_type}'

printf '\n== git pkgs diff, nothing changed ==\n'
git pkgs diff --color never 2>&1
diff_json="$(git pkgs diff -f json 2>/dev/null)"

printf '\n== result ==\n'
rc=0

rows="$(printf '%s\n' "$listing" | jq '[.[] | select(.name == "anyhow")] | length')"
if [[ "$rows" == 1 ]]; then
    printf 'REPRODUCED  git pkgs list has one anyhow row, %s; the other is gone\n' \
        "$(printf '%s\n' "$listing" | jq -r '.[] | select(.name == "anyhow") | .dependency_type')"
else
    printf 'not reproduced: git pkgs list has %s anyhow rows\n' "$rows"
    rc=1
fi

added="$(printf '%s\n' "$diff_json" | jq -c '[.added[]? | {name, dependency_type}]')"
if [[ "$added" != "[]" && -n "$added" ]]; then
    printf 'REPRODUCED  git pkgs diff on a clean tree reports as added: %s\n' "$added"
else
    printf 'not reproduced: git pkgs diff reports nothing on a clean tree\n'
    rc=1
fi
exit $rc
