#!/usr/bin/env python3
"""mismAgent — the build's deterministic tool (Python 3 stdlib only).

STATELESS: it computes over the feature's files and git and refuses what is unsafe; it never
guesses and never recovers on its own. Design: LOOP.md · interface and exact semantics: CLI.md.
Output: JSON on stdout (Markdown for `pack`). Exit: 0 ok · 1 refused / anomaly / gap · 2 usage error.
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board  # noqa: E402  (feature-dir resolution, frontmatter, sections)

STATES = ("todo", "doing", "done")
BLOCK_MOVES = {("todo", "doing"), ("doing", "todo"), ("doing", "done")}
NODE_STATES = ("backlog", "todo", "doing", "done")  # spike/cleanup nodes under tasks/<side>/
NODE_MOVES = {("backlog", "doing"), ("todo", "doing"), ("doing", "done")}
BLOCK_TYPES = ("aggregate", "application-service", "port", "adapter", "read-model", "ui", "scaffold")
PREFIX = "block/"  # a block's branch: block/<id>


class UsageError(Exception):
    pass


class YamlError(UsageError):
    def __init__(self, line, msg):
        super().__init__("building-blocks.yaml line %d: %s" % (line, msg))


# ---- YAML subset ------------------------------------------------------------------------------
KEY_RE = re.compile(r"""^("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^\s\[\]{}"'#,&*!|>%@`-][^:#]*?|-[^\s:][^:#]*?)"""
                    r"""\s*:(?:\s+(.*))?$""")


def _strip_comment(s):
    quote, i, prev = None, 0, ""
    while i < len(s):
        c = s[i]
        if quote:
            if quote == '"' and c == "\\":
                i += 2
                continue
            if c == quote:
                if quote == "'" and s[i + 1:i + 2] == "'":
                    i += 2
                    continue
                quote = None
        elif c in "\"'" and prev in ("", "[", "{", ",", ":", "-") and (i == 0 or s[i - 1] in " \t[{,"):
            quote = c  # only at the START of a scalar: the apostrophe in `don't` is text
        elif c == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
        if not quote and not c.isspace():
            prev = c
        i += 1
    return s.rstrip()


def _scalar(tok):
    if tok in ("", "~", "null", "Null", "NULL"):
        return None
    if tok in ("true", "True", "TRUE"):
        return True
    if tok in ("false", "False", "FALSE"):
        return False
    if re.match(r"^-?(0|[1-9][0-9]*)$", tok):
        return int(tok)
    return tok


def _unquote(tok, ln):
    if tok[0] == "'":
        return tok[1:-1].replace("''", "'")
    try:
        return json.loads(tok)
    except ValueError:
        raise YamlError(ln, "bad double-quoted string %s" % tok)


class _Flow:
    """Flow collections: [a, b], { k: v }, nested, quoted or plain scalars."""

    def __init__(self, text, ln):
        self.t, self.p, self.ln = text, 0, ln

    def err(self, msg):
        raise YamlError(self.ln, "%s (flow text: %s)" % (msg, self.t.strip()[:80]))

    def ws(self):
        while self.p < len(self.t) and self.t[self.p] in " \t\n":
            self.p += 1

    def peek(self):
        self.ws()
        return self.t[self.p] if self.p < len(self.t) else ""

    def quoted(self):
        q, start = self.t[self.p], self.p
        self.p += 1
        while self.p < len(self.t):
            c = self.t[self.p]
            if q == '"' and c == "\\":
                self.p += 2
                continue
            if c == q:
                if q == "'" and self.t[self.p + 1:self.p + 2] == "'":
                    self.p += 2
                    continue
                self.p += 1
                return _unquote(self.t[start:self.p], self.ln)
            self.p += 1
        self.err("unterminated quote")

    def plain(self, stop):
        start = self.p
        while self.p < len(self.t) and self.t[self.p] not in stop:
            if self.t[self.p] in "[{":
                self.err("flow indicator inside a plain scalar — quote it")
            if stop == ",]}:" and self.t[self.p] == ":" and self.t[self.p + 1:self.p + 2] not in (" ", ",", "}", ""):
                self.p += 1
                continue
            self.p += 1
        return self.t[start:self.p].strip()

    def value(self):
        c = self.peek()
        if c == "[":
            self.p += 1
            out = []
            while True:
                if self.peek() == "]":
                    self.p += 1
                    return out
                out.append(self.value())
                c = self.peek()
                if c == ",":
                    self.p += 1
                elif c != "]":
                    self.err("expected ',' or ']'")
        if c == "{":
            self.p += 1
            out = {}
            while True:
                if self.peek() == "}":
                    self.p += 1
                    return out
                key = self.quoted() if self.peek() in "\"'" else self.plain(",]}:")
                if self.peek() != ":":
                    self.err("expected ':' after key %r" % key)
                self.p += 1
                out[key] = None if self.peek() in (",", "}") else self.value()
                c = self.peek()
                if c == ",":
                    self.p += 1
                elif c != "}":
                    self.err("expected ',' or '}'")
        if c in "\"'":
            return self.quoted()
        if c == "":
            self.err("unexpected end of flow collection")
        return _scalar(self.plain(",]}"))


def _balanced(s):
    """Flow depth <= 0. A quote opens a quoted scalar only at the START of a scalar (after an
    indicator and spaces): the apostrophe in `[don't]` is plain text."""
    depth, quote, prev = 0, None, ""
    for i, c in enumerate(s):
        if quote:
            if c == quote and not (quote == '"' and s[i - 1] == "\\"):
                quote = None
        elif c in "\"'" and prev in ("", "[", "{", ",", ":"):
            quote = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        if not quote and not c.isspace():
            prev = c
    return depth <= 0


class _Yaml:
    def __init__(self, text):
        self.lines, self.raw = [], text.splitlines()
        for n, raw in enumerate(self.raw, 1):
            body = _strip_comment(raw)
            if not body.strip() or body.strip() in ("---", "..."):
                continue
            lead = raw[:len(raw) - len(raw.lstrip())]
            if "\t" in lead:
                raise YamlError(n, "tab in indentation")
            self.lines.append([n, len(lead), body.strip()])
        self.i = 0

    def cur(self):
        return self.lines[self.i] if self.i < len(self.lines) else None

    def parse(self):
        if not self.lines:
            return {}
        doc = self.block(self.lines[0][1])
        if self.cur():
            raise YamlError(self.cur()[0], "unexpected content (bad indentation?)")
        return doc

    def block(self, ind):
        text = self.cur()[2]
        return self.seq(ind) if text == "-" or text.startswith("- ") else self.mapping(ind)

    def seq(self, ind):
        out = []
        while self.cur() and self.cur()[1] >= ind:
            ln, i2, text = self.cur()
            if i2 > ind:
                raise YamlError(ln, "unexpected indentation")
            if not (text == "-" or text.startswith("- ")):
                break
            rest = text[1:].lstrip()
            if rest and KEY_RE.match(rest) and rest[0] not in "[{\"'":
                self.lines[self.i] = [ln, ind + len(text) - len(rest), rest]
                out.append(self.mapping(self.lines[self.i][1]))
                continue
            self.i += 1
            out.append(self.child(ind) if not rest else self.value(rest, ln, ind))
        return out

    def mapping(self, ind):
        out = {}
        while self.cur() and self.cur()[1] >= ind:
            ln, i2, text = self.cur()
            if i2 > ind:
                raise YamlError(ln, "unexpected indentation")
            if text == "-" or text.startswith("- "):
                raise YamlError(ln, "sequence item where a 'key:' was expected")
            m = KEY_RE.match(text)
            if not m:
                raise YamlError(ln, "expected 'key: value', got %r" % text[:60])
            key = m.group(1)
            key = _unquote(key, ln) if key[0] in "\"'" else key
            if key in out:
                raise YamlError(ln, "duplicate key %r" % key)
            self.i += 1
            rest = (m.group(2) or "").strip()
            if rest:
                out[key] = self.value(rest, ln, ind)
            else:
                nxt = self.cur()
                same_seq = nxt and nxt[1] == ind and (nxt[2] == "-" or nxt[2].startswith("- "))
                out[key] = self.block(nxt[1]) if same_seq else self.child(ind)
        return out

    def child(self, ind):
        nxt = self.cur()
        return self.block(nxt[1]) if nxt and nxt[1] > ind else None

    def value(self, rest, ln, ind):
        if rest[0] in "&*!%@`":
            raise YamlError(ln, "unsupported YAML construct %r" % rest[0])
        if rest[0] in "|>":
            if not re.match(r"^[|>][+-]?$", rest):
                raise YamlError(ln, "bad block scalar header")
            return self.block_scalar(rest, ln, ind)
        if rest[0] in "[{":
            while not _balanced(rest):
                if not self.cur():
                    raise YamlError(ln, "unterminated flow collection")
                rest += " " + self.cur()[2]
                self.i += 1
            f = _Flow(rest, ln)
            v = f.value()
            if f.peek():
                raise YamlError(ln, "trailing text after a flow collection — quote the scalar")
            return v
        if rest[0] in "\"'":
            f = _Flow(rest, ln)
            v = f.quoted()
            if f.peek():
                raise YamlError(ln, "trailing text after a quoted scalar")
            return v
        parts = [rest]
        while self.cur() and self.cur()[1] > ind:  # folded plain continuation
            parts.append(self.cur()[2])
            self.i += 1
        return _scalar(" ".join(parts))


    def block_scalar(self, header, ln, ind):
        """`|` / `>` read from the RAW lines: blank lines, `#` lines and quotes are content."""
        body, n = [], ln  # self.raw[n] is the first line after the header
        while n < len(self.raw):
            r = self.raw[n]
            if r.strip() and len(r) - len(r.lstrip(" ")) <= ind:
                break
            body.append(r)
            n += 1
        while self.cur() and self.cur()[0] <= n:
            self.i += 1
        filled = [r for r in body if r.strip()]
        cut = min(len(r) - len(r.lstrip(" ")) for r in filled) if filled else 0
        rows = [r[cut:] for r in body]
        trail = 0
        while rows and not rows[-1].strip():
            rows.pop()
            trail += 1
        if header[0] == "|":
            text = "\n".join(rows)
        else:  # folded: a line break is a space, a blank line a newline
            text, sep = "", ""
            for r in rows:
                if not r.strip():
                    text, sep = text + "\n", ""
                else:
                    text, sep = text + sep + r, " "
        chomp = header[1:]
        if not rows:
            return ""
        return text + ("" if chomp == "-" else "\n" * (1 + (trail if chomp == "+" else 0)))


def parse_yaml(text):
    doc = _Yaml(text).parse()
    if not isinstance(doc, dict):
        raise YamlError(1, "the document must be a mapping")
    return doc


# ---- files --------------------------------------------------------------------------------------
def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_json(path):
    try:
        return json.loads(read(path))
    except (OSError, ValueError):
        return None


def write_json(path, obj):
    """Atomic (tmp + rename): a crash leaves the old file or the new one, never half of one."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(path + ".tmp", path)


def list_items(text):
    return [re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", l).strip() for l in text.splitlines()
            if re.match(r"^\s*(?:[-*]|\d+[.)])\s+\S", l)]


class Feature:
    def __init__(self, arg):
        a = os.path.abspath(arg)
        if not os.path.isfile(os.path.join(a, "building-blocks.yaml")):
            try:
                a = os.path.dirname(board.resolve_blocks(arg))
            except SystemExit as e:
                raise UsageError(str(e))
        self.dir, self.odir = a, os.path.dirname(os.path.dirname(a))
        self.manifest_path = os.path.join(a, "building-blocks.yaml")
        if not os.path.isfile(self.manifest_path):
            raise UsageError("no building-blocks.yaml in %s" % a)
        self.manifest = m = parse_yaml(read(self.manifest_path))
        self.blocks = [b for b in (m.get("blocks") or []) if isinstance(b, dict)]
        self.boundaries = [b for b in (m.get("boundaries") or []) if isinstance(b, dict)]
        self.row = {str(b.get("id")): b for b in self.blocks}
        self.bnd = {str(b.get("id")): b for b in self.boundaries}

    def repo(self):
        """ONE repository per project: the git toplevel of the feature dir."""
        p = subprocess.run(["git", "-C", self.dir, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if p.returncode:
            raise UsageError("%s is not inside a git repository" % self.dir)
        return p.stdout.strip()

    def files(self):
        """{id: [(state, ctx, path)]} for every blocks/<ctx>/<state>/<id>.md."""
        out = {}
        for p in sorted(glob.glob(os.path.join(self.dir, "blocks", "*", "*", "*.md"))):
            state, ctx = os.path.basename(os.path.dirname(p)), os.path.basename(os.path.dirname(os.path.dirname(p)))
            if state in STATES:
                out.setdefault(os.path.basename(p)[:-3], []).append((state, ctx, p))
        return out

    def state_of(self, bid):
        f = self.files().get(bid)
        return f[0][0] if f else None

    def consumes(self, bid):
        return [str(x) for x in (self.row.get(bid, {}).get("consumes") or [])]

    def consumers(self, bd):
        return [str(c) for c in (bd.get("consumers") or [])]

    def touched(self, bid):
        """Boundaries a block touches: consumed, owned or listed as consumer."""
        return [b for b in self.boundaries if str(b.get("id")) in self.consumes(bid)
                or str(b.get("owner")) == bid or bid in self.consumers(b)]

    def integrated(self, bid):
        return load_json(os.path.join(self.dir, "integrated", bid + ".json"))

    def welded(self, bd):
        return all(self.integrated(x) for x in [str(bd.get("owner"))] + self.consumers(bd))

    def finishable(self, bid):
        return bool(self.integrated(bid)) and all(self.welded(bd) for bd in self.touched(bid))

    def nodes(self):
        """spike/cleanup nodes: [(id, state, frontmatter, body, path)] under tasks/<side>/<state>/."""
        out = []
        for p in sorted(glob.glob(os.path.join(self.dir, "tasks", "*", "*", "*.md"))):
            if os.path.basename(os.path.dirname(p)) in NODE_STATES:
                fm, body = board.parse_frontmatter(read(p))
                out.append((fm.get("id", os.path.basename(p)[:-3]), os.path.basename(os.path.dirname(p)), fm, body, p))
        return out


# ---- decision notes (F/decisions.md; the format is CLI.md's) -----------------------------------
NOTE_FIELDS = {  # field: word cap (None = only the entry cap); required unless in NOTE_OPTIONAL
    "Meta": None, "Question": 25, "Options": 40, "Hypothesis": 25, "Check": 30, "Result": 30,
    "Debate": 40, "Decision": 35, "By": None, "Docs": None, "Revisit": 20,
    "Confidence": 12, "Supersedes": None, "ADR": None}
NOTE_OPTIONAL = ("Confidence", "Supersedes", "ADR")
NOTE_CAP, TITLE_CAP = 220, 8
NOTE_HEAD = re.compile(r"^###\s+(D-\d{4})\s+·\s+(.*\S)\s*$")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+")
SHORT_FIELDS = ("Hypothesis", "Check", "Result")
SHORT_FORM = re.compile(r"^n/a\s*[—–-]+\s*decided by\s+(\S.*)$", re.I)
REF_ID = re.compile(r"\b[A-Za-z]+[-_]?\d+\b")  # REQ-3, ADR-0002, D-0004, US12


def _words(text):
    """Words excluding URLs: a markdown link counts its text, never its target."""
    return len(URL.sub(" ", MD_LINK.sub(lambda m: m.group(0)[:m.group(0).rfind("](") + 1], text)).split())


def parse_notes(path):
    """([entry], [error]) — an entry: {id, title, line, fields, text}; an error: {id, rule, error}."""
    entries, errors, cur = [], [], None

    def err(i, rule, msg):
        errors.append({"id": i, "rule": rule, "error": msg})
    for n, line in enumerate(read(path).splitlines(), 1):
        if line.startswith("###") or re.match(r"^\s+#|^#+\s*D-\d", line):  # malformed: an error, never skipped
            m = NOTE_HEAD.match(line)
            if not m:
                err("line %d" % n, "entry.header", "heading %r is not `### D-NNNN · <title>`" % line[:60])
                cur = None
                continue
            cur = {"id": m.group(1), "title": m.group(2), "line": n, "fields": {}, "text": m.group(2)}
            entries.append(cur)
            continue
        if cur is None and re.match(r"^\s*- [A-Za-z]+:", line):
            err("line %d" % n, "entry.header", "field line before any `### D-NNNN · <title>` heading")
        if cur is None or not line.strip():
            continue  # a title or intro before the first entry
        m = re.match(r"^- ([A-Za-z]+):\s*(.*?)\s*$", line)
        if not m or m.group(1) not in NOTE_FIELDS:
            err(cur["id"], "field.line", "line %d is not `- <Field>: <one line>` of a known field" % n)
        elif m.group(1) in cur["fields"]:
            err(cur["id"], "field.duplicate", "%s given twice" % m.group(1))
        else:
            cur["fields"][m.group(1)] = m.group(2)
            cur["text"] += " " + m.group(2)
    return entries, errors


def check_notes(path):
    """{ok, file, entries, active, errors} — exact checks of the decision-note format."""
    if not os.path.isfile(path):
        raise UsageError("%s not found" % path)
    entries, errors = parse_notes(path)
    base, ids, by = os.path.dirname(os.path.abspath(path)), [e["id"] for e in entries], {}

    def err(i, rule, msg):
        errors.append({"id": i, "rule": rule, "error": msg})
    for e in entries:
        i, f = e["id"], e["fields"]
        by.setdefault(i, e)
        if ids.count(i) > 1 and by[i] is not e:
            err(i, "id.duplicate", "id used by more than one entry")
        if len(e["title"].split()) > TITLE_CAP:
            err(i, "field.cap", "title > %d words" % TITLE_CAP)
        for k, cap in NOTE_FIELDS.items():
            if k not in f:
                if k not in NOTE_OPTIONAL:
                    err(i, "field.missing", "no %s" % k)
            elif not f[k]:
                err(i, "field.empty", "%s is empty" % k)
            elif cap and _words(f[k]) > cap:
                err(i, "field.cap", "%s: %d words > %d" % (k, _words(f[k]), cap))
        if _words(e["text"]) > NOTE_CAP:
            err(i, "entry.cap", "%d words > %d (URLs excluded)" % (_words(e["text"]), NOTE_CAP))
        meta = [p.strip() for p in f.get("Meta", "").split(";") if p.strip()]
        kv = dict(p.split(":", 1) for p in meta[1:] if ":" in p)
        kv = {k.strip(): v.strip() for k, v in kv.items()}
        try:
            datetime.date.fromisoformat(meta[0] if meta else "")
        except ValueError:
            err(i, "meta.date", "Meta must start with an ISO date (YYYY-MM-DD)")
        if not re.match(r"^(feature|(block|boundary):[A-Za-z0-9_.-]+)$", kv.get("scope", "")):
            err(i, "meta.scope", "scope %r is not feature | block:<id> | boundary:<id>" % kv.get("scope"))
        if kv.get("status") not in ("accepted", "superseded"):
            err(i, "meta.status", "status %r is not accepted | superseded" % kv.get("status"))
        if "sha" in kv and not re.match(r"^[0-9a-f]{7,40}$", kv["sha"]):
            err(i, "meta.sha", "sha %r is not a 7-40 hex commit id" % kv["sha"])
        if set(kv) - {"scope", "status", "sha"} or len(kv) != len(meta) - 1:
            err(i, "meta.keys", "Meta = <date>; scope: …; status: …[; sha: …] and nothing else")
        e["scope"], e["status"] = kv.get("scope"), kv.get("status")
        short = [k for k in SHORT_FIELDS if re.match(r"^n/a\b", f.get(k, ""), re.I)]
        if short:  # decided by a requirement / scope cut / ADR: all three, never mixed with an experiment
            if len(short) != len(SHORT_FIELDS):
                err(i, "short.all_three", "n/a in %s: Hypothesis, Check and Result are all "
                    "`n/a — decided by <reference>` or none is" % ", ".join(short))
            for k in short:
                m = SHORT_FORM.match(f[k])
                if not m or not (MD_LINK.search(m.group(1)) or URL.search(m.group(1)) or REF_ID.search(m.group(1))):
                    err(i, "short.reference", "%s: `n/a — decided by <reference>` names a verifiable reference "
                        "(a requirement/ADR id such as REQ-3, or a link to the scope cut)" % k)
        r = re.match(r"^(untested|inconclusive)\b[\s—:,.;-]*(.*)$", f.get("Result", ""), re.I)
        if r and not r.group(2).strip():
            err(i, "result.reason", "%s needs its reason" % r.group(1))
        if f.get("Result") and not r and not short and not (MD_LINK.search(f["Result"]) or URL.search(f["Result"])):
            err(i, "result.link", "Result carries a link to its evidence, or is `untested`/`inconclusive` — <reason>")
        if f.get("ADR") and not (MD_LINK.search(f["ADR"]) or URL.search(f["ADR"])):
            err(i, "adr.link", "ADR is the ADR's link (omit the field when there is none)")
        if f.get("By") and not all(re.search(r"(?:^|;)\s*%s:[ \t]*[^;\s]" % k, f["By"]) for k in ("decided", "recorded")):
            err(i, "by.roles", "By names `decided: <who>` and `recorded: <who>`, both non-empty")
        n_docs = len(MD_LINK.findall(f.get("Docs", ""))) + len(URL.findall(MD_LINK.sub("", f.get("Docs", ""))))
        if f.get("Docs") and not 1 <= n_docs <= 3:
            err(i, "docs.links", "Docs holds %d links, not 1-3" % n_docs)
        if f.get("Confidence") and not re.match(r"^(low|medium|high)\b[\s—:,.;-]*\w", f["Confidence"]):
            err(i, "confidence.level", "Confidence is `low|medium|high — <why>`")
        for t in MD_LINK.findall(e["text"]):
            local = t.split("#", 1)[0]
            if local and not re.match(r"^[a-z][a-z0-9+.-]*:", t) and \
                    not os.path.exists(os.path.normpath(os.path.join(base, local))):
                err(i, "link.missing", "local link %s does not exist (relative to %s)" % (t, os.path.basename(path)))
    superseded_by = {}
    for e in entries:
        if "Supersedes" not in e["fields"]:
            continue
        t = re.findall(r"D-\d{4}", e["fields"]["Supersedes"])
        if len(t) != 1 or t[0] == e["id"] or t[0] not in by or ids.index(t[0]) > ids.index(e["id"]):
            err(e["id"], "supersede.target", "Supersedes names one earlier entry id")
            continue
        superseded_by.setdefault(t[0], []).append(e["id"])
        if by[t[0]].get("status") != "superseded":
            err(t[0], "supersede.status", "superseded by %s but its status is not superseded" % e["id"])
    for e in entries:
        n = len(superseded_by.get(e["id"], []))
        if e.get("status") == "superseded" and n != 1:
            err(e["id"], "supersede.link", "status superseded needs exactly one entry that Supersedes it (%d)" % n)
    nums = [int(i[2:]) for i in ids]
    if nums != sorted(nums):
        err("-", "id.order", "ids are not in ascending order: append new entries at the end")
    active = [e["id"] for e in entries if e.get("status") == "accepted"]
    return {"ok": not errors, "file": path, "entries": len(entries), "active": len(active), "errors": errors}


def active_notes(path):
    """The accepted entries of a notes file (lenient: the validator is `why check`)."""
    out = []
    for e in parse_notes(path)[0] if os.path.isfile(path) else []:
        m = re.search(r"\bscope:\s*([^;]+?)\s*(?:;|$)", e["fields"].get("Meta", ""))
        if re.search(r"\bstatus:\s*accepted\b", e["fields"].get("Meta", "")) and m:
            out.append(dict(e, scope=m.group(1)))
    return out


def note_blocks(text):
    """[(id, block text)] — each `### D-NNNN · …` heading with its lines, trailing blanks dropped."""
    out = []
    for line in text.splitlines():
        m = NOTE_HEAD.match(line)
        if m:
            out.append([m.group(1), [line]])
        elif out:
            out[-1][1].append(line)
    return [(i, "\n".join(ls).rstrip()) for i, ls in out]


NOTE_UPDATABLE = re.compile(r"^- (Debate|Result|ADR):")


def note_update_ok(old, new):
    """An update of an existing entry: only `Debate`/`Result` change and an `ADR:` backlink is added
    (an existing one is kept as is); every other line stays identical."""
    keep = lambda b: [l for l in b.splitlines() if not NOTE_UPDATABLE.match(l)]
    adr = lambda b: [l for l in b.splitlines() if l.startswith("- ADR:")]
    return keep(old) == keep(new) and adr(old) in ([], adr(new))


def why_append(path, entry_path):
    """Append the entry file's entries to `path` — only if the result passes `why check`. The entries
    carry their ids (nothing is assigned); an identical entry already present is a no-op; the same id
    with other content is refused unless it is an update (`note_update_ok`), replaced in place. The one
    other edit to an old entry: `status: accepted` → `superseded` when a new entry `Supersedes` it.
    Nothing is written unless everything validates."""
    if not os.path.isfile(entry_path):
        raise UsageError("--entry %s not found" % entry_path)
    if not os.path.isdir(os.path.dirname(os.path.abspath(path))):
        raise UsageError("the directory of %s does not exist" % path)
    old = read(path) if os.path.isfile(path) else ""
    have, new = dict(note_blocks(old)), note_blocks(read(entry_path))
    if not new:
        return {"ok": False, "refused": "the entry file holds no `### D-NNNN · <title>` entry"}
    add, same, upd = [], [], []
    for i, block in new:
        if i not in have:
            add.append((i, block))
        elif have[i] == block:
            same.append(i)
        elif note_update_ok(have[i], block):
            upd.append((i, block))
        else:
            return {"ok": False, "refused": "%s already exists with other content: an update may only complete "
                    "Debate/Result or add the ADR backlink; a changed choice is a new entry that Supersedes it" % i}
    text, flipped = old, []
    for i, block in upd:
        text = text.replace(have[i], block, 1)
    for i, block in add:
        sup = re.search(r"^- Supersedes:.*?(D-\d{4})", block, re.M)
        if sup and sup.group(1) in have:
            b = have[sup.group(1)]
            nb = re.sub(r"^(- Meta:.*?\bstatus:\s*)accepted\b", r"\1superseded", b, count=1, flags=re.M)
            if nb != b:
                text, flipped = text.replace(b, nb, 1), flipped + [sup.group(1)]
    if add:
        text = (text.rstrip("\n") + "\n\n" if text.strip() else "") + "\n\n".join(b for _, b in add) + "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        r = check_notes(tmp)
    except UsageError:
        os.remove(tmp)
        raise
    if not r["ok"]:
        os.remove(tmp)
        return {"ok": False, "refused": "the file would not pass `why check`", "errors": r["errors"]}
    os.replace(tmp, path) if add or upd else os.remove(tmp)
    return {"ok": True, "file": path, "appended": [i for i, _ in add], "updated": [i for i, _ in upd],
            "unchanged": same, "superseded": flipped}


def cmd_why(a):
    if a.op == "append":
        if not a.entry:
            raise UsageError("why append takes --entry <file>")
        r = why_append(a.file, a.entry)
        return emit(r, 0 if r["ok"] else 1)
    if a.entry:
        raise UsageError("why check takes no --entry")
    r = check_notes(a.file)
    return emit(r, 0 if r["ok"] else 1)


# ---- lint (exact checks only; the list is CLI.md's) -----------------------------------------------
INV_RE = re.compile(r"INV[-_ ]?(\d+)(?!\d)", re.I)  # INV-12 ≡ INV_12 ≡ INV 12 ≡ INV12; never INV-1
SCAFFOLD_DOMAIN = ("invariants", "invariant_fields", "commands", "consumes", "pinned_types", "view_shape", "keys")


def coverage(row, tasks):
    """[(rule, message)] — each INV-n of the row's invariants (by number) and each command in the tasks."""
    out, text = [], "\n".join(tasks)
    invs = [str(x) for x in row.get("invariants") or []]
    have = {int(n) for n in INV_RE.findall(text)}
    for n in sorted({int(m.group(1)) for m in (INV_RE.search(x) for x in invs) if m}):
        if n not in have:
            out.append(("spec.invariants", "invariant INV-%d has no criterion in ## Tasks" % n))
    if [x for x in invs if not INV_RE.search(x)] and len(tasks) < len(invs):
        out.append(("spec.invariants", "%d criteria < %d invariants" % (len(tasks), len(invs))))
    for cmd in row.get("commands") or []:
        if str(cmd) not in text:
            out.append(("spec.commands", "command %s does not appear in ## Tasks" % cmd))
    return out


# ---- manifest render: the block files are a projection of building-blocks.yaml ---------------------
BODY_FIELDS = ("what", "sources", "tests_nl", "notes")  # rendered in the body, not the frontmatter
ORDER_FIELDS = ("after",)  # build order, not spec: out of the block file and of spec_hash
SLUG = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def yaml_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    s = str(v)
    plain = re.match(r"^[A-Za-z_][A-Za-z0-9_./-]*$", s) and _scalar(s) == s and \
        s.lower() not in ("yes", "no", "on", "off", "y", "n")
    return s if plain else json.dumps(s, ensure_ascii=False)


def boundary_shape(bd):
    """[problem] — `pinned_types` / `keys` must be mappings `{name: text}`; never coerced to `{}`."""
    return ["%s is not a mapping {name: text}" % k for k in ("pinned_types", "keys")
            if bd.get(k) is not None and not (isinstance(bd[k], dict) and all(
                str(n).strip() and not isinstance(v, (dict, list)) for n, v in bd[k].items()))]


def render_block(feat, b):
    """(text, [missing input]) — the block file `manifest render` writes for manifest row `b`."""
    i, t, missing = str(b.get("id") or ""), b.get("type"), []
    tests = b.get("tests_nl") or []
    if not SLUG.match(i):
        missing.append("id %r is not a slug" % i)
    if t not in BLOCK_TYPES:
        missing.append("type %r is not a block type" % (t,))
    if not SLUG.match(str(b.get("context") or "")):
        missing.append("context %r is not a slug" % b.get("context"))
    if not isinstance(b.get("wave"), int) or isinstance(b.get("wave"), bool):
        missing.append("wave %r is not an integer" % (b.get("wave"),))
    if (t != "scaffold" or b.get("what") is not None) and (not isinstance(b.get("what"), str) or not b["what"].strip()):
        missing.append("no what: (what to build, 1-3 sentences)")
    if not isinstance(tests, list) or any(isinstance(x, (dict, list)) for x in tests):
        missing.append("tests_nl is not a list of criteria")
        tests = []
    elif any(not str(x).strip() for x in tests):
        missing.append("tests_nl has an empty criterion")
    src = b.get("sources")
    if src is not None and not (isinstance(src, str) or isinstance(src, list) and not any(
            isinstance(x, (dict, list)) or not str(x).strip() for x in src)):
        missing.append("sources is not a text or a list of non-empty references")
    if t != "scaffold":
        if not (" ".join(map(str, src)) if isinstance(src, list) else str(src or "")).strip():
            missing.append("no sources: (the ADRs and the tactical-model section it comes from)")
        if not tests:
            missing.append("no tests_nl: (the acceptance criteria)")
        missing += [m for _, m in coverage(b, [str(x) for x in tests])]
    fm = ["---", "id: %s" % yaml_scalar(i)]
    for k, v in b.items():
        if k in BODY_FIELDS or k in ORDER_FIELDS or k == "id" or v is None:
            continue
        if isinstance(v, list) and v and not any(isinstance(x, (dict, list)) for x in v):
            fm += ["%s:" % k] + ["  - %s" % yaml_scalar(x) for x in v]
        else:
            fm.append("%s: %s" % (k, "[]" if v == [] else yaml_scalar(v)))
    out = fm + ["---", "# %s" % i, ""]
    if b.get("what") or t != "scaffold":
        out += ["## What to do", str(b.get("what") or "").strip(), ""]
    if b.get("invariants"):
        out += ["## Invariants"] + ["- %s" % x for x in b["invariants"]] + [""]
    if tests or t != "scaffold":
        out += ["## Tasks"] + ["- %s" % x for x in tests] + [""]
    touched = deps(feat, i)[0] if i in feat.row else []
    for bd in touched:
        missing += ["boundary %s: %s" % (bd.get("id"), m) for m in boundary_shape(bd)]
    if touched:
        out.append("## Dependencies")
        for bd in touched:
            bid, owner = str(bd.get("id")), str(bd.get("owner"))
            role = "owns it" if owner == i else "consumes it; owner `%s`" % owner
            out.append("- `%s` (%s) — consumers: %s · contract_test: %s" % (
                bid, role, ", ".join("`%s`" % c for c in feat.consumers(bd)) or "none", bd.get("contract_test")))
            for label, key in (("pinned", "pinned_types"), ("key", "keys")):
                rows = bd.get(key) if isinstance(bd.get(key), dict) else {}  # else: in `missing` above
                out += ["  - %s `%s`: %s" % (label, n, v) for n, v in rows.items()]
        out.append("")
    if b.get("notes"):
        out += ["## Notes", str(b["notes"]).strip(), ""]
    if src:
        out.append("Sources: %s" % (" · ".join(str(s) for s in src) if isinstance(src, list) else str(src).strip()))
    return "\n".join(out).rstrip("\n") + "\n", missing


def cmd_manifest(a):
    """Write each block file from its manifest row, in place: a block keeps its state folder, an
    unchanged file is not rewritten, a new block lands in todo/. Refuses — writing nothing — on
    incomplete rows, duplicate ids or files, and a context change (it would need a move)."""
    feat = Feature(a.feature_dir)
    files, problems, plan = feat.files(), [], []
    ids = [str(b.get("id")) for b in feat.blocks]
    problems += [{"id": d, "problem": "duplicate block id in the manifest"}
                 for d in sorted({i for i in ids if ids.count(i) > 1})]
    for b in feat.blocks:
        i, ctx = str(b.get("id")), str(b.get("context"))
        text, missing = render_block(feat, b)
        problems += [{"id": i, "problem": m} for m in missing]
        locs = files.get(i, [])
        if len(locs) > 1:
            problems.append({"id": i, "problem": "block file in several places: %s" % [l[2] for l in locs]})
        elif locs and locs[0][1] != ctx:
            problems.append({"id": i, "problem": "file under blocks/%s/, manifest context %s: a context change "
                             "needs a file move — do it by hand, then re-render" % (locs[0][1], ctx)})
        plan.append((i, locs[0][2] if locs else os.path.join(feat.dir, "blocks", ctx, "todo", i + ".md"), text))
    if problems:
        return emit({"ok": False, "refused": "incomplete or conflicting manifest: nothing written",
                     "problems": problems}, 1)
    written, unchanged = [], []
    for i, path, text in plan:
        if os.path.isfile(path) and read(path) == text:
            unchanged.append(i)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(path + ".tmp", path)
        written.append(os.path.relpath(path, feat.dir))
    return emit({"ok": True, "written": written, "unchanged": unchanged,
                 "orphans": sorted(set(files) - set(ids))})


def central_spikes(feat):
    """Open `[ ]` entries of the context-map's `## Open spikes` with `owner: <feature>` + `central: true`."""
    path, out = os.path.join(feat.odir, "context-map.md"), []
    for line in (board.section(read(path), "open spikes") if os.path.isfile(path) else "").splitlines():
        m = re.match(r"^\s*[-*]\s+\[([ xX~])\]\s+`?([A-Za-z0-9_.-]+)`?\s*:", line)
        if m:
            out.append({"id": m.group(2), "open": m.group(1) == " ", "text": line})
        elif out:
            out[-1]["text"] += " " + line
    own = r"owner:\s*`?%s`?(?![\w-])" % re.escape(os.path.basename(feat.dir))
    return [e["id"] for e in out if e["open"] and re.search(own, e["text"]) and re.search(r"central:\s*true", e["text"])]


def from_status(feat, frm):
    """A check's `from` block, resolved PROJECT-WIDE: "integrated" (any feature's integrated/<frm>.json
    or blocks/*/done/<frm>.md) · "pending" (a block row of some feature's manifest) · None (no such block)."""
    dirs = sorted(glob.glob(os.path.join(feat.odir, "features", "*")))
    if any(os.path.isfile(os.path.join(d, "integrated", frm + ".json"))
           or glob.glob(os.path.join(d, "blocks", "*", "done", frm + ".md")) for d in dirs):
        return "integrated"
    for d in dirs:
        m = os.path.join(d, "building-blocks.yaml")
        rows = feat.blocks if os.path.abspath(d) == feat.dir else \
            (parse_yaml(read(m)).get("blocks") or []) if os.path.isfile(m) else []
        if any(isinstance(r, dict) and str(r.get("id")) == frm for r in rows):
            return "pending"
    return None


def manifest_mode(feat):
    """"rendered" when any row has `what:` (its block files are `manifest render`'s projection);
    else "legacy" (hand-written block files: render checks off, never forced to render)."""
    return "rendered" if any("what" in b for b in feat.blocks) else "legacy"


def dep_cycles(feat):
    """[[id, …, id]] — cycles of the "waits for" graph: a block waits for the owners of the
    boundaries it consumes and for its `after:` blocks."""
    edges = {}
    for i in feat.row:
        waits = {str((feat.bnd.get(c) or {}).get("owner")) for c in feat.consumes(i)} | set(after_of(feat, i))
        edges[i] = sorted(x for x in waits if x in feat.row and x != i)
    color, stack, out = {}, [], []

    def visit(i):
        color[i] = 1
        stack.append(i)
        for x in edges[i]:
            if color.get(x) == 1:
                out.append(stack[stack.index(x):] + [x])
            elif not color.get(x):
                visit(x)
        stack.pop()
        color[i] = 2
    for i in sorted(edges):
        if not color.get(i):
            visit(i)
    return out


def lint(feat):
    gaps, deferred = [], []

    def gap(rule, where, text, to="build-manifest"):
        gaps.append({"rule": rule, "where": where, "gap": text, "bounce_to": to})

    seen = set()
    for kind, rows in (("block", feat.blocks), ("boundary", feat.boundaries)):
        for r in rows:
            i = str(r.get("id") or "")
            if not i:
                gap("ids.present", kind, "a %s row has no id" % kind)
            elif (kind, i) in seen:
                gap("ids.unique", i, "duplicate %s id" % kind)
            seen.add((kind, i))
    labels = feat.manifest.get("releases") if isinstance(feat.manifest.get("releases"), dict) else None
    for b in feat.blocks:
        i, t, w = str(b.get("id")), b.get("type"), b.get("wave")
        if t not in BLOCK_TYPES:
            gap("type.valid", i, "type %r is not one of %s" % (t, ", ".join(BLOCK_TYPES)))
        if not isinstance(w, int) or isinstance(w, bool) or w < 0:
            gap("wave.valid", i, "wave %r is not a non-negative integer" % (w,))
        elif (w == 0) != (t == "scaffold"):
            gap("wave.scaffold", i, "wave 0 is for scaffold blocks only (type %s, wave %s)" % (t, w))
        for c in feat.consumes(i):
            bd = feat.bnd.get(c)
            if not bd:
                gap("consumes.boundary", i, "consumes %r, which is not a boundary id" % c)
                continue
            own = feat.row.get(str(bd.get("owner")))
            if own and isinstance(own.get("wave"), int) and isinstance(w, int) and own["wave"] >= w:
                gap("wave.owner_first", i, "owner %s of %s is not in an earlier wave" % (own["id"], c))
        if t != "scaffold":
            rel = b.get("release")
            if not rel:
                gap("release.required", i, "non-scaffold block without release:")
            elif labels is not None and str(rel) not in labels:
                gap("release.declared", i, "release %s is not in the releases: section" % rel)
        else:
            domain = [k for k in SCAFFOLD_DOMAIN if b.get(k)]
            domain += ["owner of boundary %s" % bd.get("id") for bd in feat.boundaries if str(bd.get("owner")) == i]
            if domain:
                gap("scaffold.domain_free", i, "a scaffold declares no domain: %s — shared types/rules belong to "
                    "an ordinary, reviewed owner block" % ", ".join(domain))
    scaffold_open = any(b.get("type") == "scaffold" and feat.state_of(str(b.get("id"))) != "done" for b in feat.blocks)
    try:
        repo_root = feat.repo()
    except UsageError:  # lint needs no git: ADR checks then resolve against the project root
        repo_root = os.path.dirname(feat.odir)
    for bd in feat.boundaries:
        i = str(bd.get("id"))
        if str(bd.get("owner")) not in feat.row:
            gap("boundary.owner", i, "owner %r is not a block id" % bd.get("owner"))
        for c in feat.consumers(bd):
            if c not in feat.row:
                gap("boundary.consumers", i, "consumer %r is not a block id" % c)
            elif i not in feat.consumes(c):
                gap("boundary.consumers", i, "consumer %s does not list it in consumes" % c)
        for b in feat.blocks:
            if i in feat.consumes(str(b.get("id"))) and str(b.get("id")) not in feat.consumers(bd):
                gap("boundary.consumers", i, "block %s consumes it but is not in its consumers" % b.get("id"))
        if not bd.get("pinned_types"):
            gap("boundary.pinned_types", i, "no pinned_types (Published Language)", "architect")
        for m in boundary_shape(bd):
            gap("boundary.pinned_types", i, m, "architect")
        if bd.get("contract_test") not in ("invariant-test", "consumer-driven"):
            gap("boundary.contract_test", i,
                "contract_test %r is not invariant-test | consumer-driven" % bd.get("contract_test"))
    if "build_order" in feat.manifest:  # read by nothing; tolerated (deferred) on a legacy manifest
        msg = "build_order is read by nothing: order a block with `after: [block-id]`"
        if manifest_mode(feat) == "rendered":
            gap("manifest.build_order", "build_order", msg)
        else:
            deferred.append({"rule": "manifest.build_order", "where": "build_order", "until": "the manifest is rendered", "note": msg})
    for b in feat.blocks:
        i, v = str(b.get("id")), b.get("after")
        if v is None:
            continue
        if not isinstance(v, list):
            gap("after.block", i, "after %r is not a list of block ids" % (v,))
            continue
        for x in v:
            if str(x) == i or str(x) not in feat.row:
                gap("after.block", i, "after %r is not another block id" % (x,))
    for cyc in dep_cycles(feat):
        gap("after.cycle", " → ".join(cyc), "a cycle of after/boundary dependencies: nothing in it can ever be ready")
    files, rendered = feat.files(), manifest_mode(feat) == "rendered"
    for i, locs in files.items():
        if i not in feat.row:
            gap("blockfile.orphan", locs[0][2], "block file with no manifest row")
    for b in feat.blocks:
        i, locs = str(b.get("id")), files.get(str(b.get("id")), [])
        if not locs:
            gap("blockfile.exists", i, "no blocks/<ctx>/{todo,doing,done}/%s.md" % i)
            continue
        if len(locs) > 1:
            gap("blockfile.unique", i, "block file in several places: %s" % [l[2] for l in locs])
        fm, body = board.parse_frontmatter(read(locs[0][2]))
        for k in ("type", "context", "wave"):
            if str(fm.get(k, "")) != str(b.get(k, "")):
                gap("blockfile.frontmatter", i, "frontmatter %s=%r, manifest %r" % (k, fm.get(k), b.get(k)))
        if locs[0][1] != str(b.get("context")):
            gap("blockfile.context_dir", i, "file under blocks/%s/, manifest context %s" % (locs[0][1], b.get("context")))
        if "status" in fm or re.search(r"^\s*[-*] \[[ xX]\]", body, re.M):
            gap("blockfile.status_free", i, "a status: field or a checkbox in the block file")
        if rendered:  # a rendered manifest: the file is exactly `manifest render`'s projection
            text, missing = render_block(feat, b)
            if missing:
                gap("render.input", i, "; ".join(missing))
            elif read(locs[0][2]) != text:
                gap("blockfile.render", i, "the block file differs from `manifest render`: re-render, never hand-patch")
        if b.get("type") == "scaffold":
            continue
        tasks = list_items(board.section(body, "tasks"))
        if not board.section(body, "what to do"):
            gap("spec.what", i, "## What to do is missing or empty")
        if not tasks:
            gap("spec.tasks", i, "## Tasks has no criterion")
        if not re.search(r"^[\s*_>]*sources\s*:[ \t*_]*\S", body, re.M | re.I):
            gap("spec.sources", i, "no Sources: line")
        for rule, msg in coverage(b, tasks):
            gap(rule, i, msg)
    seen_adrs = set()
    for b in feat.blocks:
        for ref, path in deps(feat, str(b.get("id")))[1]:
            if not path or path in seen_adrs:
                continue
            seen_adrs.add(path)
            where = os.path.relpath(path, feat.odir)
            for c in adr_checks(path):
                if "legacy" in c:
                    gap("adr.checks", where, "enforced_by entry %s is not {check: <repo path>, from: <block>}: "
                        "migrate it with write-adr (a legacy rule is never executed)" % c["legacy"], "architect")
                    continue
                frm = c["from"]
                st = from_status(feat, frm) if frm else None
                if frm and not st:
                    gap("adr.checks", where, "enforced_by check %s: from %s is no block of any feature's manifest"
                        % (c["check"], frm), "architect")
                elif not os.path.exists(os.path.join(repo_root, c["check"])):
                    if st == "pending":
                        deferred.append({"where": where, "file": c["check"], "until": "%s is integrated" % frm})
                    elif not frm and scaffold_open:
                        deferred.append({"where": where, "file": c["check"], "until": "the wave-0 scaffold is done"})
                    else:
                        gap("adr.checks", where, "enforced_by check %s not found in the repo" % c["check"], "architect")
    nodes = {n[0]: n for n in feat.nodes() if n[2].get("type") == "spike"}
    for sid in central_spikes(feat):
        if sid not in nodes:
            gap("spikes.central_node", sid, "central context-map spike owned by this feature has no spike node")
        elif str(nodes[sid][2].get("central", "")).lower() != "true":
            gap("spikes.central_flag", sid, "spike node lacks central: true")
    notes = os.path.join(feat.dir, "decisions.md")
    if os.path.isfile(notes):  # optional: absent when nothing non-obvious was decided
        for e in check_notes(notes)["errors"]:
            gap("why." + e["rule"], "decisions.md " + e["id"], e["error"], "recorder")
        for e in active_notes(notes):
            kind, _, i = e["scope"].partition(":")
            if i and i not in (feat.row if kind == "block" else feat.bnd):
                gap("why.scope", "decisions.md " + e["id"], "scope %s: no such %s in the manifest" % (e["scope"], kind),
                    "recorder")
    return gaps, deferred


# ---- git ----------------------------------------------------------------------------------------
def git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True)
    if check and p.returncode != 0:
        raise UsageError("git %s: %s" % (" ".join(args), (p.stderr or p.stdout).strip()))
    return p


def sha(repo, ref):
    p = git(repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}", check=False)
    return p.stdout.strip() if p.returncode == 0 else None


def need_sha(repo, ref):
    return sha(repo, ref) or _raise(UsageError("ref %s not found in %s" % (ref, repo)))


def _raise(e):
    raise e


def is_ancestor(repo, a, b):
    return git(repo, "merge-base", "--is-ancestor", a, b, check=False).returncode == 0


def worktrees(repo):
    """{branch: path} of every registered worktree."""
    out, cur = {}, None
    for line in git(repo, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            cur = line[9:]
        elif line.startswith("branch refs/heads/"):
            out[line[18:]] = cur
    return out


def valid_worktree(path):
    return bool(path) and os.path.exists(os.path.join(path, ".git"))


def worktree_of(repo, branch):
    """The branch's worktree, only if its directory still exists (a deleted one does not count)."""
    p = worktrees(repo).get(branch)
    return p if valid_worktree(p) else None


def dirty(path):
    return [l for l in git(path, "status", "--porcelain").stdout.splitlines() if l.strip()]


def cand_dir(repo):
    common = git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    return os.path.join(os.path.abspath(os.path.join(repo, common)), "mismagent-candidates")


def open_candidates(repo):
    """Every trace of a candidate: metadata (also a half-written .tmp), a worktree dir, a candidate/ worktree."""
    ids = {re.sub(r"\.json(\.tmp)?$", "", os.path.basename(p)) for p in glob.glob(os.path.join(cand_dir(repo), "*"))}
    head = "branch refs/heads/candidate/"
    ids |= {l[len(head):] for l in git(repo, "worktree", "list", "--porcelain").stdout.splitlines() if l.startswith(head)}
    return sorted(ids)


# ---- dependency resolution (ONE, shared by pack and spec_hash) ---------------------------------
def adr_files(odir, refs):
    out = []
    for ref in refs:
        m = re.search(r"\d+", ref)
        hits = [p for p in sorted(glob.glob(os.path.join(odir, "decisions", "*.md")))
                if m and re.match(r"^0*%d\D" % int(m.group(0)), os.path.basename(p))]
        out.append((ref, hits[0] if hits else None))
    return out


def adr_checks(path):
    """An ADR's `enforced_by` entries: {"check", "from"} per versioned check (a repo-relative path,
    `from` optional), {"legacy": text} for anything else (a shell string, an old structured rule)."""
    text = read(path)
    end = text.find("\n---", 3) if text.startswith("---") else -1
    if end == -1:
        return []
    try:
        raw = parse_yaml(text[3:end]).get("enforced_by")
    except YamlError as e:
        return [{"legacy": "(unreadable frontmatter: %s)" % str(e).replace("building-blocks.yaml ", "")}]
    out = []
    for e in (raw if isinstance(raw, list) else [] if raw in (None, "") else [raw]):
        chk = e.get("check") if isinstance(e, dict) else None
        if isinstance(chk, str) and chk and set(e) <= {"check", "from"} and not os.path.isabs(chk) \
                and ".." not in chk.replace("\\", "/").split("/"):
            out.append({"check": chk, "from": None if e.get("from") in (None, "") else str(e["from"])})
        else:
            out.append({"legacy": e if isinstance(e, str) else json.dumps(e, ensure_ascii=False)})
    return out


def deps(feat, bid):
    """The boundaries a block touches and the ADRs it honours: its related_adrs ∪ those of the
    owners of the boundaries it consumes ∪ any ADR whose `enforced_by` check names it as `from` (it
    writes that check). A scaffold honours every block's ADRs: it writes the checks with no `from`."""
    refs = [str(r) for r in feat.row.get(bid, {}).get("related_adrs") or []]
    if feat.row.get(bid, {}).get("type") == "scaffold":
        for b in feat.blocks:
            refs += [str(r) for r in b.get("related_adrs") or [] if str(r) not in refs]
    for c in feat.consumes(bid):
        owner = feat.row.get(str((feat.bnd.get(c) or {}).get("owner")), {})
        refs += [str(r) for r in owner.get("related_adrs") or [] if str(r) not in refs]
    adrs = adr_files(feat.odir, refs)
    for p in sorted(glob.glob(os.path.join(feat.odir, "decisions", "*.md"))):  # the checks it must write
        if p not in [x for _, x in adrs] and any(c.get("from") == bid for c in adr_checks(p)):
            adrs.append((os.path.basename(p)[:-3], p))
    return sorted(feat.touched(bid), key=lambda b: str(b.get("id"))), adrs


def spec_hash(feat, bid):
    """A block: its file's content (not its folder) + manifest row + touched boundary rows + ADRs.
    Any other id (e.g. a pre-release group): its rework/<id>-*.md files."""
    h = hashlib.sha256()
    if bid not in feat.row:
        rw = sorted(glob.glob(os.path.join(feat.dir, "rework", bid + "-*.md")))
        if not rw:
            raise UsageError("%s is neither a block nor an id with rework/%s-<n>.md" % (bid, bid))
        for p in rw:
            h.update(read(p).encode())
        return h.hexdigest()
    locs = feat.files().get(bid) or _raise(UsageError("block %s has no block file" % bid))
    h.update(read(locs[0][2]).encode())
    h.update(json.dumps({k: v for k, v in feat.row[bid].items() if k not in ORDER_FIELDS}, sort_keys=True).encode())
    touched, adrs = deps(feat, bid)
    for bd in touched:
        h.update(json.dumps(bd, sort_keys=True).encode())
    for ref, path in adrs:
        h.update((read(path) if path else "missing:" + ref).encode())
    return h.hexdigest()


def review_stale(feat, bid, s):
    """[] if review-proof/<bid>.json judged sha `s` against the current spec; else the reasons."""
    old = load_json(os.path.join(feat.dir, "review-proof", bid + ".json"))
    if not old:
        return ["no review proof for %s" % bid]
    why = [] if old.get("sha") == s else ["reviewed sha %s, not %s" % (old.get("sha"), s)]
    return why + ([] if old.get("spec_hash") == spec_hash(feat, bid) else ["the spec changed after the review"])


def gate_hash(repo, gate, globs):
    h = hashlib.sha256(gate.encode())
    for g in globs:
        h.update(("\0glob:%s" % g).encode())
        for f in sorted(p for p in glob.glob(os.path.join(repo, g), recursive=True) if os.path.isfile(p)):
            h.update(("\0%s\0" % os.path.relpath(f, repo)).encode() + open(f, "rb").read())
    return h.hexdigest()


GENERATED_DIRS = {"__pycache__", "node_modules", "build", "dist", "target", "out", "obj", "coverage",
                  ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".venv", "venv", ".gradle",
                  ".next", ".nuxt", ".dart_tool", "DerivedData"}
GENERATED_EXT = (".pyc", ".pyo", ".class", ".o", ".obj", ".so", ".dylib", ".dll", ".log", ".tmp")


def suspect_generated(repo, globs):
    """["<file>: <why>"] for gate_files matches that look generated: git-ignored, under a usual
    build/cache directory, or a compiled/log extension. Diagnostic only."""
    matched = sorted({os.path.relpath(p, repo) for g in globs
                      for p in glob.glob(os.path.join(repo, g), recursive=True) if os.path.isfile(p)})
    p = subprocess.run(["git", "-C", repo, "check-ignore", "--stdin"], input="\n".join(matched), capture_output=True,
                       text=True)
    ignored = set(p.stdout.splitlines()) if p.returncode in (0, 1) else set()
    out = []
    for f in matched:
        parts = f.replace("\\", "/").split("/")
        why = ["git-ignored"] if f in ignored else []
        why += ["under %s/" % d for d in parts[:-1] if d in GENERATED_DIRS][:1]
        why += ["%s file" % os.path.splitext(f)[1]] if f.endswith(GENERATED_EXT) else []
        if why:
            out.append("%s: %s" % (f, ", ".join(why)))
    return out


# ---- commands -----------------------------------------------------------------------------------
def emit(obj, code=0):
    print(json.dumps(obj, indent=2, ensure_ascii=False))
    return code


def cmd_status(a):
    feat = Feature(a.feature_dir)
    repo = feat.repo()
    line, out = need_sha(repo, a.integration), []

    def add(kind, i, detail):
        out.append({"kind": kind, "id": i, "detail": detail})
    for bid, locs in sorted(feat.files().items()):
        if locs[0][0] == "doing" and not feat.integrated(bid) and not worktree_of(repo, PREFIX + bid):
            add("doing_without_worktree", bid, "in doing/, not integrated, no worktree on %s%s" % (PREFIX, bid))
        if locs[0][0] == "done" and not feat.finishable(bid):
            add("done_unwelded", bid, "in done/ but not integrated or a boundary it touches is not welded")
    for i, st, fm, _, _ in feat.nodes():
        if fm.get("type") == "spike" and str(fm.get("central")).lower() == "true" and st == "doing" \
                and not spike_dir_state(feat, repo, i):
            add("doing_without_worktree", i, "spike in doing/, no spikes/%s.md, no worktree on spike/%s" % (i, i))
    for br, p in sorted(worktrees(repo).items()):
        if not valid_worktree(p):
            add("missing_worktree", br, "worktree %s of %s is registered but its directory is gone" % (p, br))
    for i in open_candidates(repo):
        add("leftover_candidate", i, "candidate/%s left open: `compose abort`, then start again" % i)
    for p in sorted(glob.glob(os.path.join(feat.dir, "integrated", "*.json"))):
        i, rec = os.path.basename(p)[:-5], load_json(p) or {}
        if not (rec.get("sha") and sha(repo, rec["sha"]) and is_ancestor(repo, rec["sha"], line)):
            add("integrated_not_on_line", i, "sha %s is not an ancestor of %s" % (rec.get("sha"), a.integration))
    for p in sorted(glob.glob(os.path.join(feat.dir, "review-proof", "*.json"))):
        i, rec = os.path.basename(p)[:-5], load_json(p) or {}
        try:
            stale = rec.get("spec_hash") != spec_hash(feat, i)
        except UsageError:
            stale = True
        if stale:
            add("stale_review_proof", i, "the spec changed after the review of %s" % rec.get("sha"))
    res, work, waiting = outcome(feat, out, repo)
    return emit({"ok": not out, "anomalies": out, "outcome": res, "work": work, "waiting": waiting}, 1 if out else 0)


def lint_adrs(adir):
    """ADRs alone, before any manifest: file name, frontmatter, `enforced_by` shape. Whatever needs a
    manifest or the repo (does `from` name a block, does the check exist) is `deferred`."""
    if not os.path.isdir(adir):
        raise UsageError("--adrs %s is not a directory" % adir)
    gaps, deferred = [], []
    for p in sorted(glob.glob(os.path.join(adir, "*.md"))):
        where, text = os.path.basename(p), read(p)

        def gap(rule, msg):
            gaps.append({"rule": rule, "where": where, "gap": msg, "bounce_to": "architect"})
        if not re.match(r"^\d{4}-[A-Za-z0-9][A-Za-z0-9_.-]*\.md$", where):
            gap("adr.filename", "not NNNN-<slug>.md")
        end = text.find("\n---", 3) if text.startswith("---") else -1
        if end == -1:
            gap("adr.frontmatter", "no --- frontmatter ---")
            continue
        try:
            fm = parse_yaml(text[3:end])
        except YamlError as e:
            gap("adr.frontmatter", str(e).replace("building-blocks.yaml ", "frontmatter "))
            continue
        if not fm.get("scope"):
            gap("adr.frontmatter", "no scope:")
        if fm.get("status") not in ("proposed", "accepted", "superseded"):
            gap("adr.frontmatter", "status %r is not proposed | accepted | superseded" % fm.get("status"))
        for c in adr_checks(p):
            if "legacy" in c:
                gap("adr.checks", "enforced_by entry %s is not {check: <repo path>, from: <block>}" % c["legacy"])
            else:
                deferred.append({"where": where, "file": c["check"], "until": "`MM lint F` with a manifest: "
                                 "from %s resolves to a block, the check exists" % (c["from"] or "(none)")})
    return gaps, deferred


def cmd_lint(a):
    if bool(a.adrs) == bool(a.feature_dir):
        raise UsageError("lint takes F, or --adrs <dir> alone")
    if a.adrs:
        gaps, deferred = lint_adrs(a.adrs)
        return emit({"ok": not gaps, "gaps": gaps, "deferred": deferred}, 1 if gaps else 0)
    feat = Feature(a.feature_dir)
    gaps, deferred = lint(feat)
    return emit({"ok": not gaps, "manifest": manifest_mode(feat), "gaps": gaps, "deferred": deferred}, 1 if gaps else 0)


UNBLOCKS_LINE = re.compile(r"^-[ \t]+([A-Za-z0-9_][A-Za-z0-9_.-]*)[ \t]*$")  # a full `- <id>` line; prose ignored


def spike_unblocks(body):
    return {m.group(1) for m in (UNBLOCKS_LINE.match(l) for l in board.section(body, "unblocks").splitlines()) if m}


def after_of(feat, bid):
    """The row's `after:` ids (a malformed value is lint's `after.block`, read here as none)."""
    v = feat.row.get(bid, {}).get("after") or []
    return [str(x) for x in v] if isinstance(v, list) else []


def ready_state(feat):
    """ONE computation, shared by `ready` and `status`'s outcome."""
    rel = feat.manifest.get("releases")
    names = list(rel) if isinstance(rel, dict) else []
    names += sorted({str(b.get("release")) for b in feat.blocks if b.get("release")} - set(names),
                    key=lambda s: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)])
    spikes = [(i, spike_unblocks(body), st, fm)
              for i, st, fm, body, _ in feat.nodes() if fm.get("type") == "spike" and st != "done"]
    ready, excluded = [], []
    scaffolds = [str(b.get("id")) for b in feat.blocks if b.get("type") == "scaffold"
                 and not (feat.integrated(str(b.get("id"))) and feat.state_of(str(b.get("id"))) == "done")]
    for n, b in enumerate(feat.blocks):
        bid = str(b.get("id"))
        if feat.state_of(bid) != "todo":
            continue
        if scaffolds and b.get("type") != "scaffold":  # the scaffold goes alone, first
            excluded.append({"id": bid, "reason": "scaffold not integrated and done: " + ", ".join(scaffolds)})
            continue
        waiting = [str((feat.bnd.get(c) or {}).get("owner")) for c in feat.consumes(bid)]
        waiting = [o for o in waiting if not feat.integrated(o)]
        before = [x for x in after_of(feat, bid) if not feat.integrated(x)]
        blocking = [s[0] for s in spikes if bid in s[1]]
        if os.path.isfile(os.path.join(feat.dir, "open-questions", bid + ".md")):
            excluded.append({"id": bid, "reason": "parked: open-questions/%s.md" % bid})
            continue
        if blocking or waiting or before:
            excluded.append({"id": bid, "reason": "open spike: " + ", ".join(blocking) if blocking
                             else "owner not integrated: " + ", ".join(waiting) if waiting
                             else "after, not integrated: " + ", ".join(before)})
            continue
        r = str(b.get("release")) if b.get("release") else None
        ready.append(((b.get("wave") or 0, names.index(r) if r in names else -1, n),
                      {"id": bid, "type": b.get("type"), "wave": b.get("wave"), "release": r}))
    finishable = [str(b.get("id")) for b in feat.blocks
                  if feat.state_of(str(b.get("id"))) == "doing" and feat.finishable(str(b.get("id")))]
    return {"ready": [r for _, r in sorted(ready, key=lambda x: x[0])], "excluded": excluded,
            "finishable": finishable,
            "open_spikes": [{"id": i, "state": st, "central": str(fm.get("central")).lower() == "true",
                             "unblocks": sorted(u)} for i, u, st, fm in spikes]}


def cmd_ready(a):
    return emit(ready_state(Feature(a.feature_dir)))


PRE_LINE = re.compile(r"^\s*[-*]\s+\[([ xX~])\]\s+(.*\S)\s*$")


def open_findings(feat):
    """[(line number, text)] — the open `- [ ]` lines of F/pre-release.md (`[x]` fixed, `[~]` waived)."""
    path = os.path.join(feat.dir, "pre-release.md")
    lines = read(path).splitlines() if os.path.isfile(path) else []
    return [(n, m.group(2)) for n, m in ((n, PRE_LINE.match(l)) for n, l in enumerate(lines, 1)) if m and m.group(1) == " "]


# lint rules whose gap makes a terminal outcome false (nothing can become ready, or work is unseen)
TERMINAL_LINT = ("ids.present", "ids.unique", "consumes.boundary", "boundary.owner", "after.block", "after.cycle",
                 "blockfile.exists", "blockfile.unique", "blockfile.orphan", "spikes.central_node",
                 "spikes.central_flag")


def spike_dir_state(feat, repo, sid):
    """A spike node in doing/: "evidence" (F/spikes/<id>.md: waits on the user's closure) ·
    "running" (its spike/<id> worktree exists) · None (neither: an anomaly)."""
    if os.path.isfile(os.path.join(feat.dir, "spikes", sid + ".md")):
        return "evidence"
    return "running" if worktree_of(repo, "spike/" + sid) else None


def outcome(feat, anomalies, repo=None):
    """(outcome, work, waiting) for a runner: anomaly · done · work (something the composer can do
    now) · idle (only work waiting on a decision or an external condition). Never guesses `done`:
    before `done`/`idle`, the TERMINAL_LINT gaps are appended to `anomalies` as `lint_gap`."""
    if anomalies:
        return "anomaly", [], []
    r, work, waiting = ready_state(feat), [], []
    work += ["ready: " + x["id"] for x in r["ready"]] + ["finishable: " + x for x in r["finishable"]]
    for b in feat.blocks:
        bid = str(b.get("id"))
        if feat.state_of(bid) == "doing" and not feat.integrated(bid):
            work.append("in progress: %s (doing, not integrated)" % bid)
    waiting += ["%s: %s" % (x["id"], x["reason"]) for x in r["excluded"]]
    for p in sorted(glob.glob(os.path.join(feat.dir, "open-questions", "*.md"))):
        if os.path.basename(p)[:-3] not in feat.row or feat.state_of(os.path.basename(p)[:-3]) != "todo":
            waiting.append("open question: open-questions/%s" % os.path.basename(p))
    for i, st, fm, _, _ in feat.nodes():
        if st == "done":
            continue
        kind = fm.get("type")
        central = kind == "spike" and str(fm.get("central")).lower() == "true"
        if central and st in ("backlog", "todo"):
            work.append("central spike to run: %s" % i)
        elif central and st == "doing" and spike_dir_state(feat, repo, i) != "evidence":
            work.append("central spike running: %s (no spikes/%s.md yet)" % (i, i))
        elif kind == "cleanup" and st in ("todo", "doing"):
            work.append("cleanup: %s (%s)" % (i, st))
        else:
            waiting.append("%s %s in %s: waits on %s" % (kind or "node", i, st, "the user's closure decision"
                                                         if kind == "spike" else "its ready_when condition"))
    blocks_of = {}
    for b in feat.blocks:
        blocks_of.setdefault(str(b.get("release")), []).append(str(b.get("id")))
    for n, text in open_findings(feat):
        rel = text.split("·", 1)[0].strip()
        if all(feat.state_of(x) == "done" for x in blocks_of.get(rel, [])):
            work.append("pre-release.md line %d (%s blocks done)" % (n, rel))
        else:
            waiting.append("pre-release.md line %d: %s has blocks not done" % (n, rel))
    if work:
        return "work", work, waiting
    anomalies += [{"kind": "lint_gap", "id": g["rule"], "detail": "%s: %s" % (g["where"], g["gap"])}
                  for g in lint(feat)[0] if g["rule"] in TERMINAL_LINT]
    if anomalies:
        return "anomaly", [], []
    if waiting or any(feat.state_of(str(b.get("id"))) != "done" for b in feat.blocks):
        return "idle", [], waiting or ["blocks not done and nothing actionable"]
    return "done", [], []


def cmd_move(a):
    feat = Feature(a.feature_dir)
    locs = [(l, BLOCK_MOVES) for l in glob.glob(os.path.join(feat.dir, "blocks", "*", "*", a.id + ".md"))
            if os.path.basename(os.path.dirname(l)) in STATES]
    locs += [(l, NODE_MOVES) for l in glob.glob(os.path.join(feat.dir, "tasks", "*", "*", a.id + ".md"))
             if os.path.basename(os.path.dirname(l)) in NODE_STATES]
    if len(locs) != 1:
        raise UsageError("%s: %d block/node files found" % (a.id, len(locs)))
    (src, legal), frm = locs[0], os.path.basename(os.path.dirname(locs[0][0]))
    if (frm, a.to) not in legal:  # a refusal carries no `to`: nothing moved
        return emit({"ok": False, "id": a.id, "from": frm, "refused": "illegal transition %s->%s" % (frm, a.to)}, 1)
    if legal is BLOCK_MOVES and a.to == "done" and not feat.finishable(a.id):
        return emit({"ok": False, "id": a.id, "from": frm, "refused": "not finishable: not integrated, or a "
                     "boundary it touches is not welded (it stays in doing/)"}, 1)
    dst = os.path.join(os.path.dirname(os.path.dirname(src)), a.to, a.id + ".md")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tracked = git(os.path.dirname(src), "ls-files", "--error-unmatch", src, check=False).returncode == 0
    git(os.path.dirname(src), "mv", src, dst) if tracked else shutil.move(src, dst)
    return emit({"ok": True, "id": a.id, "from": frm, "to": a.to, "path": dst, "git": tracked})


def cmd_pack(a):
    feat = Feature(a.feature_dir)
    h = spec_hash(feat, a.id)  # refuses an id that is neither a block nor has rework/<id>-<n>.md
    root, out = os.path.dirname(feat.odir), []

    def add(title, path, body):
        out.append("## %s\n\nsource: `%s`\n\n%s\n" % (title, os.path.relpath(path, root), body.strip()))

    brief = os.path.join(feat.dir, "product-brief.md")
    if os.path.isfile(brief):
        add("Goal — product brief", brief, read(brief))
    if a.id in feat.row:
        pack_block(feat, a.id, add, out)
    else:  # a pre-release group: its spec is its rework files
        for p in sorted(glob.glob(os.path.join(feat.dir, "rework", a.id + "-*.md"))):
            add("Rework %s" % os.path.basename(p)[:-3], p, read(p))
    pack_notes(feat, a.id, add)
    found = open_findings(feat) if a.id in feat.row else []
    if found:  # advisory: never in spec_hash, never a contract change
        add("Open findings (advisory: deferred MED/LOW of the feature; they change no contract)",
            os.path.join(feat.dir, "pre-release.md"), "\n".join("- line %d: %s" % (n, t) for n, t in found))
    for x in a.extra or []:
        if not os.path.isfile(x):
            raise UsageError("--extra %s not found" % x)
        add("Extra — %s" % os.path.basename(x), os.path.abspath(x), read(x))
    print("spec_hash: %s\n\n# Context pack — %s\n\n%s" % (h, a.id, "\n".join(out)))
    return 0


def pack_block(feat, bid, add, out):
    bpath = feat.files()[bid][0][2]
    add("Block %s" % bid, bpath, read(bpath))
    touched, adrs = deps(feat, bid)
    for bd in touched:
        add("Boundary %s" % bd.get("id"), feat.manifest_path,
            "```json\n%s\n```" % json.dumps(bd, indent=2, ensure_ascii=False))
    for ref, path in adrs:
        if not path:
            out.append("## ADR %s\n\nsource: missing — no `decisions/%s-*.md`\n" % (ref, ref))
            continue
        text = read(path)
        title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), ref)
        body = "## Decision\n%s\n\n%s" % (
            board.section(text, "decision"), board.section(text, "rationale") or board.section(text, "consequences"))
        checks = []
        for c in adr_checks(path):
            if "legacy" in c:
                checks.append("- LEGACY `%s` — not a versioned check: never executed; report it (migrate with "
                              "write-adr)" % c["legacy"])
            elif c["from"] == bid:
                checks.append("- `%s` — applicable: THIS block writes it (violating + conforming fixture) and "
                              "registers it in the gate" % c["check"])
            elif not c["from"] or from_status(feat, c["from"]) == "integrated":
                checks.append("- `%s` — applicable%s" % (c["check"], " (from %s)" % c["from"] if c["from"] else ""))
            elif not from_status(feat, c["from"]):
                checks.append("- `%s` — UNRESOLVED: from %s is no block of any feature; report it" % (
                    c["check"], c["from"]))
            else:
                checks.append("- `%s` — not yet applicable: from %s, not integrated" % (c["check"], c["from"]))
        if checks:
            body += "\n\n**Checks (`enforced_by`)** — each must run in the gate, recognizably:\n" + "\n".join(checks)
        add("ADR %s" % title, path, body)
    lpath, btype = os.path.join(feat.odir, "architetture", "lessons-by-block-type.md"), str(feat.row[bid].get("type"))
    if os.path.isfile(lpath):
        keep, struck, lines = False, False, []
        for line in read(lpath).splitlines():
            if line.startswith("## "):
                keep = line[3:].strip().strip("`").lower() == btype
                continue
            if re.match(r"^\s*[-*]\s", line):
                struck = line.split(None, 1)[1].lstrip().startswith("~~") if len(line.split(None, 1)) > 1 else False
            elif not line.startswith((" ", "\t")):
                struck = False
            if keep and not struck:
                lines.append(line)
        if "\n".join(lines).strip():
            add("Lessons for %s blocks" % btype, lpath, "\n".join(lines))


def note_anchor(e):
    """The GitHub-style anchor of an entry's full heading (`D-0007 · A b` → `d-0007--a-b`)."""
    return re.sub(r"[^\w\- ]", "", ("%s · %s" % (e["id"], e["title"])).lower()).replace(" ", "-")


def pack_notes(feat, bid, add):
    """Active decision notes scoped to the feature, the block, the owners of the boundaries it
    consumes and the boundaries it touches: ID + Decision + Revisit + link. Never in spec_hash."""
    path = os.path.join(feat.dir, "decisions.md")
    scopes = {"feature"}
    if bid in feat.row:
        scopes |= {"block:" + bid} | {"boundary:%s" % b.get("id") for b in feat.touched(bid)}
        scopes |= {"block:%s" % (feat.bnd.get(c) or {}).get("owner") for c in feat.consumes(bid)}
    rows = ["- [%s](decisions.md#%s) (%s) — %s · Revisit: %s" % (
        e["id"], note_anchor(e), e["scope"], e["fields"].get("Decision", ""), e["fields"].get("Revisit", ""))
        for e in active_notes(path) if e["scope"] in scopes]
    if rows:
        add("Decision notes (active; the full entries in the source)", path, "\n".join(rows))


def cmd_diff_range(a):
    repo = git(os.getcwd(), "rev-parse", "--show-toplevel").stdout.strip()
    b, h = need_sha(repo, a.base), need_sha(repo, a.head)
    mb = git(repo, "merge-base", b, h).stdout.strip()
    files = [dict(zip(("status", "path"), l.split("\t", 1)))
             for l in git(repo, "diff", "--name-status", "--no-renames", mb, h).stdout.splitlines()]
    return emit({"base_sha": b, "head_sha": h, "merge_base": mb, "range": "%s..%s" % (mb, h), "files": files})


def cmd_proof(a):
    feat = Feature(a.feature_dir)
    repo = feat.repo()
    if a.kind == "review":
        if not a.sha or a.gate is not None or a.gate_files or (a.op == "record") != bool(a.spec_hash):
            raise UsageError("proof record review takes --sha and --spec-hash (the pack's); check takes --sha")
        s = need_sha(repo, a.sha)
        path = os.path.join(feat.dir, "review-proof", a.id + ".json")
        if a.op == "record":
            cur = spec_hash(feat, a.id)
            if cur != a.spec_hash:  # the reviewers judged another spec than the current one
                return emit({"refused": "the spec changed since the reviewed pack: re-pack, review again",
                             "reviewed": a.spec_hash, "current": cur}, 1)
            write_json(path, {"id": a.id, "sha": s, "spec_hash": cur})
            return emit({"recorded": path, "sha": s})
        why = review_stale(feat, a.id, s)
        return emit({"fresh": not why, "stale_because": why}, 1 if why else 0)
    if a.gate is None or not a.gate_files or a.sha or a.spec_hash:
        raise UsageError("proof gate takes --gate TEXT and --gate-files GLOB… (no --sha: it is a project fact)")
    cur = {"side": a.id, "gate": a.gate, "gate_files": a.gate_files, "gate_hash": gate_hash(repo, a.gate, a.gate_files)}
    empty = [g for g in a.gate_files
             if not any(os.path.isfile(p) for p in glob.glob(os.path.join(repo, g), recursive=True))]
    path = os.path.join(feat.dir, "gate-proof", a.id, "proof.json")
    if a.op == "record":
        if empty:
            raise UsageError("--gate-files %s match no file in %s" % (" ".join(empty), repo))
        write_json(path, cur)
        sus = suspect_generated(repo, a.gate_files)
        out = {"recorded": path, "proof": cur}
        if sus:  # hashed all the same: a warning, never a silent exclusion
            out["warnings"] = {"looks_generated": len(sus), "files": sus[:20], "hint": "gate_files name stable "
                               "inputs: a generated file matched here stales the proof whenever it is rebuilt"}
        return emit(out)
    olds = [(p, load_json(p) or {})
            for p in sorted(glob.glob(os.path.join(feat.odir, "features", "*", "gate-proof", a.id, "proof.json")))]
    for p, old in olds:  # a project fact: any feature's proof counts
        if old.get("gate_hash") == cur["gate_hash"]:
            return emit({"fresh": True, "stale_because": [], "proof": p})
    if not olds:
        return emit({"fresh": False, "stale_because": ["no gate proof for side %s" % a.id]}, 1)
    old = olds[0][1]
    why = ["gate string changed"] if old.get("gate") != a.gate else []
    if old.get("gate_files") != a.gate_files or \
            gate_hash(repo, old.get("gate") or "", old.get("gate_files") or []) != old.get("gate_hash"):
        why.append("gate files changed (list or content)")
    return emit({"fresh": False, "stale_because": why, "proof": olds[0][0]}, 1)


def cmd_compose(a):
    feat = Feature(a.feature_dir)
    repo = feat.repo()
    mdir = cand_dir(repo)
    path, meta_file, cand = os.path.join(mdir, a.id), os.path.join(mdir, a.id + ".json"), "candidate/" + a.id
    scaffold = feat.row.get(a.id, {}).get("type") == "scaffold"  # acceptance = the gate alone: no review proof
    if a.op == "start":
        if not (a.integration and a.branch):
            raise UsageError("compose start needs --integration and --branch")
        if open_candidates(repo):
            return emit({"refused": "a candidate is open: promote or abort it first", "open": open_candidates(repo)}, 1)
        base, tip = need_sha(repo, a.integration), need_sha(repo, a.branch)
        why = [] if scaffold else review_stale(feat, a.id, tip)
        if why:
            return emit({"refused": "no fresh review proof for %s's HEAD" % a.branch, "stale_because": why}, 1)
        meta = {"id": a.id, "integration": a.integration, "branch": a.branch, "branch_sha": tip,
                "base_sha": base, "candidate_path": path, "candidate_sha": None, "state": "starting"}
        write_json(meta_file, meta)  # BEFORE the worktree: whatever a crash leaves, abort finds it
        git(repo, "worktree", "add", "-B", cand, path, base)
        m = git(path, "merge", "--no-ff", "--no-edit", "-m", "compose %s into %s" % (a.branch, a.integration), tip,
                check=False)
        if m.returncode != 0:
            files = git(path, "diff", "--name-only", "--diff-filter=U").stdout.split()
            git(path, "merge", "--abort", check=False)
            git(repo, "worktree", "remove", "--force", path, check=False)
            os.remove(meta_file)
            return emit({"refused": "merge conflict", "conflict": files}, 1)
        meta.update(state="open", candidate_sha=sha(path, "HEAD"))
        write_json(meta_file, meta)
        return emit({k: meta[k] for k in ("candidate_path", "candidate_sha", "base_sha", "branch_sha")})
    meta = load_json(meta_file)
    if a.op == "abort":
        if a.id not in open_candidates(repo):
            return emit({"refused": "no candidate %s" % a.id}, 1)
        git(repo, "worktree", "remove", "--force", path, check=False)
        shutil.rmtree(path, ignore_errors=True)
        git(repo, "worktree", "prune", check=False)
        for f in (meta_file, meta_file + ".tmp"):
            if os.path.exists(f):
                os.remove(f)
        return emit({"aborted": a.id, "kept_branch": cand if sha(repo, cand) else None})
    if not meta or meta.get("state") != "open":
        return emit({"promoted": False, "refused": "no open candidate %s%s" % (
            a.id, " (half-created): compose abort, then start again" if a.id in open_candidates(repo) else "")}, 1)
    line, now, target = meta["integration"], sha(repo, meta["integration"]), meta["candidate_sha"]
    why = [] if now == meta["base_sha"] else ["%s moved since compose start: abort, start again from the new tip" % line]
    if not os.path.isdir(path):
        why.append("the candidate worktree is gone: abort")
    else:
        why += ["the candidate has uncommitted changes: only what was gated is promoted"] if dirty(path) else []
        why += ["the candidate's HEAD is not the recorded merge %s" % target] if sha(path, "HEAD") != target else []
    why += [] if scaffold else review_stale(feat, a.id, meta["branch_sha"])
    if why:
        return emit({"promoted": False, "refused": why}, 1)
    wt = worktree_of(repo, line)
    if wt:  # the line is checked out: fast-forward that checkout (git refuses to overwrite local changes)
        ff = git(wt, "merge", "--ff-only", target, check=False)
        if ff.returncode != 0:
            return emit({"promoted": False, "refused": [(ff.stderr or ff.stdout).strip()]}, 1)
    else:
        git(repo, "update-ref", "refs/heads/" + line, target, now)  # compare-and-swap
    write_json(os.path.join(feat.dir, "integrated", a.id + ".json"),
               {"id": a.id, "sha": meta["branch_sha"], "merge": target, "integration": line,
                "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    git(repo, "worktree", "remove", "--force", path, check=False)
    git(repo, "branch", "-D", cand, check=False)
    os.remove(meta_file)
    return emit({"promoted": True, "integration_sha": sha(repo, line)})


# ---- CLI ----------------------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(prog="mismagent.py", description="mismAgent build tool — see CLI.md")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, hlp, *pos):
        p = sub.add_parser(name, help=hlp)
        for x in pos:
            p.add_argument(x) if isinstance(x, str) else p.add_argument(x[0], choices=x[1])
        p.set_defaults(fn=fn)
        return p
    cmd("status", cmd_status, "anomalies (read-only)", "feature_dir").add_argument("--integration", required=True)
    p = cmd("lint", cmd_lint, "exact structural checks (F, or --adrs DIR before any manifest)")
    p.add_argument("feature_dir", nargs="?")
    p.add_argument("--adrs")
    cmd("why", cmd_why, "check | append decision notes", ("op", ("check", "append")), "file").add_argument("--entry")
    cmd("manifest", cmd_manifest, "render the block files from the manifest", ("op", ("render",)), "feature_dir")
    cmd("ready", cmd_ready, "ready blocks in order + finishable", "feature_dir")
    cmd("move", cmd_move, "legal state moves only", "feature_dir", "id").add_argument(
        "--to", required=True, choices=STATES)
    cmd("pack", cmd_pack, "the worker's context (Markdown)", "feature_dir", "id").add_argument("--extra", nargs="+")
    p = cmd("diff-range", cmd_diff_range, "the review range from the merge-base")
    p.add_argument("--base", required=True)
    p.add_argument("--head", required=True)
    p = cmd("proof", cmd_proof, "record | check a review or gate proof", ("op", ("record", "check")), "feature_dir",
            ("kind", ("review", "gate")), "id")
    p.add_argument("--sha")
    p.add_argument("--spec-hash")
    p.add_argument("--gate")
    p.add_argument("--gate-files", nargs="+")
    p = cmd("compose", cmd_compose, "candidate merge: start | promote | abort", ("op", ("start", "promote", "abort")),
            "feature_dir", "id")
    p.add_argument("--integration")
    p.add_argument("--branch")
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a)
    except UsageError as e:
        return emit({"error": str(e)}, 2)


if __name__ == "__main__":
    sys.exit(main())
