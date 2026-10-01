#!/bin/zsh
# run-design-pass.sh — the cheapest test of v0.5's main bet: one design pass (the design loop of
# docs/rationale/v0.5-vision.md) on the baseline's final code, then the same blind judges (F acceptance,
# G quality). Works on a CLONE of the baseline run, never on the run itself.
#   run-design-pass.sh <baseline-run-dir> <clone-dir>
# Results: $J (default ~/.claude/jobs/<clone-name>-designpass/).
set -u
S=${0:A:h}; CS=${S:h}/cassa-structured
B=${1:?usage: run-design-pass.sh <baseline-run-dir> <clone-dir>}; B=${B:A}
R=${2:?clone dir}; R=${R:A}
J=${J:-$HOME/.claude/jobs/${R:t}-designpass}; mkdir -p $J
MODEL=${MODEL:-sonnet}
export CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
log() { print -r -- "$(date +%H:%M:%S) $*" | tee -a $J/scenario.log; }
cost() { python3 -c "import json,sys;print(round(json.load(open(sys.argv[1])).get('total_cost_usd',0),4))" $1 2>/dev/null || echo 0; }
session() {  # name budget prompt-file dir
  (cd $4 && claude -p --model $MODEL --permission-mode bypassPermissions --output-format json \
     --max-budget-usd $2 "$(cat $3)" > $J/$1.json 2>&1)
  log "$1: \$$(cost $J/$1.json)"
}
judge() {  # name prompt-file report budget → fresh session on a detached worktree at HEAD
  local W=$J/$1-wt
  git -C $R worktree remove --force $W 2>/dev/null; git -C $R worktree add -q --detach $W HEAD
  [[ $1 == F ]] && cp $CS/acceptance.md $W/ACCEPTANCE.md
  session $1 $4 $2 $W
  [[ -f $W/$3 ]] && cp $W/$3 $J/$3 || log "$1: no report"
}

[[ -d $R ]] || git clone -q $B $R
git -C $R checkout -q R2 2>/dev/null && git -C $R checkout -q -B design-pass
log "clone at $(git -C $R rev-parse --short HEAD), $(git -C $R ls-files '*.py' | wc -l | tr -d ' ') python files"
session A-architect 3 $S/architect-prompt.md $R
[[ -f $R/ARCHITECTURE.md && -f $R/REFACTORING.md ]] || { log "STOP: architect wrote no plan"; exit 1; }
session B-refactor 8 $S/refactor-prompt.md $R
log "after refactor: $(git -C $R rev-list --count R2..HEAD) commits since R2"
judge F $CS/acceptance-prompt.md acceptance-report.md 10
judge G $S/quality-review-prompt.md quality-report.md 5
log "design pass complete — results in $J"
