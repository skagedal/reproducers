#!/usr/bin/env python3
"""Reproduce: changing java.configuration.updateBuildConfiguration re-imports
every Gradle subproject as its own root build, pinned to jdtls's bundled Gradle.

Phase 1  import the multi-project build with the default "interactive".
         Expected and observed: root uses the wrapper, `lib` carries no
         distribution of its own and delegates to the root build.

Phase 2  send workspace/didChangeConfiguration switching the setting to
         "automatic", exactly as a client does when the user edits it.
         GradlePreferenceChangeListener then loops over *every* Gradle project
         and calls GradleProjectImporter.getBuildConfiguration(subproject dir),
         which is BuildConfiguration.forRootProjectDirectory(subproject).
         `lib` becomes its own root build on DEFAULT_DISTRIBUTION.

The phase-2 state is persisted to .settings/org.eclipse.buildship.core.prefs,
so it survives restarts even though the setting never changes again.
"""
import shutil, sys, time
import jdtls_harness as V

# rootProject.name in settings.gradle.
ROOT = "jdtls-subproject-gradle-distribution-fallback"

WS = V.WS_ROOT + "/dist-check"
shutil.rmtree(WS, ignore_errors=True)

wrapper = V.wrapper_version()
print(f"wrapper declares Gradle {wrapper}; workspace {WS}")

s = V.Jdtls(WS, update_mode="interactive")
s.initialize()
print("ServiceReady:", s.wait_ready())

# Root + lib.
if not s.wait_for_projects(2):
    print("\nimport did not produce two Buildship projects; aborting")
    s.kill()
    sys.exit(2)
time.sleep(10)

before = s.buildship_prefs()
V.print_table("phase 1 - after import at updateBuildConfiguration=interactive", before)

print("\n--- workspace/didChangeConfiguration: interactive -> automatic ---")
s.set_update_build_configuration("automatic")

# The listener synchronises each project sequentially and the bundled Gradle has
# to start (and fail) against the current JVM, so give it room. Stop early once
# a subproject has grown a distribution of its own.
deadline = time.time() + 300
while time.time() < deadline:
    time.sleep(5)
    now = s.buildship_prefs()
    if any(p["distribution"] for n, p in now.items() if n != ROOT):
        break

time.sleep(5)
after = s.buildship_prefs()
V.print_table("phase 2 - after the setting changed", after)

errors = s.error_log(r"Unsupported class file major version|major version \d+")
if errors:
    print("\n  workspace log:")
    for line in errors[:3]:
        print("    " + line.strip())

s.kill()

# Every project other than the root should have no distribution of its own.
subprojects = {n: p for n, p in after.items() if n != ROOT}
bad = {n: p for n, p in subprojects.items()
       if p["distribution"] and wrapper not in p["distribution"]}

print(f"\n{len(subprojects)} subproject(s), {len(bad)} re-imported as an independent "
      f"root build on a Gradle other than the wrapper's {wrapper}")
for n, p in bad.items():
    print(f"  {n}: {p['distribution']}, connection.project.dir={p['project_dir']!r}")
print("REPRODUCED" if bad else "not reproduced (subprojects still delegate to the root)")
sys.exit(0 if bad else 1)
