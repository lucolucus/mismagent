"""mmsite --serve — the project page kept live by a local server (stdlib only).

One server per project, on 127.0.0.1 only. `start` reuses a running one (its port file in the temp
directory, checked through /health) or launches a detached child and waits for it; it returns the
URL at once, so an agent's call never blocks. The page polls /data.json: the server recomputes the
data only when the project's signature changes (HEAD, tags, `git status`, the mtimes of
.mismagent/, the acceptance folders and the conventions skill), so an idle project costs a few git
calls per poll. With no poll for IDLE_SECONDS the server exits by itself; `stop` ends it at once.
"""
import hashlib
import http.server
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zlib

import mm

IDLE_SECONDS = 30 * 60
BASE_PORT, PORT_SPAN = 8700, 1000

def port_file(root):
    tag = "%s-%08x" % (os.path.basename(root), zlib.crc32(root.encode()))
    return os.path.join(tempfile.gettempdir(), "mismagent-%s.json" % tag)

def preferred_port(root):
    return BASE_PORT + zlib.crc32(root.encode()) % PORT_SPAN

def signature():
    """What the page depends on, cheap to compute: a change here means the data may have changed."""
    h = hashlib.sha1()
    for args in (("rev-parse", "HEAD"), ("tag", "-l"), ("status", "--porcelain")):
        h.update(mm.git(*args, check=False).encode())
    rels = ["AGENTS.md"] + [r for top in [mm.M, mm.SKILL] + mm.acceptance() for r in mm.walk(top)]
    for rel in sorted(rels):
        try:
            st = os.stat(os.path.join(mm.ROOT, rel))
        except OSError:
            continue
        h.update(("%s %d %d\n" % (rel, st.st_mtime_ns, st.st_size)).encode())
    return h.hexdigest()[:16]

def alive(root):
    """The URL of a server already serving root, or None."""
    try:
        with open(port_file(root), encoding="utf-8") as f:
            port = json.load(f)["port"]
        with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=1) as r:
            if json.load(r).get("root") == root:
                return "http://127.0.0.1:%d/" % port
    except (OSError, ValueError, KeyError):
        pass
    return None

def start(script):
    """Reuse or launch the server for mm.ROOT; -> its URL."""
    url = alive(mm.ROOT)
    if url:
        return url
    subprocess.Popen([sys.executable, script, "--serve-here"], cwd=mm.ROOT, start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        time.sleep(0.1)
        url = alive(mm.ROOT)
        if url:
            return url
    raise mm.Refused("the page server did not start (python3 mmsite.py --serve-here shows why)")

def stop():
    try:
        with open(port_file(mm.ROOT), encoding="utf-8") as f:
            pid = json.load(f)["pid"]
        os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, ValueError, KeyError):
        return False

def serve(collect, render):
    """Serve mm.ROOT in the foreground until idle, a SIGTERM or Ctrl-C."""
    state = {"sig": None, "data": None, "seen": time.time()}
    lock = threading.Lock()

    def current():
        with lock:
            sig = signature()
            if sig != state["sig"]:
                state["data"], state["sig"] = dict(collect(), sig=sig), sig
            state["seen"] = time.time()
            return state["data"]

    class Handler(http.server.BaseHTTPRequestHandler):
        def send(self, code, body, kind):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path == "/health":
                return self.send(200, json.dumps({"root": mm.ROOT}), "application/json")
            if path == "/data.json":
                data = current()
                same = query == "since=" + data["sig"]
                return self.send(200, json.dumps({"sig": data["sig"]} if same else data, ensure_ascii=False),
                                 "application/json")
            if path == "/":
                return self.send(200, render(current()), "text/html")
            self.send(404, "not found", "text/plain")

        def log_message(self, *args):
            pass

    server = None
    for port in [preferred_port(mm.ROOT) + k for k in range(20)] + [0]:
        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    with open(port_file(mm.ROOT), "w", encoding="utf-8") as f:
        json.dump({"port": server.server_address[1], "pid": os.getpid(), "root": mm.ROOT}, f)

    def idle_watch():
        while time.time() - state["seen"] < IDLE_SECONDS:
            time.sleep(30)
        server.shutdown()
    threading.Thread(target=idle_watch, daemon=True).start()
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        try:
            os.remove(port_file(mm.ROOT))
        except OSError:
            pass
    return 0
