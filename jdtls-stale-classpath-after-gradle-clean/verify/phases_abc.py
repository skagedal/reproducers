#!/usr/bin/env python3
"""Phases A-C: with updateBuildConfiguration=automatic, Buildship does the right
thing — the stale source folder entry is dropped on re-sync.

A: folder exists at import time         -> entry added        (expected)
B: folder removed, project re-synced    -> entry dropped      (so: no Buildship bug)
C: fresh import while folder is absent  -> entry never added  (expected)
"""
import os, time, glob, shutil
import jdtls_harness as V

WS_ROOT, GEN = V.WS_ROOT, V.GEN

for d in glob.glob(WS_ROOT + "/ws*"):
    shutil.rmtree(d, ignore_errors=True)

print("=" * 70)
print("PHASE A: folder exists at import time")
print("=" * 70)
V.gradle("clean")
V.gradle("generateSources")
print(f"  generated dir exists: {os.path.isdir(GEN)}")

s = V.Jdtls(WS_ROOT + "/ws1", update_mode="automatic")
s.initialize()
print(f"  ServiceReady: {s.wait_ready()}")
time.sleep(8)
a = V.report("A: after import, folder present", s.src_entries(), s.markers(), os.path.isdir(GEN))

print("\n" + "=" * 70)
print("PHASE B: folder removed by `gradle clean`, then project re-synced")
print("=" * 70)
V.gradle("clean")
print(f"  generated dir exists: {os.path.isdir(GEN)}")
s.touch_build_file()
time.sleep(45)
b = V.report("B: after re-sync, folder gone", s.src_entries(), s.markers(), os.path.isdir(GEN))
s.kill()

print("\n" + "=" * 70)
print("PHASE C: control — fresh import while folder is absent")
print("=" * 70)
print(f"  generated dir exists: {os.path.isdir(GEN)}")
s2 = V.Jdtls(WS_ROOT + "/ws2", update_mode="automatic")
s2.initialize()
print(f"  ServiceReady: {s2.wait_ready()}")
time.sleep(8)
c = V.report("C: fresh import, folder absent", s2.src_entries(), s2.markers(), os.path.isdir(GEN))
s2.kill()

print("\n" + "=" * 70)
print(f"  A entry present: {a}  <- expected True")
print(f"  B entry present: {b}  <- expected False (Buildship recovers on re-sync)")
print(f"  C entry present: {c}  <- expected False")
print("  AS EXPECTED" if a and not b and not c else "  UNEXPECTED — see phases above")
