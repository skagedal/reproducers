#!/usr/bin/env python3
"""Drives jdtls headlessly over LSP against this reproducer.

Adapted from ../../jdtls-subproject-gradle-distribution-fallback/verify.
"""
import glob, json, os, re, subprocess, tempfile, threading, time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JDTLS = os.path.expanduser("~/local/bin/jdtls")
# Workspaces must live OUTSIDE the project: an Eclipse workspace created inside
# the project being imported makes the import fail.
WS_ROOT = os.path.join(tempfile.gettempdir(), "jdtls-apt-repro-ws")

FACTORYPATH_GLOB = ("/.metadata/.plugins/org.eclipse.core.resources/.projects"
                    "/*/.factorypath")


class Jdtls:
    def __init__(self, data_dir):
        self.data = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.stderr = open(os.path.join(data_dir, "jdtls-stderr.log"), "wb")
        self.p = subprocess.Popen([JDTLS, "-data", data_dir], cwd=PROJ,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.stderr)
        self.lock = threading.Lock()
        self.log = []
        self.diagnostics = {}
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
            elif msg.get("method") == "textDocument/publishDiagnostics":
                with self.lock:
                    self.diagnostics[msg["params"]["uri"]] = msg["params"]["diagnostics"]

    def initialize(self):
        self.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "processId": os.getpid(),
            "rootUri": "file://" + PROJ,
            "workspaceFolders": [{"uri": "file://" + PROJ, "name": "repro"}],
            "initializationOptions": {"settings": {"java": {
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

    def wait_ready(self, timeout=240):
        start = time.time()
        while time.time() - start < timeout:
            with self.lock:
                if any(s.get("type") == "ServiceReady" for s in self.log):
                    return True
            time.sleep(1)
        return False

    def factory_paths(self):
        """{project name: [jar basename, ...]} in .factorypath order."""
        out = {}
        for f in sorted(glob.glob(self.data + FACTORYPATH_GLOB)):
            name = os.path.basename(os.path.dirname(f))
            ids = re.findall(r'id="([^"]*)"', open(f).read())
            out[name] = [os.path.basename(i) for i in ids]
        return out

    def wait_for_factorypath(self, timeout=300):
        start = time.time()
        while time.time() - start < timeout:
            if self.factory_paths():
                time.sleep(3)   # let it finish writing
                return True
            time.sleep(2)
        return False

    def open_document(self, rel_path):
        path = os.path.join(PROJ, rel_path)
        self.send({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
            "textDocument": {"uri": "file://" + path, "languageId": "java",
                             "version": 1, "text": open(path).read()}}})

    def errors_for(self, rel_path):
        uri = "file://" + os.path.join(PROJ, rel_path)
        with self.lock:
            return [d["message"] for d in self.diagnostics.get(uri, [])
                    if d.get("severity") == 1]

    def eclipse_log(self, pattern):
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


def gradle_processor_path():
    """The processor path in Gradle's order, straight from the build."""
    out = subprocess.run(
        [PROJ + "/gradlew", ":app:printProcessorPath", "-q", "--console=plain",
         "--no-configure-on-demand", "--init-script", PROJ + "/verify/print_processor_path.gradle"],
        cwd=PROJ, capture_output=True, text=True)
    return [l.strip() for l in out.stdout.splitlines() if l.strip().endswith(".jar")]


def build_jars():
    subprocess.run([PROJ + "/gradlew", ":processors:allJars", "-q", "--console=plain"],
                   cwd=PROJ, capture_output=True, text=True)
