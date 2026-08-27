#!/usr/bin/env python3
"""Show that the phase-2 damage is permanent.

Run check_distributions.py first, then this. It restarts jdtls on the same
workspace with updateBuildConfiguration already at "automatic", so the
preference never changes and GradlePreferenceChangeListener never runs. `lib`
is still its own root build on Gradle 8.9, because Buildship persisted that to
.settings/org.eclipse.buildship.core.prefs.
"""
import os, sys, time
import jdtls_harness as V

ROOT = "jdtls-subproject-gradle-distribution-fallback"
WS = V.WS_ROOT + "/dist-check"

if not os.path.isdir(WS):
    print(f"{WS} does not exist - run check_distributions.py first")
    sys.exit(2)

wrapper = V.wrapper_version()
s = V.Jdtls(WS, update_mode="automatic")   # same value as at shutdown: no change event
s.initialize()
print("ServiceReady:", s.wait_ready())
time.sleep(30)

prefs = s.buildship_prefs()
V.print_table("after restart, no preference change", prefs)
s.kill()

bad = {n: p for n, p in prefs.items()
       if n != ROOT and p["distribution"] and wrapper not in p["distribution"]}
print("\nSTILL BROKEN - the state is persisted, not recomputed" if bad
      else "\nhealed on restart")
sys.exit(0 if bad else 1)
