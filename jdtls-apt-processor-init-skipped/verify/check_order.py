#!/usr/bin/env python3
"""Phase 1: plain javac is order-sensitive.  Phase 2: jdtls loses the order."""
import os, shutil, subprocess, sys
import jdtls_harness as H

def run_gradle(*args):
    return subprocess.run([H.PROJ + "/gradlew", ":app:compileJava", "--rerun-tasks",
                           "-q", "--console=plain", *args],
                          cwd=H.PROJ, capture_output=True, text=True)

print("Phase 1 — plain javac, same inputs, only the path order differs")
H.build_jars()
holder_first = run_gradle()
claimer_first = run_gradle("-PclaimerFirst")
for label, res in (("holder before claimer", holder_first),
                   ("claimer before holder", claimer_first)):
    verdict = "compiles" if res.returncode == 0 else "FAILS"
    detail = ""
    if res.returncode != 0:
        line = next((l for l in res.stderr.splitlines() if "error:" in l), "")
        detail = "  " + line.strip()[-90:]
    print(f"    {label:24s} {verdict}{detail}")

order_sensitive = holder_first.returncode == 0 and claimer_first.returncode != 0
print(f"    => order-sensitive: {order_sensitive}")

print("\nPhase 2 — the order jdtls gives the same processor path")
gradle_order = H.gradle_processor_path()
if not gradle_order:
    sys.exit("could not read Gradle's processor path")

ws = os.path.join(H.WS_ROOT, "order")
shutil.rmtree(ws, ignore_errors=True)
server = H.Jdtls(ws)
try:
    server.initialize()
    if not server.wait_ready():
        sys.exit("jdtls never reported ServiceReady")
    if not server.wait_for_factorypath():
        sys.exit("jdtls never wrote a .factorypath")
    paths = server.factory_paths()
    server.open_document("app/src/main/java/demo/app/Foo.java")
    import time; time.sleep(8)
    errors = server.errors_for("app/src/main/java/demo/app/Foo.java")
finally:
    server.kill()

jdtls_order = paths.get("app", [])
width = max(len(x) for x in gradle_order + jdtls_order) + 2
print(f"    {'#':>3} {'gradle (what javac sees)':{width}s} jdtls .factorypath")
for i in range(max(len(gradle_order), len(jdtls_order))):
    g = gradle_order[i] if i < len(gradle_order) else ""
    j = jdtls_order[i] if i < len(jdtls_order) else ""
    flag = "" if g == j else "   <-- differs"
    print(f"    {i+1:>3} {g:{width}s} {j}{flag}")

print(f"\n    orders identical: {gradle_order == jdtls_order}")

def relative(order):
    if "holder.jar" in order and "claimer.jar" in order:
        return "holder first" if order.index("holder.jar") < order.index("claimer.jar") \
               else "claimer first"
    return "?"

print(f"    gradle: {relative(gradle_order)};  jdtls: {relative(jdtls_order)}")
if errors:
    print(f"    jdtls reports on Foo.java: {errors[0][:100]}")
else:
    print("    jdtls reports no error on Foo.java")

print()
if gradle_order != jdtls_order:
    print("REPRODUCED — jdtls does not preserve the processor path order.")
    print("Whether an order-sensitive processor pair works in the IDE is then luck.")
else:
    print("Orders match — the LinkedHashSet fix is in effect.")
