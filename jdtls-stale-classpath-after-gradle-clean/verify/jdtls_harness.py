#!/usr/bin/env python3
"""Shared harness: drives jdtls headlessly over LSP against the reproducer."""
import json, os, re, shutil, subprocess, tempfile, threading, time, glob

PROJ = "/Users/simon/code/reproducers/jdtls-stale-classpath-after-gradle-clean"
JDTLS = "/Users/simon/local/bin/jdtls"
# Workspaces must live OUTSIDE the project: an Eclipse workspace created inside
# the project being imported makes the import fail.
WS_ROOT = os.path.join(tempfile.gettempdir(), "jdtls-repro-ws")
GEN = PROJ + "/build/generated/sources/example/java"


def gradle(*tasks):
    r = subprocess.run([PROJ + "/gradlew", "-q", *tasks], cwd=PROJ,
                       capture_output=True, text=True)
    print(f"  gradle {' '.join(tasks)} -> rc={r.returncode}")
    return r


class Jdtls:
    def __init__(self, data_dir, update_mode="automatic"):
        self.data = data_dir
        self.update_mode = update_mode
        self.p = subprocess.Popen([JDTLS, "-data", data_dir], cwd=PROJ,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
        self.lock = threading.Lock()
        self.log = []
        threading.Thread(target=self._read, daemon=True).start()

    def send(self, msg):
        b = json.dumps(msg).encode()
        self.p.stdin.write(b"Content-Length: %d\r\n\r\n" % len(b) + b)
        self.p.stdin.flush()

    def _read(self):
        f = self.p.stdout
        while True:
            length = None
            while True:
                line = f.readline()
                if not line:
                    return
                line = line.strip()
                if not line:
                    break
                if line.lower().startswith(b"content-length"):
                    length = int(line.split(b":")[1])
            if length is None:
                continue
            try:
                msg = json.loads(f.read(length))
            except Exception:
                continue
            # Answer every server->client request so the server never stalls.
            if "id" in msg and "method" in msg:
                m, res = msg["method"], None
                if m == "workspace/configuration":
                    res = [None] * len(msg.get("params", {}).get("items", [1]))
                self.send({"jsonrpc": "2.0", "id": msg["id"], "result": res})
            elif msg.get("method") == "language/status":
                with self.lock:
                    self.log.append(msg["params"])

    def initialize(self):
        self.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "processId": os.getpid(),
            "rootUri": "file://" + PROJ,
            "workspaceFolders": [{"uri": "file://" + PROJ, "name": "repro"}],
            "initializationOptions": {"settings": {"java": {
                "configuration": {"updateBuildConfiguration": self.update_mode},
                "autobuild": {"enabled": True},
            }}},
            "capabilities": {
                "workspace": {"workspaceFolders": True, "configuration": True,
                              "didChangeWatchedFiles": {"dynamicRegistration": True},
                              "executeCommand": {}},
                "textDocument": {"publishDiagnostics": {}},
                "window": {"workDoneProgress": True},
            }}})
        time.sleep(1)
        self.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})

    def wait_ready(self, timeout=180):
        start = time.time()
        while time.time() - start < timeout:
            with self.lock:
                if any(s.get("type") == "ServiceReady" for s in self.log):
                    return True
            time.sleep(1)
        return False

    def classpath(self):
        hits = glob.glob(self.data + "/.metadata/.plugins/"
                         "org.eclipse.core.resources/.projects/*/.classpath")
        return hits[0] if hits else None

    def src_entries(self):
        cp = self.classpath()
        if not cp:
            return None
        return re.findall(r'kind="src"[^>]*path="([^"]*)"', open(cp).read())

    def markers(self):
        out = []
        for m in glob.glob(self.data + "/.metadata/.plugins/"
                           "org.eclipse.core.resources/.projects/*/.markers"):
            r = subprocess.run(["strings", "-n", "6", m], capture_output=True, text=True)
            out += [l for l in r.stdout.splitlines()
                    if re.search(r"missing required|cannot be built", l, re.I)]
        return out

    def touch_build_file(self):
        os.utime(PROJ + "/build.gradle", None)
        self.send({"jsonrpc": "2.0", "method": "workspace/didChangeWatchedFiles",
                   "params": {"changes": [
                       {"uri": "file://" + PROJ + "/build.gradle", "type": 2}]}})

    def kill(self):
        self.send({"jsonrpc": "2.0", "id": 999, "method": "shutdown", "params": None})
        time.sleep(2)
        self.p.kill()


def report(label, entries, markers, gen_exists):
    print(f"\n  [{label}]")
    print(f"    build/generated/sources/example/java on disk: {gen_exists}")
    print(f"    src entries in .classpath: {entries}")
    has = entries is not None and any("generated/sources/example" in e for e in entries)
    print(f"    -> generated entry present: {has}")
    for m in markers:
        print(f"    marker: {m.strip()}")
    return has


