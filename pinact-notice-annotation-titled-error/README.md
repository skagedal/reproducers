# pinact: a line it fixed is annotated "pinact error"

**Status: reproduced against pinact 5.0.0, filed as [suzuki-shunsuke/pinact#1790](https://github.com/suzuki-shunsuke/pinact/issues/1790).**

Run in GitHub Actions, `pinact run` annotates every line it pins or updates.
When it fixes the line the annotation is a `notice`, and pinact exits 0, but
the title is still "pinact error":

```
::notice file=.github/workflows/unpinned.yml,line=6,title=pinact error::      - uses: actions/setup-java@de7274f081f381c8f8158605e0321c36c376e2e6 # v6.0.1
```

So the run summary shows "pinact error" next to every action that was moved
forward, after a run where nothing went wrong.

The cause is in `outputGitHubActionsAnnotation`: the level follows `Fix`, the
title does not.

```go
level := "notice"
if !c.param.Fix {
    level = levelError
}
fmt.Fprintf(c.param.Stderr, "::%s file=%s,line=%d,title=pinact error::%s\n", level, line.File, line.Number, newLine)
```

[pkg/controller/run/run.go#L366-L375 at v5.0.0](https://github.com/suzuki-shunsuke/pinact/blob/v5.0.0/pkg/controller/run/run.go#L366-L375)

pinact has no switch for the annotations. They are on whenever
`GITHUB_ACTIONS=true`, and unsetting that also drops the "pinact min-age
violation" errors, which are worth having.

The draft the issue was written from is at the bottom: [Issue draft](#issue-draft).

## How I hit this

The weekly dependency update in
[homebrew-tap](https://github.com/skagedal/homebrew-tap) runs
`pinact run --update`. Its run summary listed two "pinact error" annotations,
one per action pinact had updated, on a green run.

## Reproducing

This directory has one workflow,
[`.github/workflows/unpinned.yml`](.github/workflows/unpinned.yml), with an
unpinned `actions/setup-java@v6.0.1`. pinact annotates whenever
`GITHUB_ACTIONS=true`, so there is no need to be in Actions:

```sh
GITHUB_ACTIONS=true pinact run
```

pinact pins the line, so put it back before running again:

```sh
git restore .github/workflows/unpinned.yml
```

For comparison, `GITHUB_ACTIONS=true pinact run --check` reports the same line
as `::error`, still titled "pinact error", and leaves the file alone. That is
the case the title fits.

## Issue draft

````markdown
Title: `pinact run` titles the notice annotation for a fixed line "pinact error"

## pinact version

```console
$ pinact -v
pinact version 5.0.0
```

## Environment

* OS (Windows, Linux, macOS, etc): macOS, and Linux in GitHub Actions
* CPU Architecture (amd64, arm64, etc): arm64 (macOS), amd64 (Actions)

## Overview

In GitHub Actions, `pinact run` annotates each line it changes. When it fixes the line, the annotation is a `notice` and pinact exits 0, but the title is "pinact error". The run summary shows "pinact error" next to every action pinact pinned or updated, after a run where nothing went wrong.

## How to reproduce

workflow file

```yaml
on: workflow_dispatch
jobs:
  noop:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-java@v6.0.1
```

```console
$ GITHUB_ACTIONS=true pinact run
::notice file=.github/workflows/unpinned.yml,line=6,title=pinact error::      - uses: actions/setup-java@de7274f081f381c8f8158605e0321c36c376e2e6 # v6.0.1
```

Reproducer: https://github.com/skagedal/reproducers/tree/main/pinact-notice-annotation-titled-error

## Expected Behaviour

The title says what happened, e.g. "pinact fixed", when the line was fixed.

## Actual Behaviour

The title is "pinact error", although the level is `notice` and pinact exits 0.

## Important Factoids

In `outputGitHubActionsAnnotation`, the level depends on `Fix` but the title is fixed:

https://github.com/suzuki-shunsuke/pinact/blob/v5.0.0/pkg/controller/run/run.go#L366-L375

"pinact error" fits `--check`, where the level is `error`. Choosing the title together with the level would cover both.
````
