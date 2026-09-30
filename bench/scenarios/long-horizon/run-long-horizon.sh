#!/bin/zsh
# run-long-horizon.sh — S2-lite (scenario.md): step 0 and the baseline arms A and C.
#   run-long-horizon.sh noise <baseline-run> <design-passed-run>     step 0: 3 blind reviews on each
#   run-long-horizon.sh A <baseline-run> <clone-dir> [--from CRn]   arm A: the four requests, plain
#   run-long-horizon.sh C <baseline-run> <clone-dir> [--from CRn]   arm C: A + a design pass per release
#   run-long-horizon.sh Cp <baseline-run> <clone-dir> [--from CRn]  arm C′: A + a pass that decides structure
# Arm B (mismAgent 0.5) runs with its own flow once it exists. Results: $J, never in the runs.
set -u
S=${0:A:h}; H=${S:h:h:h}; BS=${S:h}/baseline; CS=${S:h}/cassa-structured
MODE=${1:?mode: noise | A | C | Cp}; SRC=${2:?baseline run}; SRC=${SRC:A}; R=${3:?second dir}; R=${R:A}
FROM=CR1; [[ ${4:-} == --from ]] && FROM=${5:?--from needs CRn}
J=${J:-$HOME/.claude/jobs/${R:t}-s2-$MODE}; mkdir -p $J
MODEL=${MODEL:-sonnet}
export CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
log() { print -r -- "$(date +%H:%M:%S) $*" | tee -a $J/scenario.log; }
cost() { python3 -c "import json,sys;print(round(json.load(open(sys.argv[1])).get('total_cost_usd',0),4))" $1 2>/dev/null || echo 0; }
record() { python3 -c "import json,sys;print(json.dumps(json.loads(sys.argv[1])))" "$1" >> $J/results.jsonl; }
session() {  # name budget prompt-file dir
  (cd $4 && claude -p --model $MODEL --permission-mode bypassPermissions --output-format json \
     --max-budget-usd $2 "$(cat $3)" > $J/$1.json 2>&1)
  log "$1: \$$(cost $J/$1.json)"
}
worktree() {  # repo ref name → path of a fresh detached worktree
  local W=$J/$3-wt
  git -C $1 worktree remove --force $W 2>/dev/null; git -C $1 worktree add -q --detach $W $2; print $W
}
quality() {  # repo ref label → three blind reviews, one line per review in results.jsonl
  local i W
  for i in 1 2 3; do
    W=$(worktree $1 $2 G-$3-$i)
    session G-$3-$i 5 $BS/quality-review-prompt.md $W
    [[ -f $W/quality-report.md ]] && cp $W/quality-report.md $J/quality-$3-$i.md
    python3 - $W/quality-report.md $3 $i >> $J/results.jsonl <<'EOF'
import json, re, sys
try:
    t = open(sys.argv[1]).read()
except OSError:
    print(json.dumps({"label": sys.argv[2], "review": int(sys.argv[3]), "score": None})); sys.exit()
dims = {m.group(1).strip(): int(m.group(2)) for m in re.finditer(r"^\|\s*([A-Z][^|]+?)\s*\|\s*([1-5])\s*\|", t, re.M)}
m = re.search(r"Overall score:?\**\s*([0-9.]+)", t)
print(json.dumps({"label": sys.argv[2], "review": int(sys.argv[3]), "score": float(m.group(1)) if m else None, "dims": dims}))
EOF
  done
}
acceptance() {  # repo ref label
  local W
  W=$(worktree $1 $2 F-$3)
  cat $CS/acceptance.md $S/acceptance-s2.md > $W/ACCEPTANCE.md
  session F-$3 10 $CS/acceptance-prompt.md $W
  [[ -f $W/acceptance-report.md ]] && cp $W/acceptance-report.md $J/acceptance-$3.md
}

case $MODE in
noise)
  quality $SRC R2 E0-R2
  quality $R design-pass E0-DP
  log "noise done — $J/results.jsonl"; exit 0 ;;
A|C|Cp) ;;
*) echo "unknown mode $MODE"; exit 2 ;;
esac

[[ -d $R ]] || { git clone -q $SRC $R; git -C $R checkout -q -B main R2; }
cat $BS/sim-user.md $S/oracle-s2.md > $J/sim-user.md
CRS=(CR1:4:sconti:R3:10 CR2:5:pagamenti:R4:11 CR3:6:listini:R5:12 CR4:7:chiusura:R6:13)
started=0
for spec in $CRS; do
  IFS=: read cr v name rel sec <<< "$spec"
  [[ $cr == $FROM ]] && started=1
  (( started )) || continue
  log "$cr ($rel) start"
  f=$S/requisiti-v$v-$name.md
  grep -q "^## $sec\. " $R/REQUISITI.md || { cat $f >> $R/REQUISITI.md; git -C $R add REQUISITI.md
    git -C $R commit -q -m "REQUISITI: sezione $sec"; }
  python3 $H/bench/converse.py --project $R --phase $cr --tag $rel --budget-usd 15 --opening-file $S/open-$cr.md \
    --sim-file $J/sim-user.md --goal "Release $rel = the whole section $sec of REQUISITI.md. Confirm $rel when the builder says it is complete and tested." \
    --model $MODEL --job-dir $J > $J/$cr-converse.json 2>>$J/scenario.log
  record "$(cat $J/$cr-converse.json 2>/dev/null || echo '{}')"
  git -C $R tag -l $rel | grep -q . || { log "STOP: $cr ended without tag $rel"; exit 1; }
  ref=$rel
  if [[ $MODE == C || $MODE == Cp ]]; then
    ap=$BS/architect-prompt.md; [[ $MODE == Cp ]] && ap=$S/architect-decide-prompt.md
    session $cr-architect 3 $ap $R
    session $cr-refactor 8 $BS/refactor-prompt.md $R
    git -C $R tag -f $rel-dp HEAD >/dev/null; ref=$rel-dp
  fi
  acceptance $R $ref $rel
  quality $R $ref $rel
  log "$cr done"
done
log "arm $MODE complete — $J"
