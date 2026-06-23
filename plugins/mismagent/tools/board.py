#!/usr/bin/env python3
"""
mismAgent board — a lightweight, READ-ONLY live view of the building blocks and their state.

It scans the feature's `blocks/<context>/{todo,doing,done}/<id>.md` (the rich, status-less block
files emitted by build-manifest) and serves a live kanban at a localhost URL. Status = the FOLDER
(todo/doing/done); the block's spec/criteria come from the file body. It NEVER writes anything —
coherent with mismAgent's invariant "only the worker-composer moves state". Zero dependencies
(Python 3 stdlib only).

Usage:
    python3 board.py [<output_dir>/<feature> | <project-root> | .] [--port N]
"""
import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATES = ("todo", "doing", "done")


# ---- parsing (no PyYAML; minimal best-effort frontmatter) -------------------
def parse_frontmatter(text):
    """Return (frontmatter_dict, body). Tolerant of missing/odd fields."""
    fm, key = {}, None
    if not text.startswith("---"):
        return fm, text
    end = text.find("\n---", 3)
    if end == -1:
        return fm, text
    block, body = text[3:end], text[end + 4:]
    for line in block.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val == "":
                fm[key] = []  # a block list may follow
            elif val.startswith("[") and val.endswith("]"):
                fm[key] = [x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()]
            else:
                fm[key] = val.strip("\"'")
        elif re.match(r"^\s*-\s+", line) and key is not None:
            fm.setdefault(key, [])
            if isinstance(fm[key], list):
                fm[key].append(re.sub(r"^\s*-\s+", "", line).strip().strip("\"'"))
    return fm, body


def section(body, name):
    """Text under a `## <name>` heading, until the next `## ` heading."""
    out, capturing = [], False
    for line in body.splitlines():
        if line.strip().startswith("## "):
            capturing = line.strip()[3:].strip().lower().startswith(name.lower())
            continue
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def bullets(text):
    return [re.sub(r"^\s*-\s+", "", l).strip()
            for l in text.splitlines() if l.strip().startswith("-")]


# ---- scanning (read-only) ---------------------------------------------------
def scan(blocks_dir):
    blocks = []
    if not os.path.isdir(blocks_dir):
        return blocks
    for ctx in sorted(os.listdir(blocks_dir)):
        ctx_dir = os.path.join(blocks_dir, ctx)
        if not os.path.isdir(ctx_dir):
            continue
        for st in STATES:
            d = os.path.join(ctx_dir, st)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(".md"):
                    continue
                try:
                    with open(os.path.join(d, fn), encoding="utf-8") as f:
                        text = f.read()
                except OSError:
                    continue
                fm, body = parse_frontmatter(text)
                blocks.append({
                    "id": fm.get("id", fn[:-3]),
                    "type": fm.get("type", ""),
                    "context": fm.get("context", ctx),
                    "wave": str(fm.get("wave", "")),
                    "consumes": fm.get("consumes", []) if isinstance(fm.get("consumes"), list) else [],
                    "status": st,
                    "cosa_fare": section(body, "cosa fare"),
                    "tasks": bullets(section(body, "task")),
                    "file": os.path.join(ctx, st, fn),
                })
    return blocks


# ---- server -----------------------------------------------------------------
PAGE = """<!doctype html><html lang=it><head><meta charset=utf-8>
<title>mismAgent board</title><style>
:root{--bg:#0e1116;--card:#1a1f27;--mut:#8b949e;--ok:#2ea043;--go:#d29922;--td:#30363d}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 -apple-system,system-ui,sans-serif;background:var(--bg);color:#e6edf3}
header{padding:12px 18px;border-bottom:1px solid #21262d;display:flex;gap:14px;align-items:baseline}
header b{font-size:16px}header span{color:var(--mut)}
.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;padding:16px}
.col h2{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin:0 0 10px;border-bottom:2px solid var(--td);padding-bottom:6px}
.col[data-s=doing] h2{color:var(--go);border-color:var(--go)}
.col[data-s=done] h2{color:var(--ok);border-color:var(--ok)}
.card{background:var(--card);border:1px solid #262c36;border-radius:8px;padding:10px 12px;margin-bottom:10px}
.card .id{font-weight:600}.badges{margin:4px 0;display:flex;gap:6px;flex-wrap:wrap}
.b{font-size:11px;color:var(--mut);background:#21262d;border-radius:5px;padding:1px 6px}
.cf{color:#c9d1d9;margin:6px 0}
.tasks{margin:6px 0 0;padding-left:16px;color:var(--mut)}.tasks li{margin:2px 0}
.empty{color:var(--mut);font-style:italic}
footer{color:var(--mut);padding:6px 18px;font-size:12px;border-top:1px solid #21262d}
</style></head><body>
<header><b>mismAgent board</b><span id=meta></span><span id=blocksdir></span></header>
<div class=cols id=cols></div>
<footer>read-only · si aggiorna ogni 1.5s · lo stato è la cartella (todo/doing/done)</footer>
<script>
const STATES=["todo","doing","done"];
function esc(s){return (s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
async function tick(){
 let d; try{d=await(await fetch("state.json",{cache:"no-store"})).json()}catch(e){return}
 document.getElementById("meta").textContent=d.blocks.length+" blocchi";
 document.getElementById("blocksdir").textContent=d.blocks_dir;
 const cols=document.getElementById("cols");cols.innerHTML="";
 for(const s of STATES){
  const bs=d.blocks.filter(b=>b.status===s).sort((a,b)=>(a.wave+a.id).localeCompare(b.wave+b.id));
  const col=document.createElement("div");col.className="col";col.dataset.s=s;
  col.innerHTML="<h2>"+s+" ("+bs.length+")</h2>";
  if(!bs.length)col.innerHTML+="<div class=empty>—</div>";
  for(const b of bs){
   const tasks=b.tasks.map(t=>"<li>"+esc(t)+"</li>").join("");
   col.innerHTML+="<div class=card><div class=id>"+esc(b.id)+"</div>"
    +"<div class=badges><span class=b>"+esc(b.type)+"</span><span class=b>"+esc(b.context)+"</span>"
    +(b.wave?"<span class=b>wave "+esc(b.wave)+"</span>":"")+"</div>"
    +(b.cosa_fare?"<div class=cf>"+esc(b.cosa_fare)+"</div>":"")
    +(tasks?"<ul class=tasks>"+tasks+"</ul>":"")+"</div>";
  }
  cols.appendChild(col);
 }
}
tick();setInterval(tick,1500);
</script></body></html>"""


def make_handler(blocks_dir):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path.startswith("/state.json"):
                self._send(200, json.dumps({"blocks_dir": blocks_dir, "blocks": scan(blocks_dir)}),
                           "application/json")
            elif self.path in ("/", "/index.html"):
                self._send(200, PAGE, "text/html; charset=utf-8")
            else:
                self._send(404, "not found", "text/plain")

        def log_message(self, *_):  # quiet
            pass
    return H


def resolve_blocks(arg):
    cand = os.path.join(arg, "blocks")
    if os.path.isdir(cand):
        return os.path.abspath(cand)
    if os.path.basename(arg.rstrip("/")) == "blocks" and os.path.isdir(arg):
        return os.path.abspath(arg)
    mm = os.path.join(arg, ".mismagent")
    if os.path.isdir(mm):
        feats = [f for f in sorted(os.listdir(mm)) if os.path.isdir(os.path.join(mm, f, "blocks"))]
        if len(feats) == 1:
            return os.path.abspath(os.path.join(mm, feats[0], "blocks"))
        if feats:
            raise SystemExit("Più feature trovate (%s). Passane una: board.py .mismagent/<feature>" % ", ".join(feats))
    raise SystemExit("Nessuna cartella blocks/ trovata sotto %r" % arg)


def main():
    ap = argparse.ArgumentParser(description="mismAgent read-only board")
    ap.add_argument("feature_dir", nargs="?", default=".",
                    help="<output_dir>/<feature>, the project root, or a blocks/ dir")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    blocks_dir = resolve_blocks(args.feature_dir)
    handler = make_handler(blocks_dir)
    port = args.port
    for attempt in range(20):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
            break
        except OSError:
            port += 1
    else:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
    print("mismAgent board → http://127.0.0.1:%d   (blocks: %s)" % (port, blocks_dir), flush=True)
    print("read-only · Ctrl-C per fermare", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
