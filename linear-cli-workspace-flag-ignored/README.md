# linear-cli: `--workspace` is ignored by every `--web`/`--app` code path

**Status: reproduced minimally against 2.6.0, not yet filed.**

The `linear` CLI's global `--workspace <slug>` flag has no effect on any command
that builds a `linear.app` URL. Those commands read the workspace with
`getOption("workspace")` and pass no CLI value, so the flag's own tier in
`resolveRawOption()` is never populated and the command dies with:

```
workspace is not set via command line, configuration file, or environment.
```

The message lists "command line" as a source, which is what makes this a
nuisance to diagnose: the flag the error implicitly points you at is precisely
the one being dropped. Only `LINEAR_WORKSPACE` or a `workspace` key in a
`linear.toml` actually work.

This is not the `-w` short-flag collision from
[schpet/linear-cli#174](https://github.com/schpet/linear-cli/issues/174), which
is fixed — `-w` maps to `--web` correctly in 2.6.0. Parsing is fine here; the
parsed value just never reaches the URL builders.

Proposed upstream issue text is at the bottom: [Issue draft](#issue-draft).

## How I hit this

`linear issue view ICC-1398` worked while `linear issue view ICC-1398 --web`
failed. The cause on my machine was unrelated to the flag — my config sat at
`~/.config/linear.toml` when the CLI reads `~/.config/linear/linear.toml`, one
directory down, so `workspace` had never been loaded. Everything except the
URL-building paths tolerates that, because they get the workspace from the API
instead.

Reaching for the documented `--workspace` flag to work around it is what
surfaced the actual bug: the flag changes nothing.

## Reproducing

```sh
cd verify
./reproduce.sh ICC-1398          # any issue id you can read
```

Exit 0 means the bug is still present, 1 means it looks fixed, 2 means the
setup is wrong (no `linear` on PATH, no credentials).

The condition that matters is a config with **no** `workspace` key, which is
awkward to arrange without disturbing a working setup. The script points
`XDG_CONFIG_HOME` at a temp directory holding only a copy of
`credentials.toml`, and runs from a scratch cwd outside any git repo so no
project-level `linear.toml` is found either. With the API key in the system
keyring it isn't in the copied file at all, so auth keeps working while
`workspace` is genuinely unset.

Nothing in the script opens a browser: the two failing commands never get far
enough to launch one, and the `LINEAR_WORKSPACE` workaround is deliberately
left unexercised because on success it would launch one for real.

## What was measured

All four invocations below run under the same temp config, in the same script:

| command | result |
| ------- | ------ |
| `linear auth whoami` | reports `Slug: airahome` |
| `linear issue url ICC-1398` | prints the full `https://linear.app/airahome/issue/...` URL |
| `linear --workspace airahome issue view ICC-1398 --web` | `workspace is not set...`, exit 1 |
| `linear --workspace airahome team list --web` | `✗ Failed to fetch teams: workspace is not set...` |

The first two are the interesting part. The workspace slug is not unavailable —
`auth whoami` prints it, and `issue url` returns an entire correct URL for the
very issue that `issue view --web` cannot construct a link to, because that
command asks the API for the URL rather than assembling one from a slug.

## Root cause

`resolveRawOption()` in `src/config.ts` has the correct precedence chain — CLI
value, then `LINEAR_*` env var, then project config, then global config:

```ts
function resolveRawOption(optionName: OptionName, cliValue?: string) {
  if (cliValue != null) {
    return { raw: cliValue, source: "cli" }
  }
  const envKey = "LINEAR_" + optionName.toUpperCase()
  ...
}
```

Every `--web`/`--app` call site calls `getOption("workspace")` with no second
argument, so `cliValue` is always `undefined` and the `"cli"` tier is dead code
for this option. `--workspace` is stored separately via `setCliWorkspace()` and
consulted only when picking which credential to authenticate with, never when
building a URL.

Affected sites, all reading `getOption("workspace")` with no CLI value:

| location | behaviour when unset |
| -------- | -------------------- |
| `openIssuePage()` (`issue view --web/--app`) | `console.error` + `Deno.exit(1)` |
| `openProjectPage()` | `console.error` + `Deno.exit(1)` |
| `openTeamAssigneeView()` | `console.error` + `Deno.exit(1)` |
| `team list --web/--app` | throws `ValidationError` |
| `team autolinks` | throws `ValidationError` |

Handling is inconsistent across the codebase: `project list --web` and
`initiative list --web` reach the same missing-workspace condition but recover
by querying `viewer.organization.urlKey` and carrying on, so they work with no
`workspace` configured at all. The five above hard-fail.

Names above come from the original TypeScript that ships embedded in the
compiled Deno binary (`strings` on the Homebrew build), so they should match
upstream. I could not pin the filename for the three `open*Page()` functions
beyond `src/utils/`.

## Issue draft

---

**Title:** `--workspace` flag is ignored by every `--web`/`--app` code path

## Summary

The global `--workspace <slug>` flag has no effect on the commands that build
`linear.app` URLs. They read the workspace via `getOption("workspace")`
**without passing the CLI value**, so the flag's own precedence tier in
`resolveRawOption()` is never populated and the command fails with:

```
workspace is not set via command line, configuration file, or environment.
```

The message names "command line" as a valid source, which is what makes this
confusing to debug — passing the flag it suggests changes nothing.

This is *not* the `-w` short-flag collision from #174 (that is fixed; `-w` maps
to `--web` correctly in 2.6.0). Flag parsing works fine here — the parsed value
simply is not plumbed through to the URL builders.

## Version

`linear 2.6.0`, installed via `brew install schpet/tap/linear`, macOS (arm64).

## Reproduction

Needs a config with no `workspace` set, so the flag is the only source.
Credentials come from the system keyring, so auth still succeeds:

```console
$ mkdir -p /tmp/lc/linear && cp ~/.config/linear/credentials.toml /tmp/lc/linear/
$ cd /tmp && export XDG_CONFIG_HOME=/tmp/lc     # no linear.toml anywhere

$ linear auth whoami
Workspace: Aira
  Slug: airahome                                # <-- the slug is known here
  URL: https://linear.app/airahome

$ linear issue url ABC-123                      # <-- and a URL is obtainable
https://linear.app/airahome/issue/ABC-123/some-title

$ linear --workspace airahome issue view ABC-123 --web
workspace is not set via command line, configuration file, or environment.
$ echo $?
1

$ linear --workspace airahome team list --web
✗ Failed to fetch teams: workspace is not set via command line, configuration file, or environment
```

Setting `LINEAR_WORKSPACE=airahome`, or `workspace = "..."` in a `linear.toml`,
both work — that's the current workaround.

## Root cause

`resolveRawOption()` in `src/config.ts` has the right precedence chain — CLI
value, then `LINEAR_*` env, then project config, then global config:

```ts
function resolveRawOption(optionName: OptionName, cliValue?: string) {
  if (cliValue != null) {
    return { raw: cliValue, source: "cli" }
  }
  const envKey = "LINEAR_" + optionName.toUpperCase()
  ...
}
```

But the `--web`/`--app` call sites all call `getOption("workspace")` with no
second argument, so `cliValue` is always `undefined` and the `"cli"` tier is
dead code for this option. The flag's value is stored separately via
`setCliWorkspace()` and is only consulted when selecting which credential to
use, never when building a URL.

Affected call sites, all reading `getOption("workspace")` with no CLI value:

| Location | Behavior when unset |
|---|---|
| `openIssuePage()` (`issue view --web/--app`) | `console.error` + `Deno.exit(1)` |
| `openProjectPage()` | `console.error` + `Deno.exit(1)` |
| `openTeamAssigneeView()` | `console.error` + `Deno.exit(1)` |
| `team list --web/--app` | throws `ValidationError` |
| `team autolinks` | throws `ValidationError` |

Worth noting the handling is inconsistent: `project list --web` and
`initiative list --web` hit the same missing-workspace condition but recover by
querying `viewer.organization.urlKey` and carrying on, so they work with no
`workspace` configured at all. The five above hard-fail instead.

## Suggested fix

Any of these would do, and they compose well:

1. Have the `"workspace"` option consult the stored CLI value directly — e.g.
   `resolveRawOption()` falling back to `cliWorkspace` for that option name.
   That fixes all five sites at once without touching their signatures, and
   keeps `--workspace` meaning the same thing everywhere.
2. Give the five hard-failing sites the `viewer.organization.urlKey` fallback
   that `project list` and `initiative list` already use, so a missing
   `workspace` config is never fatal.
3. For the issue and project cases specifically, use the `url` the API already
   returns — `issue url` does exactly this and works with no workspace
   configured — instead of assembling a URL from a slug.

Separately: if the flag is intentionally credential-selection-only, the error
message should stop listing "command line" as a source.
