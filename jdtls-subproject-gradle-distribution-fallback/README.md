# jdtls: Gradle subprojects pinned to the bundled Tooling API distribution

**Status: reproduced minimally. Ready to file.**

Changing `java.configuration.updateBuildConfiguration` makes jdtls re-import
every Gradle *subproject* as an independent root build pinned to the Gradle
version bundled with its Tooling API (8.9), instead of the wrapper's. On a
current JDK that Gradle can't run at all, so every subproject fails to import —
and the state is persisted, so it survives every restart afterwards.

Proposed upstream issue text is at the bottom: [Issue draft](#issue-draft).

## Reproducing

```sh
cd verify
python3 check_distributions.py   # phase 1 + 2, prints REPRODUCED
python3 check_persistence.py     # restart, shows the damage is permanent
```

`jdtls_harness.py` drives jdtls over LSP on stdio: it answers every
server→client request so the server never stalls, waits for `ServiceReady`,
parses each project's `org.eclipse.buildship.core.prefs`, and greps the Eclipse
workspace log. Workspaces are created under the system temp dir — **not** inside
the project, since an Eclipse workspace nested in the project being imported
makes the import fail silently.

Edit `PROJ` / `JDTLS` at the top of `jdtls_harness.py` if your paths differ.

## What was measured

The build here is the minimum that shows it: a root with a 9.4.1 wrapper and one
`include 'lib'` subproject.

**Phase 1** — import at the default `updateBuildConfiguration=interactive`.
Correct: `lib` has no distribution of its own and delegates to the root build.

```
project                                        connection.gradle.distribution     connection.project.dir
jdtls-subproject-gradle-distribution-fallback  GRADLE_DISTRIBUTION(WRAPPER)       ''
lib                                            (none - delegates to root)         '..'
```

**Phase 2** — one `workspace/didChangeConfiguration` switching the setting to
`automatic`. `lib` becomes its own root build on Gradle 8.9:

```
project                                        connection.gradle.distribution     connection.project.dir
jdtls-subproject-gradle-distribution-fallback  GRADLE_DISTRIBUTION(WRAPPER)       ''
lib                                            GRADLE_DISTRIBUTION(VERSION(8.9))  ''
```

and its import fails, from the workspace log:

```
Caused by: BUG! exception in phase 'semantic analysis' in source unit '_BuildScript_' Unsupported class file major version 69
Caused by: java.lang.IllegalArgumentException: Unsupported class file major version 69
```

Three further facts, each verified rather than assumed:

- **It is the transition, not the value.** A fresh import with `automatic` set
  from the very first `initialize` is clean — `lib` still delegates to the root.
  Only a change of the setting while a workspace is open triggers it.
- **For some clients the transition happens on every startup.** That makes the
  point above much less reassuring than it sounds. A client can deliver its
  settings either in `initializationOptions` on `initialize` — as this harness
  does, which is why phase 1 is clean — or afterwards via
  `workspace/didChangeConfiguration`. Zed does the latter for
  `lsp.<server>.settings`, so jdtls starts every session at the default
  `interactive` and is moved to `automatic` a moment later. That is a genuine
  transition, so the listener fires on each launch, and clearing the workspace
  buys exactly one good session. Observed on a real four-subproject build: the
  fresh import at 14:48 wrote no subproject prefs at all (correctly delegating
  to the root), and a restart at 15:04:52 wrote
  `connection.gradle.distribution=GRADLE_DISTRIBUTION(VERSION(8.9))` for both
  subprojects at 15:05:04, with no setting having been edited in between.
- **Either direction breaks it.** `automatic` → `interactive` poisons `lib` just
  as `interactive` → `automatic` does, as the `Objects.equals` comparison
  implies. Verified, not inferred.
- **The damage is permanent.** `check_persistence.py` restarts jdtls on the same
  workspace with the setting already at `automatic`, so no change event fires.
  `lib` is still on 8.9: Buildship persisted it to
  `.settings/org.eclipse.buildship.core.prefs`, and nothing recomputes it.
- **The JVM is not the fix, the distribution is.** Running the Groovy init
  script jdtls injects:

  | Gradle | JVM | Result |
  | ------ | --- | ------ |
  | 8.9 | Java 26 | Unsupported class file major version 70 |
  | 8.9 | Java 25 | Unsupported class file major version 69 |
  | 9.4.1 | Java 26 | succeeds |

## Cause

`GradlePreferenceChangeListener.preferencesChange` loops over every Gradle
project in the workspace — subprojects included — and hands each one's own
directory to `GradleProjectImporter.getBuildConfiguration`, which is
`BuildConfiguration.forRootProjectDirectory(...)`. That single call produces both
symptoms: declaring a subproject a *root project directory* is what empties
`connection.project.dir`, and `getGradleDistribution(subprojectDir)` finds no
`gradle/wrapper/gradle-wrapper.properties` there, so it falls through to
`DEFAULT_DISTRIBUTION` — `GradleVersion.current()`, the bundled Tooling API.

The sibling path in `GradleBuildSupport.update` guards the same call with
`isRoot`. The listener does not. Both were touched by the same commit.

## Where it came from

Commit `86e30117` (PR
[#3349](https://github.com/eclipse-jdtls/eclipse.jdt.ls/pull/3349), merged
2025-01-07, fixing
[vscode-java#3893](https://github.com/redhat-developer/vscode-java/issues/3893))
added the `isRoot` guard to `GradleBuildSupport.update` and, in the same diff,
added the unguarded loop to `GradlePreferenceChangeListener`.

This is the third time the class of bug has been fixed in a different code path;
see also `200d352d` "Ignore subprojects when updating a gradle project" (2020).

## Not already reported

Searched `eclipse-jdtls/eclipse.jdt.ls` and `redhat-developer/vscode-java`. The
neighbouring issues — [#1431](https://github.com/eclipse-jdtls/eclipse.jdt.ls/issues/1431),
[#3149](https://github.com/eclipse-jdtls/eclipse.jdt.ls/issues/3149),
[#1041](https://github.com/eclipse-jdtls/eclipse.jdt.ls/issues/1041) — are all
"jdtls ignores the wrapper for the *root* project", with different causes. The
subproject-only fallback is unreported.

## Workaround

Set `java.import.gradle.version` to the wrapper's version. It is the branch
checked immediately after the wrapper in `getGradleDistribution`, and the
version must appear in Buildship's cached published-versions list
(`.metadata/.plugins/org.eclipse.buildship.core/gradle/versions.json`).
`java.import.gradle.home` works too and skips that lookup.

Verified on a real four-subproject build: all subprojects moved to
`GRADLE_DISTRIBUTION(VERSION(9.4.1))` and the import errors cleared. It treats
the symptom — the subprojects are still independent root builds — but it keeps
them off 8.9.

Deleting the workspace and re-importing also clears it, until the setting
changes again.

---

# Issue draft

*For https://github.com/eclipse-jdtls/eclipse.jdt.ls/issues/new — everything
below is the issue body.*

**Title:** Changing `java.configuration.updateBuildConfiguration` re-imports Gradle subprojects as independent root builds on the bundled Gradle distribution

Changing `java.configuration.updateBuildConfiguration` on an open workspace makes
jdtls re-import every Gradle **subproject** as its own root build, pinned to
`GradleProjectImporter.DEFAULT_DISTRIBUTION` (the version bundled with the
Tooling API, currently 8.9) rather than the build's wrapper.

Because Gradle 8.9 cannot run on a current JDK, every affected subproject then
fails to import with `Unsupported class file major version`. Buildship persists
the bad configuration, so it survives restarts even though the setting never
changes again.

### Cause

[`GradlePreferenceChangeListener.preferencesChange`](https://github.com/eclipse-jdtls/eclipse.jdt.ls/blob/ebc2bb7a158ee45db909cd77e84339b1902da9dd/org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/GradlePreferenceChangeListener.java#L84-L93):

```java
boolean updateBuildConfigurationChanged = !Objects.equals(
        oldPreferences.getUpdateBuildConfigurationStatus(),
        newPreferences.getUpdateBuildConfigurationStatus());
if (updateBuildConfigurationChanged) {
    waitForGradleJobs();
    for (IProject project : ProjectUtils.getGradleProjects()) {   // every project, subprojects included
        String projectPath = project.getLocation().toFile().getAbsolutePath();
        BuildConfiguration buildConfiguration =
                GradleProjectImporter.getBuildConfiguration(Paths.get(projectPath));
        GradleBuild gradleBuild = GradleCore.getWorkspace().createBuild(buildConfiguration);
        gradleBuild.synchronize(new NullProgressMonitor());
    }
}
```

`getBuildConfiguration` is `BuildConfiguration.forRootProjectDirectory(dir)`, so
passing a subproject directory declares that subproject a root build — which is
what empties `connection.project.dir`. And
[`getGradleDistribution`](https://github.com/eclipse-jdtls/eclipse.jdt.ls/blob/ebc2bb7a158ee45db909cd77e84339b1902da9dd/org.eclipse.jdt.ls.core/src/org/eclipse/jdt/ls/core/internal/managers/GradleProjectImporter.java#L414-L439)
only returns the wrapper when the folder it is handed contains
`gradle/wrapper/gradle-wrapper.properties`. A subproject folder does not, so it
falls through to `DEFAULT_DISTRIBUTION`.

`GradleBuildSupport.update` guards the same call with `isRoot(...)`. The listener
has no such guard. Both were introduced by the same commit, `86e30117` /
#3349.

### Steps to reproduce

Run VS Code (or any jdtls client) on a JDK that Gradle 8.9 cannot run — JDK 25
or 26 will do. Any multi-project Gradle build reproduces it; the smallest is
four files:

```
demo/
  gradlew, gradle/wrapper/…      # wrapper on a current Gradle, e.g. 9.4.1
  settings.gradle                # rootProject.name = 'demo'
                                 # include 'lib'
  build.gradle                   # empty
  lib/build.gradle               # plugins { id 'java' }
```

1. Make sure `java.configuration.updateBuildConfiguration` is at its default,
   `interactive`.
2. Open the `demo` folder and wait for the Java import to finish. It succeeds —
   both projects build against the wrapper's Gradle.
3. Now change that one setting: open Settings, search for "update build
   configuration", and switch it from `interactive` to `automatic`. (The
   direction doesn't matter — the values are compared with `Objects.equals`, so
   `automatic` → `interactive` breaks it just as well.)
4. Watch the Java import re-run.

**Expected:** nothing changes about which Gradle is used. `lib` is part of the
root's build and keeps using the wrapper.

**Actual:** `lib` is re-imported as an independent root build on Gradle 8.9 and
fails, because 8.9's Groovy cannot read class files from a current JDK:

```
Caused by: BUG! exception in phase 'semantic analysis' in source unit '_BuildScript_' Unsupported class file major version 69
Caused by: java.lang.IllegalArgumentException: Unsupported class file major version 69
```

To see the cause directly rather than through the error, look at
`<workspace>/.metadata/.plugins/org.eclipse.core.resources/.projects/*/.settings/org.eclipse.buildship.core.prefs`
before and after step 3:

| | before | after |
| --- | --- | --- |
| `demo` | `connection.gradle.distribution=GRADLE_DISTRIBUTION(WRAPPER)`<br>`connection.project.dir=` | unchanged |
| `lib` | *(no distribution line)*<br>`connection.project.dir=..` | `connection.gradle.distribution=GRADLE_DISTRIBUTION(VERSION(8.9))`<br>`connection.project.dir=` |

`lib` has gone from "part of the build rooted at `..`" to "a root build of its
own, on the bundled Gradle".

Three things that may save you time:

- **Only changing the setting triggers it — but for some clients that is every
  startup.** Opening the project with `automatic` already set in
  `initializationOptions` is clean. However, a client is free to deliver its
  settings *after* `initialize` instead, via `workspace/didChangeConfiguration`,
  and Zed does exactly that for `lsp.<server>.settings`. jdtls then starts each
  session at the default `interactive` and is moved to the configured value a
  moment later — a real transition, so the listener fires on every launch, and
  deleting the workspace buys one good session. On a real four-subproject build
  the fresh import wrote no subproject prefs at all, and a restart sixteen
  minutes later wrote `VERSION(8.9)` for every subproject, with no setting
  having been edited in between.

  So the guard matters even for users who set this once and never touch it
  again, which may be part of why it has gone unnoticed: on the clients most
  people test with, you have to edit the setting to see it.
- **Reloading the window does not heal it.** Buildship persists the
  configuration and nothing recomputes it for non-root projects, so the project
  stays broken until the jdtls workspace is deleted. This is the part that makes
  it painful in practice: the setting was changed once, weeks ago, and every
  session since has been broken with no visible connection to that edit.
- **It is not specific to a single subproject.** On a real four-subproject build
  all four were affected.

I also have a small scripted reproducer that drives jdtls headlessly over LSP,
flips the setting via `workspace/didChangeConfiguration`, and prints the table
above for both phases — happy to share it if that is more useful than the manual
steps.

### Environment

- jdtls `main` (`org.eclipse.jdt.ls.core_1.61.0.202608260724`), also present in
  the 1.58.0 release
- `org.gradle.toolingapi_8.9.0`, `org.eclipse.buildship.core_3.1.10`
- JDK 25.0.4.1 (Zulu), macOS. The same failure occurs on JDK 26 as
  `major version 70`.

### Suggested fix

Skip non-root projects in the listener, as `GradleBuildSupport.update` already
does — resolve the existing build via `GradleCore.getWorkspace().getBuild(project)`
and only mint a new root build for actual roots. Making
`getGradleDistribution` walk up to the enclosing build root would fix the
distribution half, but the empty `connection.project.dir` would remain.
