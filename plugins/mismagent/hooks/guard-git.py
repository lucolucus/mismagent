#!/usr/bin/env python3
"""PreToolUse(Bash) guard: the builder, the reviewer and the architect never merge, pull, push,
rebase, hard-reset, switch branches, delete branches, stash, tag or move slice state — the
conductor (/mismagent:build) does — nor sweep or drop what is not theirs: `git add -A`/`-u`,
`commit -a`, an add or a commit of the whole tree however spelled (`.`, `./`, `src/..`, `..`, `*`,
`:/`, the root's absolute path, any pathspec magic but `:(literal)`), `clean`, `restore` (specify's
files sit uncommitted beside them, 0.7.27) — nor commit under the subjects mm reads as state:
`specify …` and `conventions …` (the human's commits), `design pass …` (a pass ran). The message
is read as git would keep it — comment lines gone under a cleanup that strips them, then the first
paragraph, its lines joined — from `-m`, a heredoc, a here-string, a `-F` file, the commit `-C`
reuses or `--amend` keeps; one the hook cannot read (a file not there yet, a pipe, a directory it
cannot follow) is denied: `-m` or `-F - <<'EOF'` says it. Nor run the
mm subcommand of another role: `start`, `park`, `land`, `tag` and `conventions` are nobody's among
them, `spec` and `designed` the architect's, `built` the builder's, `review` the reviewer's and the
architect's. Commits by path, `--amend`, cherry-pick, revert and a soft reset are allowed.
Main-session calls pass untouched.

It reads the command as the shell would (`scan`): a newline between commands separates them, one
inside quotes belongs to its string, a comment goes, a heredoc's body is text and is taken out —
when what it feeds reads text (`cat`, `tee`, `git`) and no shell is in the command; otherwise, and
when the shell would expand a substitution in it or it never ends, its lines are judged as
commands, heredocs of their own included. Then it splits on `&&`, `||`, `;`, `|`, `&`, tokenizes
each segment (shlex), skips env assignments and the wrappers it knows with their options (`env -u
X`, `timeout 30`, `nice -n 5`, `sudo -u bob`, `xargs`, `uv run`), and judges the git or mm
subcommand the segment runs — a word that is only an argument (`printf '%s' git push`) runs
nothing; git's global options (`-C <path>`, `-c <kv>`, `--no-pager`, …) are skipped. `cd`,
`pushd`/`popd` and `git -C` are followed for the files and commits a message comes from: a move
inside a `( )` group ends with the group, and one with an option leaves the directory unknown,
never guessed.
Partial protection by design: it reads the literal command text, so an indirection (a script, an
alias, `eval`, `sh -c`, a variable) can slip past. It backs the prompts' invariant; it does not
replace it (`mm check --base` is the real guard).
"""
import json
import os
import re
import shlex
import subprocess
import sys

BUILDER, REVIEWER, ARCHITECT = "mismagent-builder", "mismagent-reviewer", "mismagent-architect"
GUARDED = (BUILDER, REVIEWER, ARCHITECT)
# global options that consume the next token as their value (the `--opt=value` form needs no skip)
TAKES_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
ELSEWHERE = ("--git-dir", "--work-tree", "--namespace")  # another repository: the hook does not follow
# what may stand before the command a segment runs, with its options that take a value; `--opt=value`
# needs no entry. POSITIONAL: the words of its own it takes first (timeout's duration, `uv run`)
WRAPPERS = {"env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}, "command": set(), "builtin": set(),
            "exec": {"-a"}, "time": {"-o", "-f"}, "nohup": set(), "nice": {"-n"}, "ionice": {"-c", "-n", "-p"},
            "stdbuf": {"-i", "-o", "-e"}, "caffeinate": {"-t", "-w"}, "timeout": {"-s", "--signal", "-k", "--kill-after"},
            "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U", "-r", "-t"}, "doas": {"-u", "-C"},
            "xargs": {"-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a"},
            "uv": {"--project", "--directory", "-p", "--python", "--with", "--with-requirements", "--extra",
                   "--group", "--package", "--env-file", "--index", "--config-file", "--cache-dir"},
            "poetry": {"-C", "--directory", "-P", "--project"}, "pipenv": set(), "hatch": {"-e", "--env"},
            "pdm": {"-p", "--project"},
            "then": set(), "do": set(), "else": set(), "!": set(), "{": set()}
POSITIONAL = {"timeout": 1, "uv": 1, "poetry": 1, "pipenv": 1, "hatch": 1, "pdm": 1}
ELSEWHERE_TOO = ("-C", "--chdir", "--directory", "-D")  # a wrapper's option that runs its command in another directory
# a shell, or what hands its input to one: with one anywhere in the command, a heredoc may be run
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "eval", "source", "xargs", "ssh", "busybox", "parallel"}
TEXT_READERS = {"cat", "tee", "git"}  # what a heredoc feeds as text; any other consumer may run it
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# <<EOF, <<'EOF', <<"EOF", <<\EOF, <<-EOF: the whole delimiter word, or it is no opener the hook knows
OPENER = re.compile(r"<<(-?)[ \t]*(\\?)(['\"]?)([\w.+-]+)\3(?=[\s;&|()<>]|$)")
# what a heredoc's opening becomes, and that mark where it feeds a commit its message:
# `-F - <<EOF`, `-m "$(cat <<'EOF' … )"`
MARK, MARKS, MESSAGE_MARK = "\0%d\0", re.compile(r"\0(\d+)\0"), re.compile(r"(?:\$\(\s*cat\s+)?\0(\d+)\0")
REDIRECT = re.compile(r"[<>][<>&]*")
DEPTH = 8  # heredocs in heredocs: past this the hook stops reading, and denies
SWEEP = " (the human's uncommitted files beside you are not yours)"
# the subjects mm reads (its HUMAN_COMMIT and DESIGN_PASS), matched on the subject as git keeps it
RESERVED = re.compile(r'(?:revert ")?(?:specify|conventions)(?:[ :(]|$)|design[ -]pass\b', re.IGNORECASE)
MM_ROLES = {  # the mm subcommands that write: who among the three runs each (any other is read-only)
    "start": (), "park": (), "land": (), "tag": (), "conventions": (),
    "spec": (ARCHITECT,), "designed": (ARCHITECT,), "built": (BUILDER,), "review": (REVIEWER, ARCHITECT)}


def scan(command):
    """(text, bodies): the command for the tokenizer, read as the shell reads it — quotes, `$( )`,
    backticks and comments followed, so a `<<` inside a string opens nothing; `$'…'` becomes a
    plain quoted string. A newline between commands becomes ` ; `; each heredoc's body is taken
    out, a mark left where it opened, naming the body. A body the shell expands (delimiter
    unquoted) with a substitution in it stays, as commands; an unterminated heredoc stays as it is."""
    out, bodies, pending, stack, i, n = [], [], [], [], 0, len(command)
    while i < n:
        c, top = command[i], stack[-1] if stack else ""
        if top == "'":  # literal up to the next quote
            if c == "'":
                stack.pop()
        elif top == "$'":  # the same with escapes: written out as a plain quoted string
            if c == "\\" and i + 1 < n:
                out.append({"n": "\n", "t": "\t", "'": "'\\''"}.get(command[i + 1], command[i + 1]))
                i += 2
                continue
            if c == "'":
                stack.pop()
        elif c == "\\" and i + 1 < n:  # the next character is itself; a newline: the line goes on
            out.append(" " if command[i + 1] == "\n" else command[i:i + 2])
            i += 2
            continue
        elif top == '"':
            if c == '"':
                stack.pop()
            elif c == "`" or command.startswith("$(", i):
                stack.append("`" if c == "`" else "(")
                out.append(c if c == "`" else "$(")
                i += 1 if c == "`" else 2
                continue
        elif c == "`":  # command level from here: the top, a `( )`, a backtick
            stack.pop() if top == "`" else stack.append("`")
        elif c in "\"'(":
            stack.append(c)
        elif command.startswith("$'", i):
            stack.append("$'")
            out.append("'")
            i += 2
            continue
        elif c == ")" and top == "(":
            stack.pop()
        elif c == "#" and (i == 0 or command[i - 1] in " \t\n;&|("):  # a comment: to the end of its line
            i = command.find("\n", i) if "\n" in command[i:] else n
            continue
        elif c == "\n":
            for at, m in pending:  # in the order they opened; i stays on a newline, or the end
                lines = command[i + 1:].split("\n") if i < n else []
                end = next((j for j, line in enumerate(lines)
                            if (line.lstrip("\t") if m.group(1) else line) == m.group(4)), None)
                if end is None:
                    continue
                body = "\n".join(lines[:end])
                if m.group(2) or m.group(3) or not re.search(r"\$\(|`", body):
                    out[at] = MARK % len(bodies)
                    bodies.append(body)
                else:
                    out.append(" ; " + re.sub(r"[\n`]", " ; ", body))
                i += 1 + len("\n".join(lines[:end + 1]))
            pending = []
            out.append(" ; ")
            i += 1
            continue
        elif command.startswith("<<", i) and command[i:i + 3] != "<<<" and command[i - 1:i] != "<":
            m = OPENER.match(command, i)
            if m:
                pending.append((len(out), m))
                out.append(m.group(0))
                i = m.end()
                continue
        out.append(c)
        i += 1
    return "".join(out), bodies


def tokens(command):
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:  # unbalanced quotes: fall back to a plain split, every line a command
        return [t for t in re.split(r"\s+|(?=[;&|()])|(?<=[;&|()])", command.replace("\n", " ; ")) if t]


def words(seg):
    """The segment from the command it runs on: env assignments skipped, and each wrapper before it
    (`env`, `/usr/bin/env`, `timeout`, …) with its options, their values and its own first words.
    `command -v` looks a command up: it runs none."""
    i = 0
    while i < len(seg):
        name = os.path.basename(seg[i])
        if ASSIGNMENT.match(seg[i]):
            i += 1
        elif name in WRAPPERS:
            if name == "command" and seg[i + 1:i + 2] in (["-v"], ["-V"]):
                return []
            i, left = i + 1, POSITIONAL.get(name, 0)
            while i < len(seg) and (seg[i].startswith("-") or left or (name == "env" and ASSIGNMENT.match(seg[i]))):
                if seg[i].startswith("-"):
                    i += 2 if seg[i] in WRAPPERS[name] else 1
                else:
                    i, left = i + 1, left - (0 if ASSIGNMENT.match(seg[i]) else 1)
        else:
            break
    return seg[i:]


def joined(cwd, path):
    """The directory a `cd` or a `git -C` leads to from cwd; None when the hook cannot follow it."""
    if cwd is None or path == "-" or re.search(r"[$`*?\0]", path):
        return None
    return os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))


def moved(cwd, seg, stack):
    """The directory after this segment: a `cd` moves it, `pushd <dir>` and `popd` keep their stack.
    An option changes what the move does: unknown from there on (None), never a guess."""
    seg = words(seg)
    if not seg or seg[0] not in ("cd", "pushd", "popd"):
        return cwd
    if len(seg) > 2 or any(a[:1] in "-+" for a in seg[1:]):
        return None
    if seg[0] == "popd":
        return stack.pop() if stack and len(seg) == 1 else None
    if seg[0] == "pushd":
        if len(seg) != 2:
            return None
        stack.append(cwd)
    return joined(cwd, seg[1] if len(seg) > 1 else "~")


def git_call(seg, cwd):
    """(subcommand, args, the directory git runs in or None, its `-c` settings as (key, value)) if
    the segment runs git, else None."""
    whole, seg, i, settings = seg, words(seg), 1, []
    if not seg or os.path.basename(seg[0]) != "git":
        return None
    for k, tok in enumerate(whole[:len(whole) - len(seg)]):  # a wrapper that runs it elsewhere: `env -C sub git …`
        if tok.split("=")[0] in ELSEWHERE_TOO:
            at = tok.partition("=")[2] or whole[k + 1]
            cwd = joined(cwd, at) if tok.split("=")[0] in ("-C", "--chdir") and "env" in map(os.path.basename, whole[:k]) else None
    while i < len(seg) and seg[i].startswith("-"):
        name, value = seg[i], seg[i + 1] if i + 1 < len(seg) else ""
        if name == "-C":
            cwd = joined(cwd, value)
        elif name.split("=")[0] in ELSEWHERE:
            cwd = None
        elif name == "-c":
            settings.append((value.partition("=")[0].lower(), value.partition("=")[2]))
        i += 2 if name in TAKES_VALUE else 1
    if i >= len(seg):
        return None
    return seg[i], seg[i + 1:], cwd, settings


def mm_call(seg):
    """The mm subcommand the segment runs — mm.py as the script of the python it runs, or as the
    command itself — else None: reading the file, printing its name or asking for its help runs
    nothing."""
    seg = words(seg)
    if seg and os.path.basename(seg[0]).startswith("python"):  # its script: the first word that is no option
        seg = seg[next((k for k in range(1, len(seg)) if not seg[k].startswith("-")), len(seg)):]
    if not seg or os.path.basename(seg[0]) != "mm.py" or {"-h", "--help"} & set(seg):
        return None
    return next((tok for tok in seg[1:] if not tok.startswith("-")), None)


COMMIT_TAKES_VALUE = {"-m", "--message", "-F", "--file", "--author", "--date", "-C", "-c", "--cleanup",
                      "--reuse-message", "--reedit-message", "--fixup", "--squash", "--trailer"}
MESSAGE, FROM_FILE = ("-m", "--message"), ("-F", "--file")
FROM_COMMIT = ("-C", "-c", "--reuse-message", "--reedit-message")


def redirected(args, bodies):
    """(args without their redirections, stdin): stdin is ("text", it) for a heredoc or a here-string,
    ("file", path) for `< path`, None otherwise (a terminal, a pipe, a heredoc the hook did not
    take out) — the last one wins, as in the shell, wherever it stands."""
    rest, stdin, i = [], None, 0
    while i < len(args):
        a, i = args[i], i + 1
        mark = MARKS.fullmatch(a)
        if mark:
            stdin = ("text", bodies[int(mark.group(1))])
        elif REDIRECT.fullmatch(a):  # `< msg.txt`, `> out`, `>&2`: the next token is its target
            if a.startswith("<"):
                stdin = {"<": ("file", args[i]), "<<<": ("text", args[i])}.get(a) if i < len(args) else None
            i += 1
        else:
            rest.append(a)
    return rest, stdin


def commit_parts(args):
    """A commit's (options, values, pathspecs): an option's value is neither an option nor a path
    (`-m '-a flag'` and `-m"adds a"` are messages), and everything after `--` is a path. values:
    [(option, its value)] in order, for the options that take one."""
    opts, values, paths, i = [], [], [], 0
    while i < len(args):
        a, i = args[i], i + 1
        if a == "--":
            paths += args[i:]
            break
        if a == "-" or not a.startswith("-"):
            paths.append(a)
            continue
        if a.startswith("--"):
            name, joined_, value = a.partition("=")
        else:  # short options in one token (`-sam`, `-m"text"`, `-uall`): a value ends them
            ends = [k for k in range(1, len(a)) if "-" + a[k] in COMMIT_TAKES_VALUE or a[k] in "Su"]
            k = ends[0] if ends else len(a) - 1
            opts += ["-" + c for c in a[1:k]]
            name, joined_, value = "-" + a[k], a[k + 1:], a[k + 1:]
        opts.append(name)
        if name in COMMIT_TAKES_VALUE:
            if not joined_ and i < len(args):
                value, i = args[i], i + 1
            values.append((name, value))
    return opts, values, paths


def everything(path, cwd):
    """A pathspec for the whole tree, or one that may be: `.`, `*`, `..` and their spellings (`./`,
    `src/..`, `**`), the absolute path of a repository's root or of a folder above cwd, and any
    pathspec magic (`:/`, `:(top)`, `:!x`) but `:(literal)` — nobody here needs one."""
    path = path[len(":(literal)"):] if path.startswith(":(literal)") else path
    if os.path.isabs(path):
        return os.path.exists(os.path.join(path, ".git")) or (cwd is not None and (
            os.path.realpath(cwd) + os.sep).startswith(os.path.realpath(path).rstrip(os.sep) + os.sep))
    return path.startswith(":") or (bool(path) and set(os.path.normpath(path)) <= set("*./"))


def run_git(cwd, *args):
    """git's output in cwd, or None: no directory to run it in, or it failed."""
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           timeout=5) if cwd is not None else None
    except (OSError, subprocess.SubprocessError):
        p = None
    return p.stdout if p and not p.returncode else None


def message(values, stdin, bodies, cwd, amend):
    """The commit's message as the command gives it: the `-m` paragraphs, a heredoc's body, a `-F`
    file (or stdin's), the commit `-C` reuses — and with none of them, an amend keeps HEAD's. None
    when one of those cannot be read: not there yet, a pipe, a directory the hook cannot follow."""
    def read(path):
        try:
            with open(os.path.join(cwd, path), encoding="utf-8", errors="replace") as f:
                return f.read()
        except (OSError, TypeError):  # TypeError: no directory to read it from
            return None

    parts = []
    for name, value in values:
        mark = MESSAGE_MARK.match(value)
        if name in MESSAGE:
            parts.append(bodies[int(mark.group(1))] if mark else value)
        elif name in FROM_FILE and value == "-":
            parts.append(stdin and (stdin[1] if stdin[0] == "text" else read(stdin[1])))
        elif name in FROM_FILE:
            parts.append(read(value))
        elif name in FROM_COMMIT:
            parts.append(run_git(cwd, "log", "-1", "--format=%B", value, "--"))
    if amend and not any(name in MESSAGE + FROM_FILE + FROM_COMMIT for name, _ in values):
        parts.append(run_git(cwd, "log", "-1", "--format=%B", "HEAD", "--"))
    return None if None in parts else "\n\n".join(parts)


def subject(text, opts, values, settings, cwd):
    """The subject git would keep of this message: under a cleanup that strips comments — asked for,
    configured, or the default once an editor opens — the comment lines go first; then the first
    paragraph, its lines joined."""
    def config(*keys):  # the last one set wins, on the command line first: git's own order
        given = [v for k, v in settings if k in keys] or [
            line.partition(" ")[2] for line in (run_git(cwd, "config", "--get-regexp", "^(%s)$" % "|".join(
                re.escape(k) for k in keys)) or "").splitlines()]
        return given[-1] if given else ""
    mode = ([v for n, v in values if n == "--cleanup"] or [config("commit.cleanup").lower() or "default"])[-1]
    if mode == "strip" or (mode == "default" and {"-e", "--edit", "-c", "--reedit-message"} & set(opts)):
        char = config("core.commentchar", "core.commentstring") or "#"  # two names of one setting
        text = "\n".join(line for line in text.split("\n") if not line.startswith("#" if char == "auto" else char))
    return " ".join(re.split(r"\n[ \t]*\n", text.strip(), 1)[0].split())


def violation(sub, args, bodies=(), cwd=None, settings=()):
    if sub in ("merge", "push", "rebase", "checkout", "switch", "stash", "tag", "clean", "restore"):
        return "git " + sub
    if sub == "pull":
        return "git pull (a merge, or a rebase)"
    if sub == "reset" and "--hard" in args:
        return "git reset --hard"
    if sub == "add" and any(a in ("--all", "--update") or re.match(r"^-[a-zA-Z]*[Au]", a)
                            or everything(a, cwd) for a in args):
        return "git add of everything" + SWEEP
    if sub == "commit":
        args, stdin = redirected(args, bodies)
        opts, values, paths = commit_parts(args)
        if "-a" in opts or "--all" in opts:
            return "git commit -a" + SWEEP
        if any(everything(p, cwd) for p in paths):
            return "git commit of everything" + SWEEP
        text = message(values, stdin, bodies, cwd, "--amend" in opts)
        if text is None:
            return ("git commit with a message the hook cannot read (a `-F` file not there yet, a pipe, a "
                    "commit to reuse or amend it cannot find, a directory it cannot follow: give the message "
                    "with `-m`, or `-F - <<'EOF'`)")
        if RESERVED.match(subject(text, opts, values, settings, cwd)):
            return ("git commit under a subject starting with `specify`, `conventions` or `design pass` "
                    "(mm reads those as the human's commits and as a pass that ran, and only mm writes "
                    "them: `mm spec`, `mm conventions`, `mm designed`; word yours otherwise)")
    if sub == "branch" and any(a in ("-d", "-D", "--delete") or re.match(r"^-[a-zA-Z]*[dD]", a)
                               for a in args):
        return "git branch --delete"
    if sub == "mv" and any(re.search(r"(^|/)\.mismagent/slices(/|$)", a) for a in args):
        return "git mv of a slice's state"
    return None


def judged(seg, agent, bodies, cwd):
    call, sub = git_call(seg, cwd), mm_call(seg)
    if call:
        return violation(call[0], call[1], bodies, call[2], call[3])
    if sub in MM_ROLES and agent.split(":")[-1] not in MM_ROLES[sub]:
        return "mm %s (%s)" % (sub, "the conductor's, or the human's session's" if not MM_ROLES[sub] else
                               "the %s's" % " and the ".join(r.split("-")[-1] for r in MM_ROLES[sub]))
    return None


def verdict(command, agent, cwd, depth=0):
    """What the command does that this agent may not, or None: its own segments, then each heredoc
    body something may run — all of them with a shell anywhere in the command, else those fed to
    anything but a reader of text — read the same way, with its own heredocs, in the directory it
    was fed in. A `( )` group's moves end with it."""
    if depth > DEPTH:
        return "a command nested deeper than the hook reads"
    text, bodies = scan(command)
    toks = tokens(text)
    shell = any(os.path.basename(tok) in SHELLS or tok == "." for tok in toks)
    seg, stack, groups, run = [], [], [], []
    for tok in toks + [";"]:
        if not (tok and set(tok) <= set(";&|()")):
            seg.append(tok)  # an empty one too: `-m ''` has a value
            continue
        if seg:
            what = judged(seg, agent, bodies, cwd)
            if what:
                return what
            if shell or os.path.basename((words(seg) or [""])[0]) not in TEXT_READERS:
                run += [(int(k), cwd) for word in seg for k in MARKS.findall(word)]
            cwd, seg = moved(cwd, seg, stack), []
        for mark in tok:
            if mark == "(":
                groups.append((cwd, list(stack)))
            elif mark == ")" and groups:
                cwd, stack = groups.pop()
    return next((what for what in (verdict(bodies[k], agent, at, depth + 1) for k, at in run) if what), None)


try:
    event = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
agent = event.get("agent_type") or ""  # absent in the main session
if agent.split(":")[-1] not in GUARDED:  # tolerate a plugin-namespaced type
    sys.exit(0)
what = verdict((event.get("tool_input") or {}).get("command") or "", agent, event.get("cwd") or os.getcwd())
if what:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            "%s is denied to %s: state moves, merges and tags belong to the conductor "
            "(/mismagent:build). Commit your work and return your result." % (what, agent)),
    }}))
sys.exit(0)
