# jdtls: stale `.classpath` after `gradle clean` removes a generated source folder

A Gradle project imported by jdtls ends up with a permanent
`Project 'x' is missing required source folder: 'build/generated/...'` error that
no language-server restart clears, while `./gradlew check` passes cleanly.

Originally suspected to be a Buildship bug. **It is not** — see
[Not a Buildship bug](#not-a-buildship-bug). The cause is jdtls's default
`java.configuration.updateBuildConfiguration=interactive`, which leaves the
generated `.classpath` stale indefinitely in clients that don't surface the
server's actionable notifications.

## Symptom

Three error markers per affected project, all attached to the *project*
directory rather than to any file:

```
Project 'on-site-dossier-schema' is missing required source folder: 'build/generated/sources/proto/test/java'
The project cannot be built until build path errors are resolved
The project was not built since it depends on on-site-dossier-schema, which has build path errors
```

Because the marker's resource is a directory, editors that build a diagnostics
list by opening buffers and resolving ranges cannot display them — in Zed they
are counted in the status-bar indicator but never appear in the project
diagnostics panel.

## Setup

`build.gradle` registers a generated source directory unconditionally, the same
shape as `protobuf-gradle-plugin`'s `build/generated/sources/proto/<sourceSet>/java`:

```groovy
def generatedSources = layout.buildDirectory.dir('generated/sources/example/java')
sourceSets.main.java.srcDir generatedSources
```

Whether the directory exists on disk depends on whether the generating task had
anything to do. With `protobuf-gradle-plugin` and no `src/test/proto`,
`generateTestProto` is `NO-SOURCE`, so the test output directory is never
created.

## Reproduce

```sh
./gradlew generateSources    # the directory now exists
```

1. Import the project into an IDE that uses jdtls (or Eclipse + Buildship).
   The `.classpath` gains `<classpathentry kind="src" path="build/generated/sources/example/java">`
   and there are no errors.
2. `./gradlew clean` — `build/` is wiped, so the source folder disappears.
3. Restart the language server as many times as you like.

**Actual:** the entry remains in `.classpath`, the project keeps a
"missing required source folder" error, and nothing recovers it.

**Expected:** the entry is dropped, as it would be on a fresh import of the
exact same Gradle build (see phase C below).

## Verified results

`verify/` drives jdtls headlessly over LSP and inspects the generated
`.classpath` and Eclipse's persisted `.markers`:

```sh
cd verify
python3 phases_abc.py     # updateBuildConfiguration = automatic
python3 phase_d.py        # updateBuildConfiguration = interactive (jdtls default)
```

Measured against jdtls built from `eclipse.jdt.ls` main, bundling
`org.eclipse.buildship.core 3.1.10` and `org.gradle.toolingapi 8.9.0`,
Gradle 9.7.1:

| Phase | `updateBuildConfiguration` | Scenario | Entry in `.classpath` |
| ----- | -------------------------- | -------- | --------------------- |
| A | `automatic` | folder present at import | present (correct) |
| B | `automatic` | folder deleted, then re-synced | **dropped** (correct) |
| C | `automatic` | fresh import, folder absent | never added (correct) |
| D | `interactive` | folder deleted, then build file touched | **still present** (stuck) |

Phase D is the bug. Same Gradle build, same Buildship, same deleted directory —
only the update mode differs.

## Not a Buildship bug

The first hypothesis was an asymmetry in
`org.eclipse.buildship.core.internal.workspace.SourceFolderUpdater`:
`addNewSourceFolders` guards each entry with `existsInSameLocation(...)`, while
`updateExistingSourceFolders` refreshes an already-present entry with no
existence check. Phase B falsifies it — the entry *is* dropped on re-sync.

The reason is upstream of Buildship: Gradle's `EclipseProject` tooling model
omits source directories that do not exist on disk, so after `clean` the entry
is absent from the model and `updateExistingSourceFolders` removes it as a
source folder Gradle no longer declares. Buildship's existence check is
belt-and-braces, not the load-bearing part.

What actually goes wrong is that **nothing triggers the re-sync**. jdtls updates
a project's configuration when a build file changes, and in the default
`interactive` mode it does not do so itself — it sends a
`language/actionableNotification` for the client to prompt on. A client that
ignores that notification (Zed does) never re-syncs, so the `.classpath`
written at import time survives every restart. `gradle clean` does not touch a
build file, so even `automatic` mode only recovers on the *next* build file
edit.

jdtls's default: `Preferences.java`,
`updateBuildConfigurationStatus = FeatureStatus.interactive`.

## Workarounds

- Set `java.configuration.updateBuildConfiguration` to `automatic`, so editing
  any build file re-syncs and clears the stale entry without needing a prompt
  the client cannot show.
- Recreate the empty directory. JDT only checks existence, so an empty
  directory satisfies it, and it lives in gitignored `build/` — nothing to
  commit. Note that Eclipse's `IResource.exists()` reads its own persisted
  resource tree, so this needs either workspace auto-refresh
  (`refresh.enabled=true` in the workspace's
  `.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.core.resources.prefs`,
  off by default) or a fresh import to be noticed.
- Delete the jdtls workspace under `~/Library/Caches/jdtls/` and let the project
  re-import from scratch.
