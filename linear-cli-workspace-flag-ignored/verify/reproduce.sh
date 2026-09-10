#!/usr/bin/env bash
#
# Reproduces: the linear CLI ignores `--workspace <slug>` in every code path
# that builds a linear.app URL, so `issue view --web` fails outright when no
# workspace is set in a config file or LINEAR_WORKSPACE.
#
# The condition that matters is a config with no `workspace` key. Rather than
# disturb the real ~/.config/linear, this points XDG_CONFIG_HOME at a temp dir
# holding only a copy of credentials.toml: auth still resolves (with the API key
# in the system keyring it is not even in that file) while `workspace` is unset.
#
# Nothing here opens a browser. The two failing commands never get far enough
# to launch one, and the LINEAR_WORKSPACE workaround is deliberately not
# exercised, since on success it would hijack the browser -- see the README.
#
# Exits 0 if the bug reproduces, 1 if it appears fixed, 2 if the setup is wrong.

set -uo pipefail

ERR="workspace is not set via command line, configuration file, or environment"

fail() { printf 'setup problem: %s\n' "$1" >&2; exit 2; }

ISSUE="${1:-}"
if [[ -z "$ISSUE" ]]; then
  cat >&2 <<'USAGE'
usage: ./reproduce.sh <ISSUE-ID>

Takes any issue id you can read, e.g. ABC-123. Credentials must already be set
up (`linear auth login`).
USAGE
  exit 2
fi

command -v linear >/dev/null || fail "linear is not on PATH"

real_creds="${XDG_CONFIG_HOME:-$HOME/.config}/linear/credentials.toml"
[[ -f "$real_creds" ]] || fail "no credentials at $real_creds; run \`linear auth login\`"

printf '== version ==\n'
linear --version

tmp="$(mktemp -d)" || fail "mktemp failed"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/config/linear" "$tmp/cwd" || fail "could not populate $tmp"
cp "$real_creds" "$tmp/config/linear/credentials.toml" || fail "could not copy credentials"

# A linear.toml in the cwd or the enclosing git root would also supply
# `workspace`, so run from a scratch directory that is neither.
cd "$tmp/cwd" || fail "cannot cd to $tmp/cwd"
export XDG_CONFIG_HOME="$tmp/config"

printf '\n== control: auth resolves, and already knows the slug ==\n'
whoami_out="$(linear auth whoami 2>&1)" || fail "auth failed under the temp config: $whoami_out"
printf '%s\n' "$whoami_out"
slug="$(printf '%s\n' "$whoami_out" | awk '/Slug:/{print $2; exit}')"
[[ -n "$slug" ]] || fail "could not read a slug out of \`auth whoami\`"

printf '\n== control: issue url returns a URL (the API supplies it) ==\n'
url_out="$(linear issue url "$ISSUE" 2>&1)"
url_status=$?
printf '%s\n' "$url_out"

printf '\n== bug 1: issue view --web --workspace %s ==\n' "$slug"
view_out="$(linear --workspace "$slug" issue view "$ISSUE" --web 2>&1)"
view_status=$?
printf '%s\n(exit %d)\n' "$view_out" "$view_status"

printf '\n== bug 2: team list --web --workspace %s ==\n' "$slug"
team_out="$(linear --workspace "$slug" team list --web 2>&1)"
printf '%s\n' "$team_out"

printf '\n== result ==\n'
rc=0
if [[ "$view_out" == *"$ERR"* ]]; then
  printf 'REPRODUCED  issue view --web ignored --workspace (exit %d)\n' "$view_status"
else
  printf 'not reproduced: issue view --web honoured --workspace\n'
  rc=1
fi
if [[ "$team_out" == *"$ERR"* ]]; then
  printf 'REPRODUCED  team list --web ignored --workspace\n'
else
  printf 'not reproduced: team list --web honoured --workspace\n'
  rc=1
fi
if [[ $url_status -eq 0 && "$url_out" == https://* ]]; then
  printf 'CONTRAST    issue url built a URL in the same config, from the API\n'
fi
printf 'CONTRAST    auth whoami reported slug %s in the same config\n' "$slug"
exit $rc
