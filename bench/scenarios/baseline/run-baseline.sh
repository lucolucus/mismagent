#!/bin/zsh
# run-baseline.sh — E0: the cassa scenario built by plain Claude Code (no plugin), a simulated user
# answering in turns (converse.py). Phases, strictly in sequence:
#   B build → R0 · C change request v2 + build → R1 · E second feature magazzino → R2 ·
#   F external acceptance at the last tag · G blind code-quality review at the last tag.
#   run-baseline.sh <run-dir> [--from <phase>]      (run-dir must hold REQUISITI.md, the v1 text)
# Results: $J (default ~/.claude/jobs/<run-name>-baseline/), never inside the run folder.
set -u
S=${0:A:h}; H=${S:h:h:h}; CS=${S:h}/cassa-structured
R=${1:?usage: run-baseline.sh <run-dir> [--from <phase>]}; R=${R:A}
FROM=B; [[ ${2:-} == --from ]] && FROM=${3:?--from needs a phase}
J=${J:-$HOME/.claude/jobs/${R:t}-baseline}; mkdir -p $J
MODEL=${MODEL:-sonnet}
export CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
PHASES=(B C E F G)
(( ${PHASES[(Ie)$FROM]} )) || { echo "unknown phase $FROM"; exit 2; }
[[ -f $R/REQUISITI.md ]] || { echo "$R/REQUISITI.md missing"; exit 2; }
[[ -d $R/.mismagent ]] && { echo "$R is not a clean baseline folder"; exit 2; }

log() { print -r -- "$(date +%H:%M:%S) $*" | tee -a $J/scenario.log; }
record() {  # phase outcome cost start [extra-json]
  python3 -c "import json,sys,time;d={'phase':sys.argv[1],'outcome':sys.argv[2],'cost_usd':float(sys.argv[3]),
    'start':sys.argv[4],'end':time.strftime('%Y-%m-%dT%H:%M:%S')};d.update(json.loads(sys.argv[5]));print(json.dumps(d))" \
    "$1" "$2" "$3" "$4" "${5:-{\}}" >> $J/phases.jsonl
  log "phase $1: $2, \$$3"
}
fail() { record "$1" "$2" "${3:-0}" "$4"; log "STOP at phase $1: $2 — analyse, then: run-baseline.sh $R --from $1"; exit 1; }
append_once() {  # file marker → append to REQUISITI.md once, committed as the user's change
  grep -q "$2" $R/REQUISITI.md || { cat $1 >> $R/REQUISITI.md; git -C $R add REQUISITI.md;
    git -C $R commit -q -m "REQUISITI: $2"; }
}
converse() {  # phase tag budget opening goal → records the phase; stops the scenario unless released
  local out=$J/$1-converse.json o c x
  python3 $H/bench/converse.py --project $R --phase $1 --tag $2 --budget-usd $3 --opening-file $S/$4 \
    --sim-file $S/sim-user.md --goal "$5" --model $MODEL --job-dir $J > $out 2>>$J/scenario.log
  o=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['outcome'])" $out 2>/dev/null || echo runner-error)
  c=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['total_cost_usd'])" $out 2>/dev/null || echo 0)
  x=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(json.dumps({k:d[k] for k in ('turns','questions','policy_gaps','builder_usd','sim_usd')}))" $out 2>/dev/null || echo '{}')
  [[ $o == released ]] || fail $1 $o $c $t0
  record $1 $o $c $t0 "$x"
}
judge() {  # phase prompt-file report budget → a fresh session, no plugin, at the last tag
  local tag W c
  tag=$(git -C $R tag --sort=-creatordate | head -1); [[ -n $tag ]] || fail $1 no-release-tag 0 $t0
  W=$J/$1-wt; git -C $R worktree remove --force $W 2>/dev/null; git -C $R worktree add -q --detach $W $tag
  [[ $1 == F ]] && cp $CS/acceptance.md $W/ACCEPTANCE.md
  (cd $W && claude -p --model $MODEL --permission-mode bypassPermissions --output-format json --max-budget-usd $4 \
     "$(cat $2)" > $J/$1-judge.json 2>&1)
  c=$(python3 -c "import json,sys;print(round(json.load(open(sys.argv[1])).get('total_cost_usd',0),4))" $J/$1-judge.json 2>/dev/null || echo 0)
  [[ -f $W/$3 ]] || fail $1 no-report $c $t0
  cp $W/$3 $J/$3; record $1 "ok:$tag" $c $t0
}

if [[ ! -d $R/.git ]]; then
  git -C $R init -q -b main; cp $S/CLAUDE.md $R/CLAUDE.md
  git -C $R add -A; git -C $R commit -q -m "baseline: requirements and CLAUDE.md"
fi
started=0
for ph in $PHASES; do
  [[ $ph == $FROM ]] && started=1
  (( started )) || continue
  t0=$(date +%Y-%m-%dT%H:%M:%S); log "phase $ph start"
  case $ph in
  B) converse B R0 30 open-B.md "Release R0 (the release cut in the builder's first message). Confirm R0 when the builder says it is complete and tested." ;;
  C) append_once $CS/requisiti-v2.md "Modifiche v2"
     converse C R1 25 open-C.md "Release R1 = the rest of sections 3-6 including the v2 change (section 8). Confirm R1 when the builder says it is complete and tested." ;;
  E) append_once $CS/requisiti-v3-magazzino.md "Magazzino (v3"
     converse E R2 25 open-E.md "Release R2 = the whole Magazzino section (9). Confirm R2 when the builder says it is complete and tested." ;;
  F) judge F $CS/acceptance-prompt.md acceptance-report.md 10 ;;
  G) judge G $S/quality-review-prompt.md quality-report.md 5 ;;
  esac
done
log "baseline complete — results in $J"
