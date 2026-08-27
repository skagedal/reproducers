#!/usr/bin/env python3
"""Shared harness: drives jdtls headlessly over LSP against the reproducer."""
import json, os, re, subprocess, tempfile, threading, time, glob

PROJ = "/Users/simon/code/reproducers/jdtls-subproject-gradle-distribution-fallback"
JDTLS = "/Users/simon/local/bin/jdtls"
# Workspaces must live OUTSIDE the project: an Eclipse workspace created inside
# the project being imported makes the import fail.
WS_ROOT = os.path.join(tempfile.gettempdir(), "jdtls-repro-ws")

PREFS_GLOB = ("/.metadata/.plugins/org.eclipse.core.resources/.projects/*"
              "/.settings/org.eclipse.buildship.core.prefs")


def wrapper_version():
    """The Gradle version the build's wrapper declares."""
    text = open(PROJ + "/gradle/wrapper/gradle-wrapper.properties").read()
    return re.search(r'gradle-([\d.]+)-bin\.zip', text).group(1)


class Jdtls:
    def __init__(self, data_dir, update_mode="interactive"):
        self.data = data_dir
        self.update_mode = update_mode
        os.makedirs(data_dir, exist_ok=True)
        self.stderr = open(os.path.join(data_dir, "jdtls-stderr.log"), "wb")
        self.p = subprocess.Popen([JDTLS, "-data", data_dir], cwd=PROJ,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.stderr)
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

    def set_update_build_configuration(self, mode):
        """Flip java.configuration.updateBuildConfiguration the way any LSP
        client does when the user edits that setting.

        JDTLanguageServer.didChangeConfiguration passes params.settings straight
        to Preferences.updateFrom, so the map is the `java.*` tree itself with no
        enclosing "settings" key (MapFlattener accepts nested or dotted form)."""
        self.update_mode = mode
        self.send({"jsonrpc": "2.0", "method": "workspace/didChangeConfiguration",
                   "params": {"settings": {"java": {
                       "configuration": {"updateBuildConfiguration": mode}}}}})

    def wait_ready(self, timeout=180):
        start = time.time()
        while time.time() - start < timeout:
            with self.lock:
                if any(s.get("type") == "ServiceReady" for s in self.log):
                    return True
            time.sleep(1)
        return False

    def buildship_prefs(self):
        """{project name: parsed org.eclipse.buildship.core.prefs} per project."""
        out = {}
        for f in sorted(glob.glob(self.data + PREFS_GLOB)):
            name = os.path.basename(os.path.dirname(os.path.dirname(f)))
            body = open(f).read()
            out[name] = dict(
                distribution=_grab(body, "connection.gradle.distribution"),
                project_dir=_grab(body, "connection.project.dir"),
            )
        return out

    def wait_for_projects(self, count, timeout=240):
        start = time.time()
        while time.time() - start < timeout:
            if len(self.buildship_prefs()) >= count:
                return True
            time.sleep(2)
        return False

    def error_log(self, pattern):
        """Lines matching `pattern` in the Eclipse workspace log."""
        path = self.data + "/.metadata/.log"
        if not os.path.exists(path):
            return []
        body = open(path, errors="replace").read()
        return [l for l in body.splitlines() if re.search(pattern, l)]

    def kill(self):
        self.send({"jsonrpc": "2.0", "id": 999, "method": "shutdown", "params": None})
        time.sleep(2)
        self.p.kill()
        self.stderr.close()


def _grab(body, key):
    m = re.search(r'^%s=(.*)$' % re.escape(key), body, re.M)
    return m.group(1).strip() if m else None


def print_table(title, prefs):
    print(f"\n  {title}")
    print(f"    {'project':50s} {'connection.gradle.distribution':34s} connection.project.dir")
    for name, p in prefs.items():
        dist = p["distribution"] or "(none - delegates to root)"
        pdir = "(unset)" if p["project_dir"] is None else repr(p["project_dir"])
        print(f"    {name:50s} {dist:34s} {pdir}")
