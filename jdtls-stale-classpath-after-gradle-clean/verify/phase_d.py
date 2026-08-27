#!/usr/bin/env python3
"""Phase D: does jdtls's default updateBuildConfiguration=interactive leave the
project permanently stuck after `gradle clean` removes a generated source dir?"""
import os, time, glob, shutil
import jdtls_harness as V

WS_ROOT = V.WS_ROOT
GEN = V.GEN

shutil.rmtree(WS_ROOT + "/ws3", ignore_errors=True)
print("=" * 70)
print("PHASE D: updateBuildConfiguration = 'interactive' (jdtls default)")
print("=" * 70)
V.gradle("clean")
V.gradle("generateSources")
print(f"  generated dir exists: {os.path.isdir(GEN)}")

s = V.Jdtls(WS_ROOT + "/ws3", update_mode="interactive")
s.initialize()
print(f"  ServiceReady: {s.wait_ready()}")
time.sleep(8)
d1 = V.report("D1: after import, folder present", s.src_entries(), s.markers(), os.path.isdir(GEN))

V.gradle("clean")
print(f"\n  gradle clean done; generated dir exists: {os.path.isdir(GEN)}")
s.touch_build_file()
time.sleep(50)
d2 = V.report("D2: folder gone, build file touched, interactive mode",
              s.src_entries(), s.markers(), os.path.isdir(GEN))
s.kill()

print("\n" + "=" * 70)
print(f"  D1 entry present: {d1}  <- expected True")
print(f"  D2 entry present: {d2}  <- STUCK if True")
print("  STUCK STATE REPRODUCED" if d1 and d2 else "  not stuck (entry updated)")
