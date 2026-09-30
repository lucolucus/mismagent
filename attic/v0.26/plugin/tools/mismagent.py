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

    def welded(self, bd, for_bid=None):
        """Owner and consumers integrated; `for_bid`: only the consumers of its release or an earlier
        one — a later release's consumer adds a pair (proven by its contract test when it integrates),
        it never reopens work already done."""
        cons = self.consumers(bd) if for_bid is None else own_consumers(self, bd, for_bid)
        return all(self.integrated(x) for x in [str(bd.get("owner"))] + cons)

    def finishable(self, bid):
        return bool(self.integrated(bid)) and all(self.welded(bd, bid) for bd in self.touched(bid))

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


def parse_notes(path, text=None):
    """([entry], [error]) — an entry: {id, title, line, fields, text}; an error: {id, rule, error}.
    `text`: the content to parse instead of the file's."""
    entries, errors, cur = [], [], None

    def err(i, rule, msg):
        errors.append({"id": i, "rule": rule, "error": msg})
    for n, line in enumerate((read(path) if text is None else text).splitlines(), 1):
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


def check_notes(path, text=None):
    """{ok, file, entries, active, errors} — exact checks of the decision-note format. `text`: check this
    content as if it were `path` (links resolved from its directory), without writing anything."""
    if text is None and not os.path.isfile(path):
        raise UsageError("%s not found" % path)
    entries, errors = parse_notes(path, text)
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
        if not re.match(r"^(feature|(block|boundary|release):[A-Za-z0-9_.-]+)$", kv.get("scope", "")):
            err(i, "meta.scope", "scope %r is not feature | block:<id> | boundary:<id> | release:<Rn>" % kv.get("scope"))
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


def why_append(path, entry_path, entry_text=None, dry=False):
    """Append the entry file's entries to `path` — only if the result passes `why check`. The entries
    carry their ids (nothing is assigned); an identical entry already present is a no-op; the same id
    with other content is refused unless it is an update (`note_update_ok`), replaced in place. The one
    other edit to an old entry: `status: accepted` → `superseded` when a new entry `Supersedes` it.
    Nothing is written unless everything validates."""
    if entry_text is None and not os.path.isfile(entry_path):
        raise UsageError("--entry %s not found" % entry_path)
    if not os.path.isdir(os.path.dirname(os.path.abspath(path))):
        raise UsageError("the directory of %s does not exist" % path)
    old = read(path) if os.path.isfile(path) else ""
    have, new = dict(note_blocks(old)), note_blocks(read(entry_path) if entry_text is None else entry_text)
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
    mdir = os.path.dirname(os.path.abspath(path))
    if os.path.isfile(os.path.join(mdir, "building-blocks.yaml")):  # a feature's notes: scopes checked first
        feat = Feature(mdir)
        bad = [{"id": i, "rule": "meta.scope", "error": why} for i, block in add + upd
               for m in [re.search(r"^- Meta:.*?\bscope:\s*([^;\s]+)", block, re.M)] if m
               for why in [scope_problem(feat, m.group(1))] if why]
        if bad:
            return {"ok": False, "refused": "a scope names nothing of the manifest: nothing written", "errors": bad}
    r = check_notes(path, text)  # in memory, links resolved from path's directory
    if not r["ok"]:
        return {"ok": False, "refused": "the file would not pass `why check`", "errors": r["errors"]}
    if (add or upd) and not dry:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    return {"ok": True, "file": path, "appended": [i for i, _ in add], "updated": [i for i, _ in upd],
            "unchanged": same, "superseded": flipped}


def handoff_notes(handoff):
    """([(local id, block)], [error]) — a worker handoff's decision entries: everything before its
    return (the first `RESULT:` line), an optional `# ` title aside; each other line is a note heading,
    a `- Field:` line or blank — anything else is an error, never dropped."""
    entries, errors = [], []
    for n, line in enumerate(read(handoff).splitlines(), 1):
        if line.startswith("RESULT:"):
            break
        m = NOTE_HEAD.match(line)
        if m:
            entries.append([m.group(1), [line]])
        elif re.match(r"^- [A-Za-z]+:", line) and entries:
            entries[-1][1].append(line)
        elif line.strip() and not (line.startswith("# ") and not entries):
            errors.append({"id": "line %d" % n, "rule": "handoff.line", "error": "neither a `### D-NNNN · <title>` "
                           "heading nor a `- <Field>: <one line>` line of a note: %r" % line[:60]})
    return [(i, "\n".join(ls)) for i, ls in entries], errors


def why_import(path, handoff, dry=False):
    """Import a handoff's entries into `path`. Its heading ids are LOCAL: the composer assigns the final
    ids (the next free ones, in order), references to local ids are rewritten, and the mapping is kept
    in `handoff-imports.json` beside `path` (key: the handoff's file name) — a retry reuses it, so an
    imported entry is a no-op or an allowed update (`why_append`), cycles included. `dry`: validate in
    memory, write nothing."""
    if not os.path.isfile(handoff):
        raise UsageError("--handoff %s not found" % handoff)
    entries, errors = handoff_notes(handoff)
    if errors:
        return {"ok": False, "refused": "the handoff's notes section is malformed: nothing written", "errors": errors}
    old = read(path) if os.path.isfile(path) else ""
    ledger_path = os.path.join(os.path.dirname(os.path.abspath(path)), "handoff-imports.json")
    ledger = load_json(ledger_path) or {}
    key = os.path.basename(handoff)
    mapping = dict(ledger.get(key) or {})
    have = {i for i, _ in note_blocks(old)}
    mapping = {k: v for k, v in mapping.items() if v in have}  # a mapping whose entry is gone is void
    nxt = max([int(i[2:]) for i in have], default=0)
    for i, _ in entries:
        if i not in mapping:
            nxt += 1
            mapping[i] = "D-%04d" % nxt
    remap = lambda body: re.sub(r"\bD-\d{4}\b", lambda x: mapping.get(x.group(0), x.group(0)), body)
    out = []
    for i, b in entries:
        head, _, body = b.partition("\n")
        out.append(re.sub(r"^###\s+D-\d{4}", "### " + mapping[i], head, count=1) + ("\n" + remap(body) if body else ""))
    if not out:
        return {"ok": True, "file": path, "mapping": {}, "appended": [], "updated": [], "unchanged": []}
    r = why_append(path, handoff, entry_text="\n\n".join(out) + "\n", dry=dry)
    if r["ok"] and not dry and (r["appended"] or r["updated"] or ledger.get(key) != mapping):
        ledger[key] = mapping
        write_json(ledger_path, ledger)
    return dict(r, file=path, mapping=mapping)


def why_template(path):
    """A valid entry skeleton (it passes `why check` as printed): the next id of `path` (D-0001 when
    none), today, scope feature; every `<…>` states its field's rule."""
    ids = [int(e["id"][2:]) for e in parse_notes(path)[0]] if path and os.path.isfile(path) else []
    caps = lambda k: "≤ %d words" % NOTE_FIELDS[k]
    f = [("Meta", "%s; scope: feature; status: accepted" % datetime.date.today().isoformat()),
         ("Question", "<the question, one line, %s>" % caps("Question")),
         ("Options", "<2-3 real alternatives and why each loses, %s>" % caps("Options")),
         ("Hypothesis", "<what should hold, %s>" % caps("Hypothesis")),
         ("Check", "<how it was checked and what counts as success, %s>" % caps("Check")),
         ("Result", "untested — <reason; or the result with a link to its evidence, %s>" % caps("Result")),
         ("Debate", "none"),
         ("Decision", "<the choice, %s>" % caps("Decision")),
         ("By", "decided: <who>; recorded: <who>"),
         ("Docs", "[<doc title>](https://example.invalid/replace-with-1-to-3-links)"),
         ("Revisit", "<when to reopen it, %s>" % caps("Revisit"))]
    return "### D-%04d · <title, ≤ %d words>\n%s" % (max(ids, default=0) + 1, TITLE_CAP,
                                                    "".join("- %s: %s\n" % kv for kv in f))


def cmd_why(a):
    if a.op == "template":
        if a.entry:
            raise UsageError("why template takes no --entry")
        sys.stdout.write(why_template(a.file))
        return 0
    if not a.file:
        raise UsageError("why %s takes <file>" % a.op)
    if a.op == "append":
        if not a.entry or a.handoff or a.into:
            raise UsageError("why append takes --entry <file>")
        r = why_append(a.file, a.entry)
        return emit(r, 0 if r["ok"] else 1)
    if a.op == "import":
        if not a.handoff or a.entry or a.into:
            raise UsageError("why import takes <decisions.md> --handoff <file>")
        r = why_import(a.file, a.handoff)
        return emit(r, 0 if r["ok"] else 1)
    if a.entry or a.handoff:
        raise UsageError("why check takes <file> [--into <decisions.md>]")
    r = why_import(a.into, a.file, dry=True) if a.into else check_notes(a.file)
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


COMP_ROOT = re.compile(r"composition_root:[ \t*_`'\"]*([^\s`'\"*#][^\s`'\"*]*)")  # same line, a path token
COMP_LINE = ("Composition: extend the existing composition at %s in place — never wrap it; the other blocks of "
             "this release publish what you wire.")


FENCE = re.compile(r"^```ya?ml[^\n]*\n(.*?)^```", re.M | re.S)


def yaml_section(path, key):
    """The value of top-level `key` in the first fenced YAML block of a Markdown file that has it."""
    for m in FENCE.finditer(read(path)) if os.path.isfile(path) else []:
        try:
            doc = parse_yaml(m.group(1))
        except YamlError:
            continue
        if key in doc:
            return doc[key]
    return None


def composition_root(feat, side=None):
    """The composition root of `side`: `composition_roots: {<side>: <path>}` in a YAML block of the
    trunk's architecture.md, else the legacy `composition_root: <path>` line (one side); None when absent."""
    p = os.path.join(feat.odir, "architecture.md")
    roots = yaml_section(p, "composition_roots")
    if isinstance(roots, dict) and roots:
        r = roots.get(side)
        return r.strip() if isinstance(r, str) and r.strip() else None
    sides = yaml_section(os.path.join(feat.odir, "profile.md"), "sides")
    if side is not None and isinstance(sides, dict) and len(sides) > 1:
        return None  # a single `composition_root:` line never serves several sides
    for line in read(p).splitlines() if os.path.isfile(p) else []:
        m = None if line.lstrip().startswith("#") else COMP_ROOT.search(line)
        if m:
            return m.group(1)
    return None


def compositions(feat):
    """The valid `composition: true` rows (a scaffold never is one)."""
    return [b for b in feat.blocks if b.get("composition") is True and b.get("type") != "scaffold"]


def earlier_compositions(feat, b):
    """[id] — the composition blocks of the same side in releases before `b`'s, nearest release first
    (release order: the `releases:` keys, then the other labels)."""
    order = release_names(feat)
    rel = str(b.get("release"))
    if rel not in order:
        return []
    out = [x for x in compositions(feat) if x.get("side") == b.get("side") and str(x.get("release")) in order
           and order.index(str(x.get("release"))) < order.index(rel)]
    return [str(x.get("id")) for x in sorted(out, key=lambda x: -order.index(str(x.get("release"))))]


def code_paths_ok(cp):
    """None, or a list of repo-relative paths (no absolute path, no `..`)."""
    return cp is None or (isinstance(cp, list) and all(
        isinstance(x, str) and x.strip() and not x.startswith("/") and ".." not in x.split("/") for x in cp))


def render_block(feat, b):
    """(text, [missing input]) — the block file `manifest render` writes for manifest row `b`."""
    i, t, missing = str(b.get("id") or ""), b.get("type"), []
    tests = b.get("tests_nl") or []
    if b.get("composition") is not None and not isinstance(b["composition"], bool):
        missing.append("composition %r is not true | false" % (b["composition"],))
    if not code_paths_ok(b.get("code_paths")):
        missing.append("code_paths %r is not a list of repo-relative paths" % (b.get("code_paths"),))
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
        out += ["## What to do", str(b.get("what") or "").strip()]
        if b.get("composition") is True and t != "scaffold":  # the wiring obligation reaches the worker via the spec
            out.append(COMP_LINE % (composition_root(feat, b.get("side")) or "<composition_root in architecture.md>"))
        out.append("")
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
        if not code_paths_ok(b.get("code_paths")):
            gap("code_paths.shape", i, "code_paths %r is not a list of repo-relative paths" % (b.get("code_paths"),))
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
            if feat.state_of(i) != "done" and code_paths_ok(b.get("code_paths")) and b.get("code_paths") \
                    and all(feat.integrated(x) for x in after_of(feat, i)):  # before: the code it extends is still owed
                try:
                    repo = feat.repo()
                except UsageError:
                    repo = None
                gone = [x for x in b["code_paths"] if repo and not git(repo, "ls-tree", "HEAD", "--", x.rstrip("/"),
                                                                        check=False).stdout.strip()]
                if gone:
                    gap("code_paths.exist", i, "code_paths name no existing file or directory: %s (they are the "
                        "existing code the block changes; new files need no entry)" % ", ".join(gone))
            if rel and (labels is None or str(rel) in labels) and feat.state_of(i) != "done":
                order = release_names(feat)
                later = [r for r in order[order.index(str(rel)) + 1:] if str(rel) in order
                         and re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(r), str(b.get("notes") or ""))]
                if later:
                    gap("release.later_work", i, "its notes name later release %s: that release's work is a block "
                        "of that release (`after:` this one), never a note on this one" % ", ".join(later))
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
    gaps += composition_gaps(feat)
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
            why = scope_problem(feat, e["scope"])
            if why:
                gap("why.scope", "decisions.md " + e["id"], why, "recorder")
    gaps += release_gaps(feat)
    return gaps, deferred


def composition_gaps(feat):
    """lint's composition rules: `composition` is a boolean, never on a scaffold; at most one
    `composition: true` block per (release, side), whose `after:` lists every other non-scaffold block
    of that (release, side); any such block needs `composition_root:` in architecture.md. A manifest
    without the flag has none of these gaps."""
    gaps, comps = [], []

    def gap(rule, where, text, to="build-manifest"):
        gaps.append({"rule": rule, "where": where, "gap": text, "bounce_to": to})
    for b in feat.blocks:
        i, v = str(b.get("id")), b.get("composition")
        if v is None:
            continue
        if not isinstance(v, bool):
            gap("composition.valid", i, "composition %r is not true | false" % (v,))
        elif v and b.get("type") == "scaffold":
            gap("composition.valid", i, "a scaffold is never the composition block: the composition wires a release")
        elif v:
            comps.append(b)
    key = lambda b: (str(b.get("release")), str(b.get("side")) if b.get("side") is not None else "(no side)")
    groups = {}
    for b in comps:
        groups.setdefault(key(b), []).append(str(b.get("id")))
    for (rel, side), ids in sorted(groups.items()):
        if len(ids) > 1:
            gap("composition.unique", ", ".join(ids), "release %s, side %s: %d composition blocks — exactly one "
                "wires a release into the app" % (rel, side, len(ids)))
    for b in comps:
        i = str(b.get("id"))
        sibs = [str(x.get("id")) for x in feat.blocks if x is not b and x.get("type") != "scaffold"
                and x.get("composition") is not True and key(x) == key(b)]
        missing = [s for s in sibs if s not in after_of(feat, i)]
        if missing:
            gap("composition.last", i, "after: lacks %s — the composition block comes after every other block of "
                "its (release, side)" % ", ".join(missing))
    for b in comps:
        prev = earlier_compositions(feat, b)
        if prev and prev[0] not in after_of(feat, str(b.get("id"))):
            gap("composition.chain", str(b.get("id")), "after: lacks %s — the composition block of the nearest "
                "earlier release on the same side: the root is extended release after release, in order" % prev[0])
    for side in sorted({str(b.get("side")) for b in comps if not composition_root(feat, b.get("side"))}):
        gap("composition.root", "architecture.md", "a block of side %s has composition: true but "
            "<output_dir>/architecture.md names no composition root for it (`composition_roots: {<side>: <path>}`, "
            "or one `composition_root: <path>` for a single side)" % side, "architect")
    return gaps


def scope_problem(feat, scope):
    """None if a decision note's scope names something of the manifest; else why not."""
    kind, _, i = scope.partition(":")
    have = feat.row if kind == "block" else feat.bnd if kind == "boundary" else \
        release_names(feat) if kind == "release" else None
    return None if not i or have is None or i in have else "scope %s: no such %s in the manifest" % (scope, kind)


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


def group_spec(feat, gid):
    """A pre-release group: (its rework/<gid>-*.md files, the frontmatter of <gid>-1.md). Its
    `blocks:` must be manifest rows; a legacy group (no frontmatter) has no blocks."""
    rw = sorted(glob.glob(os.path.join(feat.dir, "rework", gid + "-*.md")))
    if not rw:
        raise UsageError("%s is neither a block nor an id with rework/%s-<n>.md" % (gid, gid))
    first = os.path.join(feat.dir, "rework", gid + "-1.md")
    fm = board.parse_frontmatter(read(first))[0] if os.path.isfile(first) else {}
    blocks = fm.get("blocks") if isinstance(fm.get("blocks"), list) else []
    ghost = [b for b in blocks if b not in feat.row]
    if ghost:
        raise UsageError("rework/%s-1.md names blocks not in the manifest: %s" % (gid, ", ".join(ghost)))
    return rw, dict(fm, blocks=blocks)


def deps_many(feat, bids):
    """deps() of several blocks, each boundary and ADR once."""
    touched, adrs, seen = {}, [], set()
    for bid in bids:
        t, a = deps(feat, bid)
        touched.update((str(bd.get("id")), bd) for bd in t)
        for ref, path in a:
            if (path or "missing:" + ref) not in seen:
                seen.add(path or "missing:" + ref)
                adrs.append((ref, path))
    return [touched[k] for k in sorted(touched)], adrs


def own_consumers(feat, bd, bid):
    """The consumers of boundary `bd` that belong to block `bid`'s spec (and weld): a consumer's is
    itself — other consumers never bind it; the owner's are those of its release or an earlier one (a
    later release's consumer is a new pair, proven by its own contract test when it integrates)."""
    if str(bd.get("owner")) != bid:
        return [c for c in feat.consumers(bd) if c == bid]
    order, mine = release_names(feat), str(feat.row.get(bid, {}).get("release"))
    if mine not in order:
        return feat.consumers(bd)
    return [c for c in feat.consumers(bd) if str(feat.row.get(c, {}).get("release")) not in order
            or order.index(str(feat.row[c].get("release"))) <= order.index(mine)]


def spec_view(feat, bid, text):
    """A block file as its spec: each Dependencies line lists only the block's own consumers."""
    for bd in feat.touched(bid):
        cons = own_consumers(feat, bd, bid)
        if cons != feat.consumers(bd):
            text = re.sub(r"(?m)^(- `%s` \([^)]*\) — consumers: ).*?( · contract_test: )" % re.escape(str(bd.get("id"))),
                          lambda m: m.group(1) + (", ".join("`%s`" % c for c in cons) or "none") + m.group(2), text)
    return text


def spec_hash(feat, bid, own=True):
    """A block: its file's content (not its folder) + manifest row + touched boundary rows + ADRs.
    Any other id (a pre-release group): its rework/<id>-*.md files + the same dependencies of the
    blocks its first rework file names, each once."""
    h = hashlib.sha256()
    if bid in feat.row:
        bids = [bid]
    else:
        rw, fm = group_spec(feat, bid)
        for p in rw:
            h.update(read(p).encode())
        bids = sorted(fm["blocks"])
    for b in bids:
        locs = feat.files().get(b) or _raise(UsageError("block %s has no block file" % b))
        text = read(locs[0][2])
        h.update((spec_view(feat, b, text) if own else text).encode())
        h.update(json.dumps({k: v for k, v in feat.row[b].items() if k not in ORDER_FIELDS}, sort_keys=True).encode())
    touched, adrs = deps_many(feat, bids)
    for bd in touched:  # a later release's consumer is not in an earlier block's spec
        if own and "consumers" in bd and len(bids) == 1:
            bd = dict(bd, consumers=own_consumers(feat, bd, bids[0]))
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
    return why + ([] if spec_current(feat, bid, old.get("spec_hash")) else ["the spec changed after the review"])


def spec_current(feat, bid, recorded):
    """A recorded spec hash still judges the current spec: today's hash, or the one a proof recorded
    before later-release consumers left a block's spec (v0.25.4) while nothing else changed."""
    return recorded in (spec_hash(feat, bid), spec_hash(feat, bid, own=False))


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


# ---- codemap: where the existing code is (discovery, never authority) ----------------------------
def codemap(odir, ref, side=None, module=None, files=False):
    """Markdown: per side (profile `sides:`), per module (architecture.md `modules:` — {id, side, root,
    entry_files}) else per top directory, the files git tracks at `ref`, entry files marked. A module's
    contract stays the project's (its dependency lint); this only says where to start reading."""
    p = subprocess.run(["git", "-C", odir, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if p.returncode:
        raise UsageError("%s is not inside a git repository" % odir)
    repo, s = p.stdout.strip(), need_sha(p.stdout.strip(), ref)
    skip = os.path.relpath(os.path.abspath(odir), repo).replace(os.sep, "/") + "/"
    tracked = [f for f in git(repo, "ls-tree", "-r", "--name-only", s).stdout.splitlines()
               if not f.startswith(skip) and not f.startswith(".worktrees/")]
    sides = yaml_section(os.path.join(odir, "profile.md"), "sides")
    sides = {str(k): str((v or {}).get("path", ".")) for k, v in sides.items()} if isinstance(sides, dict) else {"-": "."}
    mods = yaml_section(os.path.join(odir, "architecture.md"), "modules")
    mods = [m for m in mods if isinstance(m, dict) and m.get("root")] if isinstance(mods, list) else []
    under = lambda f, root: root in (".", "", "./") or f == root.rstrip("/") or f.startswith(root.rstrip("/") + "/")
    note = "" if mods else " No `modules:` in architecture.md: modules unknown, grouped by directory."
    out = ["# Code map at %s" % s[:12], "",
           "Discovery only: a module's contract is the project's (its dependency lint enforces it); entry files (*) are where to start "
           "reading." + note, ""]
    for sd, root in sorted(sides.items()):
        if side and sd != side:
            continue
        mine = [f for f in tracked if under(f, root)]
        out += ["## Side %s (`%s`, %d files)" % (sd, root, len(mine)), ""]
        own = [m for m in mods if m.get("side") is None or str(m.get("side")) == sd]
        if own:  # this side's modules, as declared
            groups = [(str(m.get("id")), str(m["root"]), [str(e) for e in m.get("entry_files") or []]) for m in own]
        else:  # this side's top directories, under its root
            pre = "" if root in (".", "", "./") else root.rstrip("/") + "/"
            groups = [(d, pre + d, []) for d in sorted({f[len(pre):].split("/")[0] for f in mine if "/" in f[len(pre):]})]
        seen = set()
        for mid, base, entries in groups:
            if module and mid != module:
                continue
            fs = [f for f in mine if under(f, base)]
            seen.update(fs)
            out.append("- **%s** `%s` — %d files%s" % (mid, base, len(fs), "; entry: " + ", ".join(
                "`%s`" % e for e in entries) if entries else ""))
            if files:
                out += ["  - %s`%s`" % ("* " if any(under(f, e) for e in entries) else "", f) for f in fs]
        rest = [f for f in mine if f not in seen]
        if rest and not module:
            shown = rest if files else rest[:12]
            out.append("- (outside any module) — %d files: %s" % (len(rest), ", ".join("`%s`" % f for f in shown)
                                                                   + ("" if len(shown) == len(rest) else " …")))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def cmd_codemap(a):
    sys.stdout.write(codemap(os.path.abspath(a.output_dir), a.ref, a.side, a.module, a.files))
    return 0


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
        if locs[0][0] == "done" and not (feat.integrated(bid) and all(feat.integrated(str(bd.get("owner")))
                                                                      for bd in feat.touched(bid))):
            # a consumer added after it finished is a new pair, proven by its contract test when it integrates
            add("done_unwelded", bid, "in done/ but it or the owner of a boundary it touches is not integrated")
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
            stale = not spec_current(feat, i, rec.get("spec_hash"))
        except UsageError:
            stale = True
        if stale:
            add("stale_review_proof", i, "the spec changed after the review of %s" % rec.get("sha"))
    res, work, waiting = outcome(feat, out, repo, line)
    return emit({"ok": not out, "anomalies": out, "outcome": res, "work": work, "waiting": waiting,
                 "resume": resume_candidates(feat, repo)}, 1 if out else 0)


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
        w = b.get("wave") if isinstance(b.get("wave"), int) else 0  # a wave is a barrier within its side: a
        before += [str(x.get("id")) for x in feat.blocks  # shared owner (kernel, schema) is used implicitly
                   if isinstance(x.get("wave"), int) and x["wave"] < w and x.get("type") != "scaffold"
                   and (x.get("side") is None or b.get("side") is None or x.get("side") == b.get("side"))
                   and not feat.integrated(str(x.get("id"))) and str(x.get("id")) not in before]
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
    feat = Feature(a.feature_dir)
    try:
        repo = feat.repo()
    except UsageError:
        repo = None
    return emit(dict(ready_state(feat), resume=resume_candidates(feat, repo)))


PRE_LINE = re.compile(r"^(\s*[-*]\s+\[)([ xX~])(\]\s+)(.*\S)\s*$")


# ---- findings and releases (F/pre-release.md; the format and the policy are CLI.md's) --------------
SEVS, UNWAIVABLE = ("HIGH", "FAIL", "MED", "LOW"), ("HIGH", "FAIL")
LOCATOR = re.compile(r"^(\S+?)(?::\d+(?:-\d+)?|#\S+)$|^([^\s:#,]+)$")  # file:line[-line] · path#symbol · path
MARKS = {" ": "open", "x": "closed", "X": "closed", "~": "waived"}
FINDING_FIELDS = ("release", "block", "sev", "locator", "issue", "reviewer", "date")
RECORD_KEYS = {"close": ("line", "finding", "sha", "by", "evidence"),
               "waive": ("line", "finding", "by", "consent", "reason", "risk", "revisit")}
TAG_KEY = "mismagent-release"


def finding_id(fields):
    """The identity of a finding: a hash of its seven original fields (never the mark, the line
    number or a trailing annotation) — the line number is only a selector."""
    return hashlib.sha256("\x1f".join(fields).encode()).hexdigest()[:12]


def parse_findings(feat):
    """[{line, mark, text, release, finding, block, sev, locator, …}] of the `- [ ]` lines of
    F/pre-release.md; a malformed line carries `error` (and no `finding`)."""
    path = os.path.join(feat.dir, "pre-release.md")
    out = []
    for n, l in enumerate(read(path).splitlines() if os.path.isfile(path) else [], 1):
        m = PRE_LINE.match(l)
        if not m:
            continue
        parts = [p.strip() for p in m.group(4).split("·")]
        f = {"line": n, "mark": MARKS[m.group(2)], "text": m.group(4), "release": parts[0]}
        if len(parts) < len(FINDING_FIELDS) or not all(parts[:len(FINDING_FIELDS)]):
            f["error"] = "not `<release> · <id> · <sev> · <locator> · <issue> · <reviewer> · <date>`"
        elif parts[2] not in SEVS:
            f["error"] = "severity %r is not %s" % (parts[2], " | ".join(SEVS))
        elif not LOCATOR.match(parts[3]):
            f["error"] = "locator %r is not `file:line[-line]`, `path#symbol` or `path`" % parts[3]
        else:
            f.update(zip(FINDING_FIELDS, parts))
            f["finding"] = finding_id(parts[:len(FINDING_FIELDS)])
        out.append(f)
    return out


def release_names(feat, findings=()):
    """The releases in order: the `releases:` keys, then the other labels (blocks', findings')."""
    rel = feat.manifest.get("releases")
    names = [str(x) for x in rel] if isinstance(rel, dict) else []
    labels = {str(b.get("release")) for b in feat.blocks if b.get("release")} | {f["release"] for f in findings}
    return names + sorted(labels - set(names), key=lambda s: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)])


def decisions_path(feat, rn):
    return os.path.join(feat.dir, "release-decisions", rn + ".md")


def read_records(feat, rn):
    """(doc, [record], [error]) of F/release-decisions/<rn>.md — its ONE ```json block
    `{"records": [...]}`. doc is None when the block is absent (no file, or legacy prose only) or
    unreadable (then an error says so); only valid records are returned."""
    path = decisions_path(feat, rn)
    if not os.path.isfile(path):
        return None, [], []
    found = re.findall(r"^```json[ \t]*\n(.*?)^```[ \t]*$", read(path), re.S | re.M)
    if len(found) > 1:
        return None, [], ["%d ```json blocks: exactly one holds the records" % len(found)]
    if not found:
        return None, [], []
    try:
        doc = json.loads(found[0])
    except ValueError as e:
        return None, [], ["the ```json block does not parse: %s" % e]
    if not isinstance(doc, dict) or not isinstance(doc.get("records"), list):
        return None, [], ["the ```json block is not {\"records\": [...]}"]
    recs, errs = [], []
    for k, r in enumerate(doc["records"]):
        bad = record_problem(r)
        if bad:
            errs.append("record %d: %s" % (k, bad))
        else:
            recs.append(r)
    return doc, recs, errs


def record_problem(r):
    """None for a valid record; else what is wrong with it."""
    keys = RECORD_KEYS.get(r.get("action")) if isinstance(r, dict) else None
    return "not an object with action close|waive" if keys is None else next(
        ("%s missing or empty" % x for x in keys[1:] + ("at",) if not isinstance(r.get(x), str) or not r[x].strip()),
        None)


def on_line(feat, repo, line_sha, bid):
    """Block `bid` is integrated: its integrated/ record exists and — given the line — its sha is a
    commit on the line (the same rule as the `integrated_not_on_line` anomaly)."""
    rec = feat.integrated(bid)
    if not rec:
        return False
    if not (repo and line_sha):
        return True
    s = rec.get("sha") if isinstance(rec, dict) else None
    return bool(isinstance(s, str) and sha(repo, s) and is_ancestor(repo, s, line_sha))


def locator_path(locator):
    m = LOCATOR.match(locator)
    return (m.group(1) or m.group(2)) if m else locator


def closure_problem(feat, repo, line_sha, f, r):
    """None if the close record `r` still holds for finding `f` on the line tip; else why not."""
    ev = r["evidence"]
    epath = os.path.join(feat.dir, ev.split("#", 1)[0])
    if not re.match(r"^release-evidence/%s\.md(#\S*)?$" % re.escape(f["release"]), ev) or not os.path.isfile(epath):
        return "closure evidence %s is not an existing release-evidence/%s.md" % (ev, f["release"])
    if f["finding"] not in read(epath):
        return "closure evidence %s does not name finding %s" % (ev, f["finding"])
    if not repo:
        return None
    s = sha(repo, r["sha"])
    if not s:
        return "closure sha %s not found" % r["sha"]
    if line_sha and not is_ancestor(repo, s, line_sha):
        return "closure sha %s is not on the integration line" % r["sha"][:12]
    if line_sha and git(repo, "diff", "--quiet", s, line_sha, "--", locator_path(f["locator"]), check=False).returncode:
        return "%s changed after the closure at %s: verify again" % (locator_path(f["locator"]), r["sha"][:12])
    return None


def release_tags(repo):
    """[{tag, target, release, merge_to, from, integration, decided, consent}] — the annotated tags
    `release confirm` wrote."""
    fmt = "%(refname:short)%1f%(objecttype)%1f%(*objectname)%1f%(contents)%1e"
    out = []
    for rec in git(repo, "for-each-ref", "--format=" + fmt, "refs/tags").stdout.split("\x1e"):
        parts = rec.lstrip("\n").split("\x1f")
        if len(parts) != 4 or parts[1] != "tag":
            continue
        m = re.search(r"^%s: (\S+)$" % TAG_KEY, parts[3], re.M)
        b = re.search(r"^merge-to: (\S+)(?: \(from (\S+)\))?", parts[3], re.M)
        i = re.search(r"^integration: (\S+) @ ", parts[3], re.M)
        if m:
            out.append({"tag": parts[0], "target": parts[2], "release": m.group(1), "merge_to": b.group(1) if b else None,
                        "from": b.group(2) if b else None, "integration": i.group(1) if i else None,
                        **{k: (re.search(r"^%s: (.*)$" % k, parts[3], re.M) or [None, None])[1]
                           for k in ("decided", "consent")}})
    return out


def release_key(feat, rn):
    return "%s/%s" % (os.path.basename(feat.dir), rn)


def confirmed(feat, rn, repo, tags):
    """The confirmation of Rn: a `release confirm` tag of it whose commit is on its merge-to branch."""
    for t in tags:
        if t["release"] == release_key(feat, rn) and t["merge_to"] and sha(repo, t["merge_to"]) \
                and is_ancestor(repo, t["target"], t["merge_to"]):
            return {"tag": t["tag"], "sha": t["target"], "merge_to": t["merge_to"]}
    return None


def release_eval(feat, rn, repo=None, line_sha=None, findings=None, tags=None):
    """ONE evaluation of release Rn, shared by `status` and the `release` commands. Policy: an open
    HIGH/FAIL/MED blocks; a MED is freed only by a verified close or a valid waiver record, a
    HIGH/FAIL only by a verified close; a LOW never blocks (advisory, and shown as a view to every
    later release — never copied). Releasable ⇔ Rn has blocks, all done and integrated, nothing
    blocking, its records file readable."""
    findings = parse_findings(feat) if findings is None else findings
    doc, recs, errors = read_records(feat, rn)
    last = {r["finding"]: r for r in recs}
    order = release_names(feat, findings)
    earlier = order[:order.index(rn)] if rn in order else []
    blocks = [str(b.get("id")) for b in feat.blocks if str(b.get("release")) == rn and b.get("type") != "scaffold"]
    waiting = [] if blocks else ["%s has no blocks" % rn]
    integ = {b: on_line(feat, repo, line_sha, b) for b in blocks}
    for b in blocks:
        st = feat.state_of(b)
        if st != "done" or not integ[b]:
            waiting.append("block %s: %s%s" % (b, st, "" if integ[b] else ", not integrated" if not feat.integrated(b)
                                               else ", its integrated sha is not on the line"))
    blocking, advisory, waived, closed = [], [], [], []

    def view(f, **kw):
        v = {"line": f["line"], "finding": f.get("finding"), "sev": f.get("sev"), "block": f.get("block"),
             "locator": f.get("locator"), "issue": f.get("issue")}
        return dict(v, **kw)
    for f in findings:
        if f["release"] != rn:
            if f["release"] in earlier and f.get("sev") == "LOW" and f["mark"] == "open":
                advisory.append(view(f, release=f["release"]))
            continue
        if "error" in f:
            blocking.append(view(f, reason="malformed line: " + f["error"]))
            continue
        r = last.get(f["finding"])
        if f["mark"] == "closed" and r and r["action"] == "close":
            why = closure_problem(feat, repo, line_sha, f, r)
            if not why:
                closed.append(view(f, sha=r["sha"], by=r["by"], evidence=r["evidence"]))
                continue
        elif f["mark"] == "waived" and r and r["action"] == "waive" and f["sev"] not in UNWAIVABLE:
            waived.append(view(f, by=r["by"], reason=r["reason"], revisit=r["revisit"], consent=r["consent"]))
            continue
        else:
            why = "open" if f["mark"] == "open" else "a HIGH/FAIL is never waived" if f["mark"] == "waived" and \
                f["sev"] in UNWAIVABLE else "marked [%s] without a valid %s record%s" % (
                    "x" if f["mark"] == "closed" else "~", "close" if f["mark"] == "closed" else "waive",
                    " (a legacy waiver: record it with `release waive`)" if f["mark"] == "waived" else "")
        if f["sev"] == "LOW":
            advisory.append(view(f, release=rn))
        else:
            blocking.append(view(f, reason=why))
    conf = confirmed(feat, rn, repo, release_tags(repo) if tags is None else tags) if repo else None
    gaps = ["%s: %s: %s" % (g["rule"], g["where"], g["gap"]) for g in release_gaps(feat, only=rn)]
    return {"release": rn, "sha": line_sha, "blocks": [{"id": b, "state": feat.state_of(b),
                                                        "integrated": integ[b]} for b in blocks],
            "blocking": blocking, "advisory": advisory, "waived": waived, "closed": closed, "waiting": waiting,
            "errors": errors, "gaps": gaps,
            "releasable": bool(blocks) and not waiting and not blocking and not errors and not gaps,
            "confirmed": conf}


def release_gaps(feat, only=None):
    """lint's release rules: malformed lines; records ↔ marks (every `[x]`/`[~]` has a matching last
    record, every record a line of its release carrying its mark); readable records files. `only`:
    one release's gaps."""
    gaps, findings = [], parse_findings(feat)

    def gap(rule, where, text):
        gaps.append({"rule": rule, "where": where, "gap": text, "bounce_to": "composer"})
    for f in findings:
        if "error" in f and only in (None, f["release"]):
            gap("release.finding", "pre-release.md line %d" % f["line"], f["error"])
    files = [os.path.basename(p)[:-3] for p in glob.glob(os.path.join(feat.dir, "release-decisions", "*.md"))]
    for rn in sorted(set(release_names(feat, findings)) | set(files)):
        if only not in (None, rn):
            continue
        doc, recs, errs = read_records(feat, rn)
        for e in errs:
            gap("release.record", "release-decisions/%s.md" % rn, e)
        mine = {f["finding"]: f for f in findings if f.get("finding") and f["release"] == rn}
        last = {}
        for r in recs:
            if r["finding"] not in mine:
                gap("release.record_orphan", "release-decisions/%s.md" % rn,
                    "%s record for finding %s: no such %s line in pre-release.md" % (r["action"], r["finding"], rn))
            last[r["finding"]] = r
        for h, f in sorted(mine.items(), key=lambda x: x[1]["line"]):
            want, r = {"closed": "close", "waived": "waive"}.get(f["mark"]), last.get(h)
            if want and (not r or r["action"] != want):
                gap("release.unverified", "pre-release.md line %d" % f["line"], "marked [%s] without a %s record in "
                    "release-decisions/%s.md%s" % ("x" if want == "close" else "~", want, rn,
                                                   ": a legacy mark, kept but unverified" if not r else ""))
            elif not want and r:
                gap("release.record_orphan", "pre-release.md line %d" % f["line"],
                    "a %s record but the line is open" % r["action"])
    return gaps


# lint rules whose gap makes a terminal outcome false (nothing can become ready, or work is unseen)
TERMINAL_LINT = ("ids.present", "ids.unique", "consumes.boundary", "boundary.owner", "after.block", "after.cycle",
                 "blockfile.exists", "blockfile.unique", "blockfile.orphan", "spikes.central_node",
                 "spikes.central_flag", "composition.valid", "composition.unique", "composition.last",
                 "composition.root", "composition.chain")


def spike_dir_state(feat, repo, sid):
    """A spike node in doing/: "evidence" (F/spikes/<id>.md: waits on the user's closure) ·
    "running" (its spike/<id> worktree exists) · None (neither: an anomaly)."""
    if os.path.isfile(os.path.join(feat.dir, "spikes", sid + ".md")):
        return "evidence"
    return "running" if worktree_of(repo, "spike/" + sid) else None


def resume_candidates(feat, repo):
    """[{id, branch, worktree, uncommitted, attempt, commits, handoff[, progress]}] — blocks in doing/,
    not integrated: facts for resuming them (never a diagnosis: a dirty tree also describes a worker
    still running). `attempt` = 1 + rework cycles; `commits` = commits only block/<id> holds (on no
    other branch but its own candidate);
    `handoff` = .worktrees/returns/<feature>/<id>-<attempt>.md if it exists, else null; `result` = the
    last `RESULT:` its worker appended there on returning (null: it never returned). `progress` when a checkpoint was recorded: {attempt, head, next, fresh} (a stale one is
    reported, not an anomaly)."""
    out = []
    for b in feat.blocks:
        bid = str(b.get("id"))
        if feat.state_of(bid) == "doing" and not feat.integrated(bid):
            wt = worktree_of(repo, PREFIX + bid) if repo else None
            r = {"id": bid, "branch": PREFIX + bid, "worktree": wt, "uncommitted": len(dirty(wt)) if wt else None}
            r["attempt"] = len(rework_cycles(feat, bid)[0]) + 1
            n = git(repo, "rev-list", "--count", PREFIX + bid, "--not", "--exclude=" + PREFIX + bid,
                    "--exclude=candidate/*", "--branches", check=False) if repo else None
            r["commits"] = int(n.stdout) if n is not None and n.returncode == 0 else None
            h = os.path.join(repo, ".worktrees", "returns", os.path.basename(feat.dir),
                             "%s-%d.md" % (bid, r["attempt"])) if repo else None
            r["handoff"] = h if h and os.path.isfile(h) else None
            got = re.findall(r"(?m)^RESULT:\s*([A-Z-]+)", read(h)) if r["handoff"] else []
            r["result"] = got[-1] if got else None
            rec, fresh = progress_of(feat, repo, bid)
            if rec:
                r["progress"] = {"attempt": rec.get("attempt"), "head": rec.get("head"),
                                 "next": (rec.get("checkpoint") or {}).get("next"), "fresh": fresh}
            out.append(r)
    return out


# ---- progress: a worker's checkpoint at a green AC boundary (F/progress/<id>.json) ------------------
CHECKPOINT_REQUIRED, CHECKPOINT_OPTIONAL = ("done", "next"), ("tests", "decisions", "deviations", "notes")


def progress_path(feat, bid):
    return os.path.join(feat.dir, "progress", bid + ".json")


def progress_of(feat, repo, bid):
    """(record, fresh) of F/progress/<bid>.json — (None, False) when absent, unreadable, or the block is
    integrated (then it is history, ignored). fresh ⇔ its head is still block/<bid>'s tip, its
    spec_hash the current one, and the block's worktree clean (a change after it = unverified work)."""
    rec = load_json(progress_path(feat, bid))
    if not isinstance(rec, dict) or not isinstance(rec.get("checkpoint"), dict) or feat.integrated(bid):
        return None, False
    try:
        cur = spec_hash(feat, bid)
    except UsageError:
        cur = None
    tip = sha(repo, PREFIX + bid) if repo else None
    wt = worktree_of(repo, PREFIX + bid) if repo else None
    return rec, bool(tip and rec.get("head") == tip and cur and rec.get("spec_hash") == cur
                     and not (wt and dirty(wt)))


def load_checkpoint(raw):
    """(checkpoint, problem) — --json: `-` (stdin), a file, or the JSON object inline."""
    try:
        text = sys.stdin.read() if raw == "-" else raw if raw.lstrip().startswith("{") else \
            read(raw) if os.path.isfile(raw) else None
    except OSError as e:
        return None, "--json %s: %s" % (raw, e)
    if text is None:
        return None, "--json %s: neither `-`, a file, nor a JSON object" % raw
    try:
        cp = json.loads(text)
    except ValueError as e:
        return None, "--json does not parse: %s" % e
    if not isinstance(cp, dict):
        return None, "--json is not a JSON object"
    extra = sorted(set(cp) - set(CHECKPOINT_REQUIRED + CHECKPOINT_OPTIONAL))
    if extra:
        return None, "unknown keys %s (allowed: %s)" % (", ".join(extra), ", ".join(CHECKPOINT_REQUIRED + CHECKPOINT_OPTIONAL))
    if not isinstance(cp.get("done"), list):
        return None, "`done` is missing or not a list (the acceptance criteria done, green)"
    if not isinstance(cp.get("next"), str) or not cp["next"].strip():
        return None, "`next` is missing or not a non-empty string (the next action)"
    bad = [k for k in CHECKPOINT_OPTIONAL if k in cp and not isinstance(cp[k], (str, list))]
    return (None, "%s: a string or a list" % ", ".join(bad)) if bad else (cp, None)


def cmd_progress(a):
    """Record a worker's checkpoint: refused — nothing written — unless the block is a manifest row in
    doing/, --head is block/<id>'s tip, its worktree clean, --spec-hash the current one, the checkpoint
    well-formed, every --extra a file, and there is progress since the previous record."""
    feat = Feature(a.feature_dir)
    repo, bid = feat.repo(), a.id
    if bid not in feat.row:
        return emit({"ok": False, "refused": "nothing written", "problems": [
            "%s is not a block of the manifest: checkpoints are for manifest blocks only" % bid]}, 1)
    problems = [] if feat.state_of(bid) == "doing" else ["block %s is in %s, not doing/" % (bid, feat.state_of(bid))]
    problems += ["block %s is already integrated" % bid] if feat.integrated(bid) else []
    tip, head = sha(repo, PREFIX + bid), sha(repo, a.head)
    if not tip:
        problems.append("no branch %s%s" % (PREFIX, bid))
    elif head != tip:
        problems.append("--head %s is not the tip of %s%s (%s): commit, then record the tip" % (a.head, PREFIX, bid, tip[:12]))
    wt = worktree_of(repo, PREFIX + bid)
    if wt and dirty(wt):
        problems.append("the worktree %s has uncommitted or untracked changes: commit everything before a "
                        "checkpoint" % wt)
    extras = [os.path.abspath(x) for x in dict.fromkeys(a.extra or [])]
    problems += ["--extra %s not found" % x for x in extras if not os.path.isfile(x)]
    try:
        cur = spec_hash(feat, bid)
    except UsageError as e:
        cur = None
        problems.append(str(e))
    if cur and a.spec_hash != cur:
        problems.append("--spec-hash is not the block's current spec hash %s: the spec changed, re-pack" % cur)
    cp, why = load_checkpoint(a.json)
    problems += [why] if why else []
    path = progress_path(feat, bid)
    old = load_json(path)
    old = old if isinstance(old, dict) else {}
    n = old.get("attempt")
    n = n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0
    if cp and tip and old.get("head") == tip and (old.get("checkpoint") or {}).get("done") == cp["done"]:
        problems.append("no progress since attempt %d: same head, same done list" % n)
    if problems:
        return emit({"ok": False, "refused": "nothing written", "problems": problems}, 1)
    attempt = n + 1
    write_json(path, {"head": tip, "spec_hash": cur, "attempt": attempt, "checkpoint": cp, "extras": extras})
    return emit({"ok": True, "id": bid, "file": path, "attempt": attempt})


def outcome(feat, anomalies, repo=None, line_sha=None):
    """(outcome, work, waiting) for a runner: anomaly · done · work (something the composer can do
    now) · idle (only work waiting on a decision or an external condition). Never guesses `done`:
    before `done`/`idle`, the TERMINAL_LINT gaps are appended to `anomalies` as `lint_gap`."""
    if anomalies:
        return "anomaly", [], []
    r, work, waiting = ready_state(feat), [], []
    work += ["ready: " + x["id"] for x in r["ready"]] + ["finishable: " + x for x in r["finishable"]]
    for x in resume_candidates(feat, repo):
        p = x.get("progress")
        work.append("resume: %s (doing, not integrated; worktree %s, %s uncommitted, attempt %s, %s commits, %s%s)" % (
            x["id"], x["worktree"] or "none", "?" if x["uncommitted"] is None else x["uncommitted"], x["attempt"],
            "?" if x["commits"] is None else x["commits"], "returned %s" % x["result"] if x["result"] else "no return",
            "; checkpoint attempt %s, %s" % (p["attempt"], "fresh" if p["fresh"] else "stale") if p else ""))
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
    findings = parse_findings(feat)
    tags = release_tags(repo) if repo else []
    for rn in release_names(feat, findings):
        ev = release_eval(feat, rn, repo, line_sha, findings, tags)
        n = len(ev["blocking"])
        if ev["confirmed"]:
            continue
        if ev["gaps"]:  # record ↔ mark gaps: the composer repairs them now, whatever the blocks' state
            work.append("release %s: %d record/mark gaps to repair (`lint`)" % (rn, len(ev["gaps"])))
        if not ev["blocks"]:  # not started: its lines wait, nothing is actionable
            waiting.append("release %s: no blocks%s" % (rn, " (%d blocking lines wait)" % n if n else ""))
        elif ev["waiting"]:
            if n:
                waiting.append("release %s: %d blocking lines wait for its blocks" % (rn, n))
        elif n:
            work.append("release %s: %d blocking lines (`release list`)" % (rn, n))
        elif not ev["gaps"]:
            waiting.append("release %s: releasable, awaiting the user's confirmation (`release confirm`)" % rn)
    if work:
        return "work", work, waiting
    anomalies += [{"kind": "lint_gap", "id": g["rule"], "detail": "%s: %s" % (g["where"], g["gap"])}
                  for g in lint(feat)[0] if g["rule"] in TERMINAL_LINT]
    if anomalies:
        return "anomaly", [], []
    if waiting or any(feat.state_of(str(b.get("id"))) != "done" for b in feat.blocks):
        return "idle", [], waiting or ["blocks not done and nothing actionable"]
    return "done", [], []


def relink_notes(feat, src, dst):
    """Rewrite F/decisions.md links to a file that a state move relocated (src → dst): a note cites
    the file where it was when written. Returns the number of links rewritten."""
    npath = os.path.join(feat.dir, "decisions.md")
    if not os.path.isfile(npath):
        return 0
    old, new = (os.path.relpath(x, feat.dir).replace(os.sep, "/") for x in (src, dst))
    text = read(npath)
    out, n = re.subn(r"\]\((?:\./)?%s(#[^)]*)?\)" % re.escape(old), lambda m: "](%s%s)" % (new, m.group(1) or ""), text)
    if n:
        write_text(npath, out)
    return n


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
    out = {"ok": True, "id": a.id, "from": frm, "to": a.to, "path": dst, "git": tracked,
           "relinked": relink_notes(feat, src, dst)}
    prog = progress_path(feat, a.id)
    if legal is BLOCK_MOVES and a.to == "done" and os.path.isfile(prog):  # a finished block's checkpoint is spent
        if git(feat.dir, "ls-files", "--error-unmatch", prog, check=False).returncode == 0:
            git(feat.dir, "rm", "-q", "-f", prog)
        else:
            os.remove(prog)
        out["progress_removed"] = prog
    return emit(out)


def cmd_pack(a):
    feat = Feature(a.feature_dir)
    h = spec_hash(feat, a.id)  # refuses an id that is neither a block nor has rework/<id>-<n>.md
    root, out = os.path.dirname(feat.odir), []
    extras = list(dict.fromkeys(os.path.abspath(x) for x in a.extra or []))

    def add(title, path, body):
        out.append("## %s\n\nsource: `%s`\n\n%s\n" % (title, os.path.relpath(path, root), body.strip()))

    if a.id in feat.row:  # a fresh checkpoint first: the re-dispatched worker resumes from it
        try:
            repo = feat.repo()
        except UsageError:
            repo = None
        rec, fresh = progress_of(feat, repo, a.id)
        if rec and fresh:  # the dispatch's extras survive the checkpoint: packed below, each once
            extras = list(dict.fromkeys([os.path.abspath(x) for x in a.extra or []] +
                                        [x for x in rec.get("extras") or [] if isinstance(x, str)]))
            add("Checkpoint — attempt %s (resume from it; never in spec_hash)" % rec.get("attempt"),
                progress_path(feat, a.id), checkpoint_md(rec))
    brief = os.path.join(feat.dir, "product-brief.md")
    if os.path.isfile(brief):
        add("Goal — product brief", brief, read(brief))
    if a.id in feat.row:
        pack_deps(feat, [a.id], add, out, writer=a.id)
    else:  # a pre-release group: its rework files, then its blocks' specs and dependencies, each once
        rw, fm = group_spec(feat, a.id)
        for p in rw:
            add("Rework %s" % os.path.basename(p)[:-3], p, read(p))
        pack_deps(feat, fm["blocks"], add, out, writer=None)
    ex = existing_code(feat, [a.id] if a.id in feat.row else group_spec(feat, a.id)[1]["blocks"])
    if ex:
        add("Existing code (paths; read before writing — never in spec_hash)", os.path.join(feat.odir, "architecture.md"), ex)
    pack_notes(feat, a.id, add)
    if a.id in feat.row:  # advisory: never in spec_hash, never a contract change
        mine, others = block_findings(feat, a.id)
        if mine or others:
            add("Open findings (advisory: deferred MED/LOW of this block and its boundary neighbours; they change "
                "no contract)", os.path.join(feat.dir, "pre-release.md"), "\n".join(
                    ["- line %d: %s" % (f["line"], f["text"]) for f in mine] +
                    ["%d other open findings in the feature (not relevant to this block)" % others] * bool(others)))
    for x in extras:
        if not os.path.isfile(x):
            raise UsageError("--extra %s not found" % x)
        add("Extra — %s" % os.path.basename(x), os.path.abspath(x), read(x))
    print("spec_hash: %s\n\n# Context pack — %s\n\n%s" % (h, a.id, "\n".join(out)))
    return 0


def existing_code(feat, bids):
    """The pack's `## Existing code` body: the blocks' `code_paths` (to change) and, read-only, the entry
    files of the modules serving their (context, side) and their consumed owners' (a module serves the
    contexts it lists in `contexts:`, else the one named like its id; no `side:` = every side), plus a
    composition block's side root and its side's entry files. Paths only."""
    mods = yaml_section(os.path.join(feat.odir, "architecture.md"), "modules")
    mods = [m for m in mods if isinstance(m, dict)] if isinstance(mods, list) else []
    serves = lambda m, ctx, side: ctx in [str(x) for x in m.get("contexts") or [m.get("id")]] and \
        (m.get("side") is None or side is None or str(m.get("side")) == str(side))
    change, read_, comp = [], [], []
    for bid in bids:
        row = feat.row.get(bid, {})
        cp = row.get("code_paths")
        change += [str(x) for x in cp if str(x) not in change] if isinstance(cp, list) else []
        side = row.get("side")
        pairs = {(str(row.get("context")), side)} | {
            (str(o.get("context")), o.get("side", side)) for c in feat.consumes(bid)
            for o in [feat.row.get(str((feat.bnd.get(c) or {}).get("owner")), {})]}
        picked = [m for m in mods if any(serves(m, c, sd) for c, sd in pairs)]
        if row.get("composition") is True and row.get("type") != "scaffold":
            r = composition_root(feat, side)
            comp += ["- composition root (%s): `%s`" % (side or "-", r)] if r else []
            picked += [m for m in mods if m not in picked and (m.get("side") is None or str(m.get("side")) == str(side))]
        for m in picked:
            for e in m.get("entry_files") or []:
                if str(e) not in read_ and str(e) not in change:
                    read_.append(str(e))
    if not (change or read_ or comp):
        return "" if mods else "No module index in architecture.md: `MM codemap <output_dir> --ref <B>` shows the code."
    return "\n".join(["To change (`code_paths`):"] + ["- `%s`" % x for x in change] * bool(change) +
                     (["- none"] if not change else []) + ["", "To read, never write (entry files):"] +
                     (["- `%s`" % x for x in read_] or ["- none"]) + ([""] + comp if comp else []))


def checkpoint_md(rec):
    """A progress record as the pack's `## Checkpoint` body."""
    cp = rec["checkpoint"]
    item = lambda x: x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    rows = ["- head: `%s` · attempt %s" % (rec.get("head"), rec.get("attempt"))]
    for k, label in (("done", "done"), ("next", "next"), ("tests", "tests"), ("decisions", "pending DECISIONS"),
                     ("deviations", "pending DEVIATIONS"), ("notes", "notes")):
        v = cp.get(k)
        if isinstance(v, list):
            rows += ["- %s:%s" % (label, "" if v else " none")] + ["  - %s" % item(x) for x in v]
        elif v is not None:
            rows.append("- %s: %s" % (label, item(v)))
    return "\n".join(rows)


def block_findings(feat, bid):
    """([finding], n_others) — the open pre-release.md lines relevant to block `bid`: its own, those of
    a block sharing a boundary with it (owner or consumer of one it touches) or scoped to such a
    boundary, and — for a composition block — those of every earlier composition block of its side (the
    shared root's debt); the rest of the feature's open lines only counted."""
    touched = feat.touched(bid)
    near = {bid} | {str(bd.get("id")) for bd in touched} | {str(bd.get("owner")) for bd in touched} | \
        {c for bd in touched for c in feat.consumers(bd)}
    if feat.row[bid].get("composition") is True and feat.row[bid].get("type") != "scaffold":
        near |= set(earlier_compositions(feat, feat.row[bid]))
    open_ = [f for f in parse_findings(feat) if f["mark"] == "open"]
    mine = [f for f in open_ if f.get("block") in near]
    return mine, len(open_) - len(mine)


def pack_deps(feat, bids, add, out, writer):
    """The blocks' files, then the boundaries and ADRs they resolve (each once), then the lessons of
    their types. `writer`: the packed block (it writes the checks whose `from` it is); None for a group."""
    for bid in bids:
        bpath = feat.files()[bid][0][2]
        add("Block %s" % bid, bpath, read(bpath))
    touched, adrs = deps_many(feat, bids)
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
            elif writer and c["from"] == writer:
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
    lpath = os.path.join(feat.odir, "architetture", "lessons-by-block-type.md")
    for btype in sorted({str(feat.row[b].get("type")) for b in bids}) if os.path.isfile(lpath) else []:
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
    scopes, bids = {"feature"}, [bid]
    if bid not in feat.row:  # a pre-release group: its release and its blocks
        fm = group_spec(feat, bid)[1]
        m = re.match(r"^pre-(.+)-\d+$", bid)
        scopes |= {"release:%s" % (fm.get("release") or (m.group(1) if m else ""))}
        bids = fm["blocks"]
    for b in bids:
        scopes |= {"block:" + b} | {"boundary:%s" % x.get("id") for x in feat.touched(b)}
        scopes |= {"block:%s" % (feat.bnd.get(c) or {}).get("owner") for c in feat.consumes(b)}
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


def record_review_proof(feat, bid, s, cur):
    """F/review-proof/<bid>.json = the reviewed sha + the spec hash (the caller checked it is current)."""
    path = os.path.join(feat.dir, "review-proof", bid + ".json")
    write_json(path, {"id": bid, "sha": s, "spec_hash": cur})
    return path


def cmd_proof(a):
    feat = Feature(a.feature_dir)
    repo = feat.repo()
    if a.kind == "review":
        if not a.sha or a.gate is not None or a.gate_files or (a.op == "record") != bool(a.spec_hash):
            raise UsageError("proof record review takes --sha and --spec-hash (the pack's); check takes --sha")
        s = need_sha(repo, a.sha)
        if a.op == "record":
            cur = spec_hash(feat, a.id)
            if cur != a.spec_hash:  # the reviewers judged another spec than the current one
                return emit({"refused": "the spec changed since the reviewed pack: re-pack, review again",
                             "reviewed": a.spec_hash, "current": cur}, 1)
            return emit({"recorded": record_review_proof(feat, a.id, s, cur), "sha": s})
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


# ---- release: list · group · close · waive · confirm (serial: one writer, the composer) ------------
RELEASE_OPTS = {"list": {"integration"}, "group": {"id", "lines"}, "close": {"entries"}, "waive": {"entries"},
                "confirm": {"integration", "sha", "tag", "merge_to", "base_sha", "by", "consent"}}


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_text(path, text):
    """Atomic (tmp + rename), like write_json."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)


def load_entries(raw):
    """--entries: a JSON file, or the JSON array inline."""
    text = raw if raw.lstrip().startswith("[") else read(raw) if os.path.isfile(raw) else \
        _raise(UsageError("--entries %s: neither a JSON array nor a file" % raw))
    try:
        entries = json.loads(text)
    except ValueError as e:
        raise UsageError("--entries does not parse: %s" % e)
    if not isinstance(entries, list) or not entries:
        raise UsageError("--entries is a non-empty JSON array of objects")
    return entries


def release_record(feat, rn, action, raw, replace=()):
    """close | waive: validate the WHOLE batch, then append the records to
    F/release-decisions/<rn>.md (its one ```json block; `action`/`at` set here) and flip the marks
    (`[x]` close, `[~]` waive). `replace`: findings of the batch whose earlier records (valid or
    not) are dropped — the repair path; an invalid record not replaced is refused. Any problem →
    nothing written."""
    entries, findings = load_entries(raw), parse_findings(feat)
    by_line = {f["line"]: f for f in findings}
    keys = RECORD_KEYS[action]
    repo = feat.repo() if action == "close" else None
    doc, _, errs = read_records(feat, rn)
    path = decisions_path(feat, rn)
    problems = ["release-decisions/%s.md: %s — fix it first" % (rn, e) for e in errs if not e.startswith("record ")]
    replace = set(replace or ())
    kept = [r for r in (doc or {}).get("records") or [] if not (isinstance(r, dict) and r.get("finding") in replace)]
    for k, r in enumerate((doc or {}).get("records") or []):
        bad = record_problem(r)
        if bad and r in kept:
            h = r.get("finding") if isinstance(r, dict) and isinstance(r.get("finding"), str) else None
            problems.append("release-decisions/%s.md record %d is invalid (%s): %s" % (
                rn, k, bad, "re-record finding %s with --replace %s" % (h, h) if h else
                "it names no finding — remove it from the ```json block"))
    batch = {e.get("finding") for e in entries if isinstance(e, dict)}
    problems += ["--replace %s: not a finding of the batch" % h for h in sorted(replace - batch)]
    seen, recs = set(), []
    for k, e in enumerate(entries):
        p = lambda msg: problems.append("entry %d: %s" % (k, msg))
        if not isinstance(e, dict) or set(e) != set(keys):
            p("keys must be exactly %s" % ", ".join(keys))
            continue
        if not isinstance(e["line"], int) or isinstance(e["line"], bool) or \
                any(not isinstance(e[x], str) or not e[x].strip() for x in keys[1:]):
            p("line is an integer, every other field a non-empty string")
            continue
        f = by_line.get(e["line"])
        if not f or "error" in f:
            p("line %d is not a well-formed finding of pre-release.md" % e["line"])
        elif f["finding"] != e["finding"]:
            p("line %d is finding %s, not %s: re-read `release list`" % (e["line"], f["finding"], e["finding"]))
        elif f["release"] != rn:
            p("line %d belongs to %s, not %s" % (e["line"], f["release"], rn))
        elif f["finding"] in seen:
            p("finding %s twice in the batch" % f["finding"])
        elif action == "waive" and f["sev"] in UNWAIVABLE:
            p("line %d is %s: a HIGH/FAIL is fixed, never waived" % (e["line"], f["sev"]))
        elif action == "waive" and f["mark"] == "closed":
            p("line %d is already closed" % e["line"])
        else:
            seen.add(f["finding"])
            rec = dict({x: e[x].strip() if isinstance(e[x], str) else e[x] for x in keys}, action=action, at=now_utc())
            if action == "close":
                s = sha(repo, e["sha"])
                ev = e["evidence"]
                epath = os.path.join(feat.dir, ev.split("#", 1)[0])
                if not s:
                    p("sha %s is not a commit" % e["sha"])
                elif not re.match(r"^release-evidence/%s\.md(#\S*)?$" % re.escape(rn), ev) or not os.path.isfile(epath):
                    p("evidence %s is not an existing release-evidence/%s.md[#anchor]" % (ev, rn))
                elif f["finding"] not in read(epath):
                    p("release-evidence/%s.md does not name finding %s" % (rn, f["finding"]))
                rec["sha"] = s
            recs.append(rec)
    if problems:
        return {"ok": False, "refused": "nothing written", "problems": problems}, 1
    old = read(path) if os.path.isfile(path) else ""
    block = "```json\n%s\n```" % json.dumps({"records": kept + recs},
                                            indent=2, ensure_ascii=False)
    if doc is not None:  # replace the one block; any prose around it (a legacy file) is kept
        text = re.sub(r"^```json[ \t]*\n.*?^```[ \t]*$", lambda _: block, old, count=1, flags=re.S | re.M)
    elif old.strip():
        text = old.rstrip("\n") + "\n\n" + block + "\n"
    else:
        text = "# Release decisions — %s\n\nWritten by `release close|waive` only.\n\n%s\n" % (rn, block)
    write_text(path, text)
    ppath = os.path.join(feat.dir, "pre-release.md")
    lines = read(ppath).split("\n")
    mark = "x" if action == "close" else "~"
    for r in recs:
        lines[r["line"] - 1] = PRE_LINE.sub(lambda m: m.group(1) + mark + m.group(3) + m.group(4), lines[r["line"] - 1])
    write_text(ppath, "\n".join(lines))
    return {"ok": True, "release": rn, "action": action, "lines": [r["line"] for r in recs],
            "findings": [r["finding"] for r in recs], "replaced": sorted(replace), "file": path}, 0


def release_group(feat, rn, gid, raw_lines):
    """Write F/rework/<gid>-1.md: frontmatter release/blocks/findings + the selected open lines,
    copied. One group per (context, side); a finding already in another group is refused."""
    if not re.match(r"^pre-%s-\d+$" % re.escape(rn), gid) or gid in feat.row:
        raise UsageError("--id is pre-%s-<k> and not a block id" % rn)
    pairs = [re.match(r"^(\d+):([0-9a-f]{12})$", x or "") for x in raw_lines or []]
    if not pairs or not all(pairs):
        raise UsageError("--lines takes <line>:<finding> pairs (the line number and hash from `release list`)")
    by_line, problems, picked = {f["line"]: f for f in parse_findings(feat)}, [], []
    for n, h in ((int(m.group(1)), m.group(2)) for m in pairs):
        f = by_line.get(n)
        if not f or "error" in f:
            problems.append("line %d is not a well-formed finding" % n)
        elif f["finding"] != h:
            problems.append("line %d is finding %s, not %s: re-read `release list`" % (n, f["finding"], h))
        elif f["release"] != rn or f["mark"] != "open":
            problems.append("line %d is not an open %s line" % (n, rn))
        elif f["block"] not in feat.row:
            problems.append("line %d names %s, not a block of the manifest" % (n, f["block"]))
        elif f in picked:
            problems.append("line %d given twice" % n)
        else:
            picked.append(f)
    blocks = list(dict.fromkeys(f["block"] for f in picked))
    for key in ("context", "side"):
        vals = sorted({str(feat.row[b].get(key)) for b in blocks if feat.row[b].get(key) is not None})
        if len(vals) > 1:
            problems.append("the lines span %ss %s: one group per (context, side)" % (key, ", ".join(vals)))
    for p in sorted(glob.glob(os.path.join(feat.dir, "rework", "pre-*-1.md"))):
        other = os.path.basename(p)[:-5]
        if other != gid:
            fm = board.parse_frontmatter(read(p))[0]
            problems += ["line %d (finding %s) is already in group %s" % (f["line"], f["finding"], other)
                         for f in picked if f["finding"] in (fm.get("findings") or [])]
    if problems:
        return {"ok": False, "refused": "nothing written", "problems": problems}, 1
    ctx = feat.row[blocks[0]].get("context")
    text = "---\nrelease: %s\nblocks: [%s]\nfindings: [%s]\n---\n# %s — %s fixes (context %s)\n\n%s\n" % (
        rn, ", ".join(blocks), ", ".join(f["finding"] for f in picked), gid, rn, ctx,
        "\n".join("- [ ] %s" % f["text"] for f in picked))
    path = os.path.join(feat.dir, "rework", gid + "-1.md")
    if os.path.isfile(path) and read(path) != text:
        return {"ok": False, "refused": "rework/%s-1.md exists with other content" % gid}, 1
    unchanged = os.path.isfile(path)
    if not unchanged:
        write_text(path, text)
    return {"ok": True, "id": gid, "file": path, "blocks": blocks, "findings": [f["finding"] for f in picked],
            "context": ctx, "unchanged": unchanged}, 0


def one_line(s):
    return " ".join(str(s).split())


def release_confirm(feat, rn, a):
    """Preflight everything, then fast-forward BASE to S and put an annotated tag on S. An identical
    repeat is a no-op; a half-done confirmation (one of the two present) is completed and reported;
    anything else is refused with nothing written. Never a push, never a new merge commit."""
    repo = feat.repo()
    S, T = sha(repo, a.sha), sha(repo, a.base_sha)
    b_tip, base_tip = need_sha(repo, a.integration), need_sha(repo, a.merge_to)
    problems = [] if S else ["--sha %s is not a commit" % a.sha]
    problems += [] if T else ["--base-sha %s is not a commit" % a.base_sha]
    problems += ["--merge-to is the integration line itself"] if a.merge_to == a.integration else []
    problems += ["--by and --consent are the deciding user and a reference to the consent"] \
        if not (one_line(a.by) and one_line(a.consent)) else []
    if S and b_tip != S:
        problems.append("%s is at %s, not the consented %s" % (a.integration, b_tip[:12], S[:12]))
    ev = release_eval(feat, rn, repo, b_tip)
    if not ev["releasable"]:
        problems.append("%s is not releasable: %s" % (rn, "; ".join(
            ev["waiting"] + ["%d blocking lines" % len(ev["blocking"])] * bool(ev["blocking"]) + ev["errors"])))
    problems += ["lint " + g for g in ev["gaps"]]
    if git(repo, "check-ref-format", "refs/tags/" + a.tag, check=False).returncode:
        problems.append("--tag %r is not a valid tag name" % a.tag)
    head = git(repo, "symbolic-ref", "--short", "-q", "HEAD", check=False).stdout.strip()
    if head != a.integration:
        problems.append("the checkout of F is on %s, not %s: the evaluated files must be the line's" % (
            head or "a detached HEAD", a.integration))
    elif dirty(repo):
        problems.append("the checkout of F has uncommitted changes: commit the records on %s first" % a.integration)
    base_wt = worktree_of(repo, a.merge_to)
    if base_wt and dirty(base_wt):
        problems.append("the checkout of %s (%s) has uncommitted changes" % (a.merge_to, base_wt))
    key = release_key(feat, rn)
    tagged = sha(repo, "refs/tags/" + a.tag) is not None
    want = {"target": S, "release": key, "merge_to": a.merge_to, "from": T, "integration": a.integration,
            "decided": one_line(a.by), "consent": one_line(a.consent)}
    old = next((t for t in release_tags(repo) if t["tag"] == a.tag), None)
    if tagged and (not old or any(old[k] != v for k, v in want.items())):  # same release, sha AND consent
        problems.append("tag %s exists and is not this confirmation's tag (%s): collision" % (a.tag, ", ".join(
            "%s %s" % (k.replace("_", "-"), old[k]) for k, v in want.items() if old[k] != v) if old else "not ours"))
    merged = bool(S) and base_tip == S
    if S and T and not merged:
        if base_tip != T:
            problems.append("%s is at %s, neither the consented base %s nor %s" % (a.merge_to, base_tip[:12], T[:12], S[:12]))
        elif not is_ancestor(repo, T, S):
            problems.append("%s@%s is not an ancestor of %s: diverged — stop (no new merge)" % (a.merge_to, T[:12], S[:12]))
    elif merged and T and not is_ancestor(repo, T, S):
        problems.append("--base-sha %s is not an ancestor of %s" % (T[:12], S[:12]))
    if problems:
        return {"ok": False, "refused": "nothing written", "problems": problems}, 1
    out = {"ok": True, "confirmed": True, "release": rn, "sha": S, "tag": a.tag, "merge_to": a.merge_to,
           "base_sha_before": base_tip, "partial": [], "unchanged": merged and tagged}
    if merged and tagged:
        return out, 0
    if merged:
        out["partial"].append("%s was already at %s: only the tag is created" % (a.merge_to, S[:12]))
    elif base_wt:  # checked out: fast-forward that checkout (git refuses to overwrite local changes)
        ff = git(base_wt, "merge", "--ff-only", S, check=False)
        if ff.returncode:
            return {"ok": False, "refused": "fast-forward failed: nothing written",
                    "problems": [(ff.stderr or ff.stdout).strip()]}, 1
    else:
        git(repo, "update-ref", "refs/heads/" + a.merge_to, S, T)  # compare-and-swap
    if tagged:
        out["partial"].append("tag %s was already on %s: only the fast-forward is done" % (a.tag, S[:12]))
        return out, 0
    msg = "release %s\n\n%s: %s\nintegration: %s @ %s\nmerge-to: %s (from %s)\ndecided: %s\nconsent: %s\n" % (
        key, TAG_KEY, key, a.integration, S, a.merge_to, T, one_line(a.by), one_line(a.consent))
    t = git(repo, "tag", "-a", a.tag, S, "-m", msg, check=False)
    if t.returncode:
        return {"ok": False, "confirmed": False, "partial": ["%s fast-forwarded to %s; the tag was NOT created: %s — "
                                                             "repeat the identical command" % (
                                                                 a.merge_to, S[:12], (t.stderr or t.stdout).strip())]}, 1
    return out, 0


def cmd_release(a):
    feat = Feature(a.feature_dir)
    need = RELEASE_OPTS[a.op]
    given = {k for k in ("integration", "entries", "id", "lines", "sha", "tag", "merge_to", "base_sha", "by", "consent")
             if getattr(a, k) is not None}
    if given != need:
        flag = lambda ks: " ".join("--" + k.replace("_", "-") for k in sorted(ks))
        raise UsageError("release %s takes %s" % (a.op, flag(need)) + "".join(
            "; %s: %s" % (what, flag(ks)) for what, ks in (("not an option of " + a.op, given - need),
                                                          ("missing", need - given)) if ks))
    if a.replace and a.op not in ("close", "waive"):
        raise UsageError("--replace is for release close|waive only")
    rn = a.release
    if a.op == "list":
        repo = feat.repo()
        return emit(release_eval(feat, rn, repo, need_sha(repo, a.integration)))
    if a.op in ("close", "waive"):
        r, code = release_record(feat, rn, a.op, a.entries, a.replace)
    elif a.op == "group":
        r, code = release_group(feat, rn, a.id, a.lines)
    else:
        r, code = release_confirm(feat, rn, a)
    return emit(r, code)


# ---- review ingest: the reviewers' reports → one action (the composer never reads the findings) ------
REVIEW_VERDICTS = {"verifier": ("PASS", "FAIL", "SKIP"), "code-review": ("APPROVE", "CHANGES", "BLOCKED")}
DEPTH_REVIEWERS = {"standard": ("verifier",), "deep": ("verifier", "code-review")}
REPORT_KEYS = ("version", "id", "attempt", "reviewer", "sha", "spec_hash", "verdict", "failures", "findings")
REPORT_OPTIONAL = ("checks", "notes", "objections")
REVIEW_FINDING_KEYS = ("sev", "at", "issue", "fix", "evidence")
REVIEW_SEVS, REVIEW_FIXES = ("HIGH", "MED", "LOW"), ("Patch", "Defer", "Decision")
REWORK_CAP = 2  # rework cycles per block; a third failed review parks it
REWORK_REASONS = ("candidate-red", "merge-conflict", "other")
OBJECTION_CAP = 40  # words


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def nonempty(x):
    return isinstance(x, str) and bool(x.strip())


def report_problems(r, where):
    """Shape and type problems of one review report (the schema is CLI.md's): every field is
    type-checked before it is used, so a malformed report is refused, never a crash."""
    if not isinstance(r, dict):
        return ["%s: not a JSON object" % where]
    out = ["%s: missing %s" % (where, k) for k in REPORT_KEYS if k not in r]
    out += ["%s: unknown key %s" % (where, k) for k in r if k not in REPORT_KEYS + REPORT_OPTIONAL]
    if out:
        return out
    if not is_int(r["version"]) or r["version"] != 1:
        out.append("%s: version %r, not 1" % (where, r["version"]))
    if not is_int(r["attempt"]) or r["attempt"] < 1:
        out.append("%s: attempt is a positive integer" % where)
    for k in ("id", "sha", "spec_hash", "reviewer", "verdict"):
        if not nonempty(r[k]):
            out.append("%s: %s is a non-empty string" % (where, k))
    if not isinstance(r["reviewer"], str) or r["reviewer"] not in REVIEW_VERDICTS:
        return out + ["%s: reviewer %r is not %s" % (where, r["reviewer"], " | ".join(REVIEW_VERDICTS))]
    if not isinstance(r["verdict"], str) or r["verdict"] not in REVIEW_VERDICTS[r["reviewer"]]:
        out.append("%s: %s verdict %r is not %s" % (where, r["reviewer"], r["verdict"],
                                                    " | ".join(REVIEW_VERDICTS[r["reviewer"]])))
    if not isinstance(r["failures"], list) or not all(nonempty(x) for x in r["failures"]):
        out.append("%s: failures is a list of non-empty strings" % where)
    elif r["failures"] and r["verdict"] in ("PASS", "APPROVE"):
        out.append("%s: verdict %s with %d failures" % (where, r["verdict"], len(r["failures"])))
    if not isinstance(r["findings"], list):
        out.append("%s: findings is a list" % where)
    else:
        for k, f in enumerate(r["findings"]):
            at = "%s finding %d" % (where, k)
            if not isinstance(f, dict) or set(f) != set(REVIEW_FINDING_KEYS):
                out.append("%s: keys must be exactly %s" % (at, ", ".join(REVIEW_FINDING_KEYS)))
            elif not isinstance(f["evidence"], str) or not all(nonempty(f[x]) for x in ("sev", "at", "issue", "fix")):
                out.append("%s: every field is a string; sev, at, issue, fix non-empty" % at)
            elif f["sev"] not in REVIEW_SEVS:
                out.append("%s: sev %r is not %s" % (at, f["sev"], " | ".join(REVIEW_SEVS)))
            elif f["fix"] not in REVIEW_FIXES:
                out.append("%s: fix %r is not %s" % (at, f["fix"], " | ".join(REVIEW_FIXES)))
            elif not LOCATOR.match(clean_field(f["at"])):
                out.append("%s: at %r is not ONE location: `file:line[-line]`, `path#symbol` or `path` (a list is one "
                           "finding per location)" % (at, f["at"]))
    obj = r.get("objections", [])
    if not isinstance(obj, list):
        out.append("%s: objections is a list" % where)
    else:
        for k, o in enumerate(obj):
            if not isinstance(o, dict) or set(o) != {"about", "text"} or not nonempty(o["about"]) \
                    or not nonempty(o["text"]):
                out.append("%s objection %d: exactly about and text, non-empty strings" % (where, k))
    return out


def clean_field(s):
    """One line, no field separator: safe inside a seven-field pre-release.md line."""
    return one_line(s).replace("·", "-")


def rework_cycles(feat, bid):
    """([(n, path)] of the rework cycles written, the next n). A pre-release group's rework/<id>-1.md
    is its spec (`release group`), not a cycle: its cycles are n ≥ 2."""
    got = []
    for p in glob.glob(os.path.join(feat.dir, "rework", bid + "-*.md")):
        m = re.match(r"^%s-(\d+)\.md$" % re.escape(bid), os.path.basename(p))
        if m:
            got.append((int(m.group(1)), p))
    got.sort()
    cycles = [(n, p) for n, p in got if bid in feat.row or n >= 2]
    return cycles, (got[-1][0] if got else 0) + 1


def rework_next(feat, bid, lines, summary):
    """Write the next rework/<bid>-<n>.md (the ONE numbering and cap of ingest and `rework write`):
    ({action: rework, rework, reason} | {action: park, rework: None, reason: "rework cap…"})."""
    cycles, n = rework_cycles(feat, bid)
    if len(cycles) >= REWORK_CAP:
        return {"action": "park", "rework": None, "reason": "rework cap: %d cycles used (%s); %s" % (
            len(cycles), ", ".join(os.path.relpath(p, feat.dir) for _, p in cycles), summary)}
    path = os.path.join(feat.dir, "rework", "%s-%d.md" % (bid, n))
    write_text(path, "\n".join(["# Rework %s — cycle %d" % (bid, n), ""] + lines).rstrip("\n") + "\n")
    return {"action": "rework", "rework": path, "reason": "%s: cycle %d of %d" % (summary, len(cycles) + 1, REWORK_CAP)}


def drop_review_proof(feat, bid):
    """A non-promote outcome invalidates the block's review proof: `proof check`/`compose start` refuse."""
    p = os.path.join(feat.dir, "review-proof", bid + ".json")
    if os.path.isfile(p):
        os.remove(p)
        return True
    return False


def review_release(feat, bid):
    """The release a finding of `bid` is filed under: the block's row, or a group's frontmatter."""
    if bid in feat.row:
        rel = feat.row[bid].get("release")
    else:
        first = os.path.join(feat.dir, "rework", bid + "-1.md")
        rel = board.parse_frontmatter(read(first))[0].get("release") if os.path.isfile(first) else None
    return str(rel) if rel not in (None, "") else None


def finding_block(feat, bid, at):
    """The block a finding of `bid` is filed under. A group's finding names one of its `blocks:` —
    the one whose grouped lines cite the finding's file, when exactly one does, else the first —
    so `release group` accepts it later. A legacy group (no blocks) keeps its own id."""
    if bid in feat.row:
        return bid
    first = os.path.join(feat.dir, "rework", bid + "-1.md")
    if not os.path.isfile(first):
        return bid
    fm, body = board.parse_frontmatter(read(first))
    blocks = [str(b) for b in fm.get("blocks") or []] if isinstance(fm.get("blocks"), list) else []
    if not blocks:
        return bid
    path, cited = locator_path(clean_field(at)), set()
    for l in body.splitlines():
        m = PRE_LINE.match(l)
        parts = [p.strip() for p in m.group(4).split("·")] if m else []
        if len(parts) >= 4 and parts[1] in blocks and locator_path(parts[3]) == path:
            cited.add(parts[1])
    return cited.pop() if len(cited) == 1 else blocks[0]


def ingest_marker(feat, bid, attempt):
    return os.path.join(feat.dir, "review-ingest", "%s-%d.json" % (bid, attempt))


def review_ingest(feat, a):
    """Validate the whole set of reports first (nothing written on any problem), then: file the
    MED/LOW deferrals in pre-release.md (idempotent, every attempt), and decide ONE action —
    decide (a Decision finding, a code-review BLOCKED) · blocked (a verifier SKIP) · rework (a FAIL,
    a HIGH, a CHANGES: one rework/<id>-<n>.md; park once REWORK_CAP cycles exist) · promote (the
    review proof recorded, as `proof record review`). Every non-promote outcome drops the review
    proof. The result is recorded per (id, attempt, reports, answers): an identical retry returns it.
    `--answered D-NNNN…` (notes of F/decisions.md): the Decision findings (and a code-review BLOCKED)
    are answered — the only re-ingest of an attempt allowed is a `decide` one with answers."""
    repo, bid, problems = feat.repo(), a.id, []
    S = sha(repo, a.sha)
    problems += [] if S else ["--sha %s is not a commit" % a.sha]
    tip = sha(repo, PREFIX + bid)
    if not tip:
        problems.append("no branch %s%s" % (PREFIX, bid))
    elif S and tip != S:
        problems.append("--sha %s is not the tip of %s%s (%s): review the tip" % (a.sha, PREFIX, bid, tip[:12]))
    raw = []
    for path in a.file:
        try:
            raw.append((path, open(path, "rb").read()))
        except OSError as e:
            problems.append("%s: unreadable (%s)" % (path, e))
    hashes = sorted(hashlib.sha256(b).hexdigest() for _, b in raw)
    mpath, answered = ingest_marker(feat, bid, a.attempt), sorted(set(a.answered or []))
    mark = load_json(mpath) if os.path.isfile(mpath) else None
    if mark and not problems:  # checked BEFORE the spec: a group's own rework file changes its spec
        same = mark.get("reports") == hashes and mark.get("sha") == S and mark.get("depth") == a.depth
        if same and sorted(mark.get("answered") or []) == answered:
            return dict(mark.get("result") or {}, repeat=True), 0
        if not (same and answered and (mark.get("result") or {}).get("action") == "decide"):
            return {"ok": False, "refused": "nothing written", "problems": [
                "attempt %d of %s was already ingested with other reports (or sha, depth, answers): a new review "
                "is a new attempt; only a `decide` result is ingested again, with --answered" % (a.attempt, bid)]}, 1
    npath = os.path.join(feat.dir, "decisions.md")
    have_notes = {e["id"] for e in parse_notes(npath)[0]} if answered and os.path.isfile(npath) else set()
    problems += ["--answered %s: no such entry in F/decisions.md (record the answer first)" % d
                 for d in answered if d not in have_notes]
    try:
        cur = spec_hash(feat, bid)
    except UsageError as e:
        cur = None
        problems.append(str(e))
    if cur and a.spec_hash != cur:
        problems.append("--spec-hash is not the current spec hash (%s): the spec changed since the reviewed "
                        "pack — re-pack, review again" % cur[:12])
    reports, seen = [], {}
    for path, b in raw:
        where = os.path.basename(path)
        try:
            r = json.loads(b.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            problems.append("%s: unreadable JSON (%s)" % (path, e))
            continue
        bad = report_problems(r, where)
        if bad:
            problems += bad
            continue
        problems += ["%s: id %s, not %s" % (where, r["id"], bid)] if r["id"] != bid else []
        problems += ["%s: attempt %s, not %s" % (where, r["attempt"], a.attempt)] if r["attempt"] != a.attempt else []
        if S and sha(repo, r["sha"]) != S:
            problems.append("%s: sha %s is not --sha %s" % (where, r["sha"], S[:12]))
        problems += ["%s: spec_hash is not --spec-hash" % where] if r["spec_hash"] != a.spec_hash else []
        if r["reviewer"] in seen:
            problems.append("%s: a second %s report (%s)" % (where, r["reviewer"], seen[r["reviewer"]]))
        seen[r["reviewer"]] = where
        reports.append((path, r))
    need = DEPTH_REVIEWERS[a.depth]
    problems += ["depth %s requires a %s report" % (a.depth, x) for x in need if x not in seen]
    problems += ["depth %s takes no %s report" % (a.depth, x) for x in seen if x not in need]
    rel = review_release(feat, bid)
    deferred = [(r["reviewer"], f) for _, r in reports for f in r["findings"]
                if f["sev"] in ("MED", "LOW") and f["fix"] != "Decision"]
    if deferred and not rel:
        problems.append("%s has no release: its MED/LOW findings cannot be filed in pre-release.md" % bid)
    if answered and not any(f["fix"] == "Decision" for _, r in reports for f in r["findings"]) and \
            not any(r["reviewer"] == "code-review" and r["verdict"] == "BLOCKED" for _, r in reports):
        problems.append("--answered: no Decision finding or code-review BLOCKED to answer")
    if problems:
        return {"ok": False, "refused": "nothing written", "problems": problems}, 1

    # -- deferrals: every attempt's, each finding once (release, block, sev, at, issue)
    ppath = os.path.join(feat.dir, "pre-release.md")
    have = {tuple(f[k] for k in ("release", "block", "sev", "locator", "issue"))
            for f in parse_findings(feat) if "finding" in f}
    today, new = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"), []
    tag = "" if bid in feat.row else "[%s] " % bid  # a group's finding keeps the group id in its issue
    for reviewer, f in deferred:
        key = (rel, finding_block(feat, bid, f["at"]), f["sev"], clean_field(f["at"]), tag + clean_field(f["issue"]))
        if key not in have:
            have.add(key)
            new.append("- [ ] %s" % " · ".join(key + (reviewer, today)))
    if new:
        old = read(ppath) if os.path.isfile(ppath) else "# Pre-release findings\n\n"
        write_text(ppath, old + ("" if old.endswith("\n") else "\n") + "\n".join(new) + "\n")

    allf = [(r["reviewer"], f) for _, r in reports for f in r["findings"]]
    fails = [(r["reviewer"], x) for _, r in reports for x in r["failures"]]
    counts = {s: sum(1 for _, f in allf if f["sev"] == s) for s in REVIEW_SEVS}
    counts["failures"] = len(fails)
    verdicts = {r["reviewer"]: r["verdict"] for _, r in reports}
    vtext = " · ".join("%s %s" % kv for kv in sorted(verdicts.items()))
    objections, warnings = [], []
    for path, r in reports:  # an objection over the cap is truncated, never refused
        for k, o in enumerate(r.get("objections") or []):
            words = one_line(o["text"]).split()
            if len(words) > OBJECTION_CAP:
                warnings.append("%s objection %d: %d words, truncated to %d" % (
                    os.path.basename(path), k, len(words), OBJECTION_CAP))
            objections.append(dict(reviewer=r["reviewer"], about=one_line(o["about"]),
                                   text=" ".join(words[:OBJECTION_CAP])))
    out = {"ok": True, "action": None, "reason": None, "rework": None, "counts": counts, "appended": len(new),
           "proof": False, "objections": objections}
    if warnings:
        out["warnings"] = warnings
    if answered:
        out["answered"] = answered
    brief = lambda items: "; ".join(("%s %s" % (w, clean_field(t))).strip()[:160] for w, t in items[:3]) + \
        (" (+%d more)" % (len(items) - 3) if len(items) > 3 else "")
    decisions = [(f["at"], f["issue"]) for _, f in allf if f["fix"] == "Decision" and not answered]
    high = [(rv, f) for rv, f in allf if f["sev"] == "HIGH" and not (answered and f["fix"] == "Decision")]
    patch = [(rv, f) for rv, f in allf if f["sev"] != "HIGH" and f["fix"] == "Patch"]
    if decisions or (verdicts.get("code-review") == "BLOCKED" and not answered):
        out.update(action="decide", reason="a human/product choice: " + (
            brief(decisions) or "code-review BLOCKED — see " + seen.get("code-review", "")))
    elif verdicts.get("verifier") == "SKIP":
        out.update(action="blocked", reason="verifier SKIP (a strategy problem outside the block): " +
                   (brief([("", x) for rv, x in fails if rv == "verifier"]) or "see " + seen["verifier"]))
    elif fails or high or verdicts.get("verifier") == "FAIL" or verdicts.get("code-review") == "CHANGES":
        body = ["review: attempt %d · sha %s · spec %s" % (a.attempt, S, a.spec_hash), "verdicts: " + vtext,
                "reports: " + " · ".join(p for p, _ in reports), ""]
        if fails:
            body += ["## Failures", ""] + ["- [%s] %s" % (rv, one_line(x)) for rv, x in fails] + [""]
        if high:
            body += ["## HIGH findings", ""] + ["- [%s] %s · %s — fix: %s. Evidence: %s" % (
                rv, f["at"], one_line(f["issue"]), f["fix"], one_line(f["evidence"]) or "-") for rv, f in high] + [""]
        if patch:
            body += ["## MED/LOW to patch in this cycle (also filed in pre-release.md)", ""] + [
                "- [%s] %s · %s · %s. Evidence: %s" % (rv, f["sev"], f["at"], one_line(f["issue"]),
                                                      one_line(f["evidence"]) or "-") for rv, f in patch] + [""]
        out.update(rework_next(feat, bid, body, "%d failures, %d HIGH (%s)" % (len(fails), len(high), vtext)))
    else:
        record_review_proof(feat, bid, S, cur)
        out.update(action="promote", reason="every report passes (%s), no HIGH%s" % (
            vtext, "; the Decision findings answered by " + ", ".join(answered) if answered else ""), proof=True)
    if out["action"] != "promote":
        out["proof_dropped"] = drop_review_proof(feat, bid)
    write_json(mpath, {"id": bid, "attempt": a.attempt, "depth": a.depth, "sha": S, "reports": hashes,
                       "answered": answered, "result": out})
    return out, 0


def review_template(feat, a):
    """The ready-to-fill report skeleton: the identity filled, every other value a placeholder that
    states its rule (an unfilled placeholder is refused by ingest). --out writes it (the report path)."""
    if a.reviewer not in REVIEW_VERDICTS:
        raise UsageError("review template takes --reviewer %s" % " | ".join(REVIEW_VERDICTS))
    if not (a.attempt and a.attempt >= 1):
        raise UsageError("--attempt is a positive integer")
    cur = spec_hash(feat, a.id)
    if a.spec_hash != cur:
        return {"ok": False, "refused": "--spec-hash is not the current spec hash (%s): re-pack" % cur[:12]}, 1
    t = {"version": 1, "id": a.id, "attempt": a.attempt, "reviewer": a.reviewer, "sha": a.sha, "spec_hash": cur,
         "verdict": " | ".join(REVIEW_VERDICTS[a.reviewer]) + " (keep exactly one)",
         "checks": ["<what you ran and its result>"],
         "failures": ["<one failed AC or check per string; [] with %s>" % REVIEW_VERDICTS[a.reviewer][0]],
         "findings": [{"sev": "HIGH | MED | LOW (keep one)",
                       "at": "<ONE location: path:12 or path:12-30 or path#Symbol or path; never a list "
                             "(path:12,40): one finding per location>",
                       "issue": "<the problem, one line>", "fix": "Patch | Defer | Decision (keep one)",
                       "evidence": "<why: the line, the failing input; may be empty>"}],
         "objections": [{"about": "<D-NNNN or a topic>",
                         "text": "<your objection to a decision, at most %d words>" % OBJECTION_CAP}],
         "notes": "<optional; replace every <...> placeholder, [] for an empty list>"}
    if not a.out:
        print(json.dumps(t, indent=2, ensure_ascii=False))
        return None, 0
    write_text(os.path.abspath(a.out), json.dumps(t, indent=2, ensure_ascii=False) + "\n")
    return {"ok": True, "file": os.path.abspath(a.out)}, 0


def cmd_review(a):
    feat = Feature(a.feature_dir)
    if a.op == "template":
        if a.file or a.depth or a.answered:
            raise UsageError("review template takes no --file, --depth or --answered")
        out, code = review_template(feat, a)
        return code if out is None else emit(out, code)
    if not a.file or not a.depth:
        raise UsageError("review ingest takes --depth and --file")
    if a.reviewer or a.out:
        raise UsageError("review ingest takes no --reviewer or --out")
    return emit(*review_ingest(feat, a))


# ---- open questions: F/open-questions/<id>.md, closed by a recorded decision ------------------------
def question_close(feat, a):
    """Move F/open-questions/<id>.md to F/open-questions/closed/ (git mv if tracked) with a trailer
    naming the decision that answers it; `status`/`ready` read only the top-level files."""
    src = os.path.join(feat.dir, "open-questions", a.id + ".md")
    if not os.path.isfile(src):
        return {"ok": False, "refused": "no open question %s" % os.path.relpath(src, feat.dir)}, 1
    npath = os.path.join(feat.dir, "decisions.md")
    if a.decision not in {e["id"] for e in (parse_notes(npath)[0] if os.path.isfile(npath) else [])}:
        return {"ok": False, "refused": "%s is not an entry of F/decisions.md: record the answer first "
                "(`why append`)" % a.decision}, 1
    cdir, n = os.path.join(feat.dir, "open-questions", "closed"), 1
    dst = os.path.join(cdir, a.id + ".md")
    while os.path.exists(dst):  # the same id parked and closed again
        n += 1
        dst = os.path.join(cdir, "%s-%d.md" % (a.id, n))
    os.makedirs(cdir, exist_ok=True)
    tracked = git(feat.dir, "ls-files", "--error-unmatch", src, check=False).returncode == 0
    git(feat.dir, "mv", src, dst) if tracked else shutil.move(src, dst)
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    text = read(dst)
    write_text(dst, text + ("" if text.endswith("\n") else "\n") + "\nClosed by %s on %s\n" % (a.decision, day))
    return {"ok": True, "id": a.id, "decision": a.decision, "path": dst, "git": tracked,
            "relinked": relink_notes(feat, src, dst)}, 0


def cmd_question(a):
    return emit(*question_close(Feature(a.feature_dir), a))


def rework_write(feat, a):
    """A rework cycle that is not a review's (a red candidate, a merge conflict): the next
    rework/<id>-<n>.md under the same numbering and cap as `review ingest`; drops the review proof."""
    try:
        spec_hash(feat, a.id)  # a block, or a group with its rework/<id>-1.md
    except UsageError as e:
        return {"ok": False, "refused": "nothing written", "problems": [str(e)]}, 1
    try:
        ev = sys.stdin.read() if a.evidence == "-" else read(a.evidence)
    except OSError as e:
        return {"ok": False, "refused": "nothing written", "problems": ["--evidence: %s" % e]}, 1
    if not ev.strip():
        return {"ok": False, "refused": "nothing written", "problems": ["--evidence is empty"]}, 1
    out = rework_next(feat, a.id, ["reason: %s" % a.reason, "", "## Evidence", "", ev.strip(), ""], a.reason)
    out = dict({"ok": True}, **out)
    out["proof_dropped"] = drop_review_proof(feat, a.id)
    return out, 0


def cmd_rework(a):
    return emit(*rework_write(Feature(a.feature_dir), a))


# ---- state commit: the composer's bookkeeping, exactly <output_dir>, on the integration line --------
def state_commit(feat, a):
    repo = feat.repo()
    rel = os.path.relpath(feat.odir, repo)
    if rel == "." or rel.startswith(".."):
        return {"ok": False, "refused": "the output_dir %s is not a directory strictly inside the repository %s"
                % (feat.odir, repo)}, 1
    head = git(repo, "symbolic-ref", "--short", "-q", "HEAD", check=False).stdout.strip()
    if head != a.integration:
        return {"ok": False, "refused": "the checkout of F (%s) is on %s, not %s" % (
            repo, head or "a detached HEAD", a.integration)}, 1
    if open_candidates(repo):
        return {"ok": False, "refused": "a candidate is open: commit before compose start or after compose "
                "promote, never between", "open": open_candidates(repo)}, 1
    def staged():  # every staged path (added, modified, deleted), unquoted
        parts = git(repo, "diff", "--cached", "--name-only", "--no-renames", "-z").stdout.split("\0")
        return [p for p in parts if p]
    prefix = rel.replace(os.sep, "/").rstrip("/") + "/"
    outside = [p for p in staged() if not p.startswith(prefix)]
    if outside:
        return {"ok": False, "refused": "changes outside %s are staged: unstage them (never committed with the "
                "state)" % prefix, "outside": outside}, 1
    git(repo, "add", "-A", "--", rel)
    paths = staged()
    if not paths:
        return {"ok": True, "committed": False}, 0
    c = git(repo, "commit", "-q", "-m", a.m, check=False)
    if c.returncode:
        return {"ok": False, "refused": "git commit failed: %s" % (c.stderr or c.stdout).strip(), "paths": paths}, 1
    return {"ok": True, "committed": True, "sha": sha(repo, "HEAD"), "paths": paths}, 0


def cmd_state(a):
    return emit(*state_commit(Feature(a.feature_dir), a))


# ---- CLI ----------------------------------------------------------------------------------------
HELP = {  # `MM <command> --help`: what it reads, writes, refuses — the exact semantics are CLI.md's
    "status": "Read-only. Lists anomalies (doing without worktree, leftover candidate, stale review proof, ...),\n"
              "the outcome (done|work|idle|anomaly) and the resume blocks. Exit 1 if any anomaly.",
    "lint": "Read-only. The exact structural checks of the manifest, block files, ADRs, decisions.md and\n"
            "pre-release.md; each gap names its bounce_to. --adrs DIR: the ADRs alone. Exit 1 on a gap.",
    "why": "check: validate a decision-notes file (read-only). append: add an entry file's D-NNNN entries only\n"
           "if the whole file still passes (identical = no-op; only Debate/Result/ADR updates); else nothing written.\n"
           "import <decisions.md> --handoff H: a worker handoff's entries; their ids are local — the next free ids\n"
           "are assigned, references remapped; idempotent (an entry imported before adds nothing); prints the mapping.\n"
           "check H --into <decisions.md>: validate that import without writing (the worker, before returning).\n"
           "template [file]: print a valid entry skeleton with the file's next id.\n\nThe rules `check` enforces:\n"
           "- an entry = `### D-NNNN · <title, ≤ %d words>`, then `- <Field>: <value>` lines: EVERY field is ONE\n"
           "  physical line (never wrapped), given once, non-empty; any other line is an error.\n"
           "- required: %s; optional: %s.\n"
           "- word caps (links count their text, URLs excluded): %s; the whole entry ≤ %d.\n"
           "- Meta = `YYYY-MM-DD; scope: feature|block:<id>|boundary:<id>|release:<Rn>; status: accepted|superseded\n"
           "  [; sha: <hex>]`, nothing else; beside a manifest the scope names a row or release of it.\n"
           "- Hypothesis, Check, Result: ALL THREE `n/a — decided by <reference>` (an id like REQ-3/ADR-0002 or a\n"
           "  link), or none of them.\n"
           "- Result: a link to its evidence, or `untested — <reason>` / `inconclusive — <reason>`.\n"
           "- By = `decided: <who>; recorded: <who>`; Docs = 1-3 links; ADR = a link; Confidence = `low|medium|high\n"
           "  — <why>`; every local link exists (relative to the file).\n"
           "- ids ascending: a new entry takes the highest id + 1, appended at the end; Supersedes names one\n"
           "  earlier id (which becomes superseded); an existing entry changes only Debate/Result/ADR." % (
               TITLE_CAP, ", ".join(k for k in NOTE_FIELDS if k not in NOTE_OPTIONAL), ", ".join(NOTE_OPTIONAL),
               ", ".join("%s %d" % (k, c) for k, c in NOTE_FIELDS.items() if c), NOTE_CAP),
    "manifest": "render: write every block file from its building-blocks.yaml row (state folder kept, identical\n"
                "files untouched); an incomplete row, a duplicate or a context change refuses, writing nothing.",
    "ready": "Read-only. Blocks in todo/ whose dependencies are integrated, in build order (scaffold first),\n"
             "plus finishable blocks, open spikes and resume blocks.",
    "move": "Moves a block file todo->doing, doing->todo, doing->done (only if finishable), git mv if tracked;\n"
            "done deletes its progress. Anything else: ok:false + refused, nothing moved (exit 1).",
    "pack": "Read-only. Prints the block's context (Markdown) headed by spec_hash: block, row, boundaries, ADRs,\n"
            "lessons, decision notes, open findings, a fresh checkpoint, --extra files.",
    "progress": "record: write F/progress/<id>.json (a worker's checkpoint) atomically. Refused, nothing written:\n"
                "not in doing/, head not block/<id>'s tip, dirty worktree, spec changed, no progress.",
    "diff-range": "Read-only. The review range from the merge-base of --base and --head (run in the repo).",
    "proof": "record review: write F/review-proof/<id>.json (refused if --spec-hash is not the current one).\n"
             "record gate: F/gate-proof/<side>/proof.json. check: fresh or stale_because (exit 1 when stale).",
    "compose": "start: candidate worktree = line tip + --branch (refused without a fresh review proof, or while a\n"
               "candidate is open). promote: fast-forward the line, write integrated/<id>.json. abort: remove it.",
    "release": "list: the release evaluation (read-only). group: write rework/pre-<Rn>-<k>-1.md. close|waive:\n"
               "append records + flip marks, the whole batch validated first. confirm: ff the base + tag (consent).",
    "question": "close: move F/open-questions/<id>.md to open-questions/closed/ with `Closed by D-NNNN on <date>`\n"
                "(git mv if tracked); refused unless the question exists and --decision is an entry of F/decisions.md.",
    "review": "template: print (or --out: write) a report skeleton for --reviewer, its placeholders stating each rule.\n"
              "ingest: validate the reviewers' JSON reports (full set for --depth, same id/attempt/sha/spec_hash;\n"
              "--sha the tip of block/<id>, --spec-hash current), else nothing written. Files MED/LOW in pre-release.md\n"
              "(idempotent), then ONE action: promote (review proof written) | rework (rework/<id>-<n>.md) | park\n"
              "(rework cap) | decide | blocked; a non-promote action drops the review proof. An identical retry\n"
              "of an attempt returns its recorded result. --answered D-NNNN (repeatable, notes of F/decisions.md): the\n"
              "Decision findings are answered — re-ingest a `decide` attempt with them to promote without code.",
    "codemap": "Read-only. Markdown on stdout, at --ref: per side (profile `sides:`), per module (architecture.md\n"
               "`modules:` [{id, side, root, entry_files}] in a YAML block; else per top directory), the files git tracks,\n"
               "entry files marked with --files. Discovery only: a module's contract stays the project's dependency lint.",
    "rework": "write: the next rework/<id>-<n>.md (same numbering and 2-cycle cap as review ingest; a group's -1\n"
              "is its spec) from --evidence; at the cap: action park, nothing written. Drops the review proof.",
    "state": "commit: on the checkout of F, on --integration only, no candidate open: stage every change under\n"
             "<output_dir> and commit it; refused if anything outside it is staged. Nothing to commit: committed:false.",
}


def build_parser():
    ap = argparse.ArgumentParser(prog="mismagent.py", description="mismAgent build tool — `<command> --help` for "
                                 "each; exact semantics in CLI.md")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, hlp, *pos):
        p = sub.add_parser(name, help=hlp, description=HELP[name], formatter_class=argparse.RawDescriptionHelpFormatter)
        for x in pos:
            p.add_argument(x) if isinstance(x, str) else p.add_argument(x[0], choices=x[1])
        p.set_defaults(fn=fn)
        return p
    cmd("status", cmd_status, "anomalies (read-only)", "feature_dir").add_argument("--integration", required=True)
    p = cmd("lint", cmd_lint, "exact structural checks (F, or --adrs DIR before any manifest)")
    p.add_argument("feature_dir", nargs="?")
    p.add_argument("--adrs")
    p = cmd("why", cmd_why, "check | append | import | template decision notes",
            ("op", ("check", "append", "import", "template")))
    p.add_argument("file", nargs="?")
    p.add_argument("--entry")
    p.add_argument("--handoff")
    p.add_argument("--into")
    p = cmd("codemap", cmd_codemap, "where the existing code is (Markdown; discovery only)", "output_dir")
    p.add_argument("--ref", required=True)
    p.add_argument("--side")
    p.add_argument("--module")
    p.add_argument("--files", action="store_true")
    cmd("manifest", cmd_manifest, "render the block files from the manifest", ("op", ("render",)), "feature_dir")
    cmd("ready", cmd_ready, "ready blocks in order + finishable", "feature_dir")
    cmd("move", cmd_move, "legal state moves only", "feature_dir", "id").add_argument(
        "--to", required=True, choices=STATES)
    cmd("pack", cmd_pack, "the worker's context (Markdown)", "feature_dir", "id").add_argument(
        "--extra", action="extend", nargs="+")
    p = cmd("progress", cmd_progress, "record a worker's checkpoint", ("op", ("record",)), "feature_dir", "id")
    for opt in ("--head", "--spec-hash", "--json"):
        p.add_argument(opt, required=True)
    p.add_argument("--extra", action="extend", nargs="+")
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
    p = cmd("release", cmd_release, "release list | group | close | waive | confirm",
            ("op", tuple(RELEASE_OPTS)), "feature_dir", "release")
    for opt in ("--integration", "--entries", "--id", "--sha", "--tag", "--merge-to", "--base-sha", "--by", "--consent"):
        p.add_argument(opt)
    p.add_argument("--lines", nargs="*")
    p.add_argument("--replace", nargs="+")
    p = cmd("review", cmd_review, "a report template | ingest the reviewers' reports into one action",
            ("op", ("ingest", "template")), "feature_dir", "id")
    p.add_argument("--attempt", type=int, required=True, help="the review attempt the reports carry")
    p.add_argument("--depth", choices=tuple(DEPTH_REVIEWERS),
                   help="ingest: standard = a verifier report; deep = verifier + code-review")
    p.add_argument("--file", action="extend", nargs="+", help="ingest: a reviewer's report (one per reviewer)")
    p.add_argument("--answered", action="append", metavar="D-NNNN",
                   help="ingest: a decision note answering the Decision findings (repeatable)")
    p.add_argument("--reviewer", choices=tuple(REVIEW_VERDICTS), help="template: whose report")
    p.add_argument("--out", help="template: write the skeleton here (the report path)")
    p.add_argument("--sha", required=True, help="the reviewed head: the tip of block/<id>")
    p.add_argument("--spec-hash", required=True, help="the reviewed pack's spec_hash")
    cmd("question", cmd_question, "close an answered open question", ("op", ("close",)), "feature_dir",
        "id").add_argument("--decision", required=True, metavar="D-NNNN")
    p = cmd("rework", cmd_rework, "write the next rework file (a red candidate, a merge conflict)",
            ("op", ("write",)), "feature_dir", "id")
    p.add_argument("--reason", choices=REWORK_REASONS, required=True)
    p.add_argument("--evidence", required=True, help="a file, or - for stdin")
    p = cmd("state", cmd_state, "commit the state under <output_dir> on the integration line", ("op", ("commit",)),
            "feature_dir")
    p.add_argument("-m", required=True, metavar="MESSAGE")
    p.add_argument("--integration", required=True)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a)
    except UsageError as e:
        return emit({"error": str(e)}, 2)


if __name__ == "__main__":
    sys.exit(main())
