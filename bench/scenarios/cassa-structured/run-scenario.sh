#!/bin/zsh
# run-scenario.sh — the cassa-structured scenario (scenario.md), phase by phase, strictly in sequence.
#   run-scenario.sh <run-dir> [--from <phase>]      phases: A1 A2 B C D E1 E2 E3 F
# A phase whose outcome is not the expected one stops the scenario (exit 1): analyse, then --from it.
# Logs and results: $J (default ~/.claude/jobs/<run-name>-scenario/), never inside the run folder.
set -u
S=${0:A:h}; H=${S:h:h:h}; P=$H/plugins/mismagent; TOOL=$P/tools/mismagent.py
R=${1:?usage: run-scenario.sh <run-dir> [--from <phase>]}; R=${R:A}
FROM=A1; [[ ${2:-} == --from ]] && FROM=${3:?--from needs a phase}
J=${J:-$HOME/.claude/jobs/${R:t}-scenario}; mkdir -p $J
POLICY="$(cat $S/sim-policy.md)"
MODEL=${MODEL:-sonnet}
export CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
PHASES=(A1 A2 B C D E1 E2 E3 F)
(( ${PHASES[(Ie)$FROM]} )) || { echo "unknown phase $FROM"; exit 2; }

log() { print -r -- "$(date +%H:%M:%S) $*" | tee -a $J/scenario.log; }
frictions() { local n; n=$(grep -c '^## #' $R/MISMAGENT-LOG.md 2>/dev/null); print ${n:-0}; }
record() {  # phase outcome cost start
  python3 -c "import json,sys,time;print(json.dumps({'phase':sys.argv[1],'outcome':sys.argv[2],'cost_usd':float(sys.argv[3]),
    'start':sys.argv[4],'end':time.strftime('%Y-%m-%dT%H:%M:%S'),'frictions':int(sys.argv[5])}))" \
    "$1" "$2" "$3" "$4" "$(frictions)" >> $J/phases.jsonl
  git -C $R add -A && git -C $R commit -q -m "scenario: phase $1 ($2) [skip-readme]" 2>/dev/null
  log "phase $1: $2, \$$3"
}
fail() { record "$1" "$2" "${3:-0}" "$4"; log "STOP at phase $1: $2 — analyse, then: run-scenario.sh $R --from $1"; exit 1; }

headless() {  # name budget prompt  → echoes cost; exit status 0 iff the session ended without error
  local out=$J/$1.json
  (cd $R && claude -p --plugin-dir $P --model $MODEL --permission-mode bypassPermissions --output-format json \
     --max-budget-usd $2 "$3" > $out 2>&1)
  python3 - "$out" <<'EOF'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print(0); sys.exit(1)
print(round(d.get("total_cost_usd", 0), 4)); sys.exit(1 if d.get("is_error") else 0)
EOF
}
build() {  # name feature budget release → echoes "outcome cost"
  local out=$J/$1.json
  python3 $H/bench/run.py --project $R --feature $2 --plugin-dir $P --total-usd $3 --model $MODEL \
    --permission-mode bypassPermissions --prompt-file $J/sim-policy.md --until-release $4 > $out 2>&1
  python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['outcome'],round(d['total_cost_usd'],4))" $out 2>/dev/null \
    || echo "runner-error 0"
}
lint_ok() { python3 $TOOL lint $R/.mismagent/features/$1 >/dev/null 2>&1; }
manifest() { print $R/.mismagent/features/$1/building-blocks.yaml; }
append_once() {  # file marker → append the file to REQUISITI.md once, committed as the user's change
  grep -q "$2" $R/REQUISITI.md || { cat $1 >> $R/REQUISITI.md; git -C $R add REQUISITI.md;
    git -C $R commit -q -m "REQUISITI: $2 [skip-readme]"; }
}
cp $S/sim-policy.md $J/sim-policy.md
started=0
for ph in $PHASES; do
  [[ $ph == $FROM ]] && started=1
  (( started )) || continue
  t0=$(date +%Y-%m-%dT%H:%M:%S); log "phase $ph start"
  case $ph in
  A1) c=$(headless A1-explore 6 "/mismagent:explore Registratore di cassa per il bar dell'oratorio, secondo REQUISITI.md. Usa come nome della feature: cassa.

$POLICY") || fail A1 cli-error "$c" $t0
      [[ -f $R/.mismagent/profile.md && -f $R/.mismagent/features/cassa/product-brief.md ]] || fail A1 missing-artifact "$c" $t0
      record A1 ok $c $t0 ;;
  A2) c=$(headless A2-model 14 "/mismagent:model cassa

$POLICY") || fail A2 cli-error "$c" $t0
      [[ -f $(manifest cassa) ]] && lint_ok cassa || fail A2 manifest-not-clean "$c" $t0
      record A2 ok $c $t0 ;;
  B)  read o c <<< "$(build B-build cassa 60 R0)"; [[ $o == released ]] || fail B $o $c $t0; record B $o $c $t0 ;;
  C)  append_once $S/requisiti-v2.md "Modifiche v2"
      h0=$(shasum < $(manifest cassa))
      c=$(headless C-change 15 "/mismagent:model cassa

REQUISITI.md è cambiato: la sezione 8 «Modifiche v2» è una richiesta di modifica (IVA per categoria) da recepire in R1. Recepiscila.

$POLICY") || fail C cli-error "$c" $t0
      [[ $(shasum < $(manifest cassa)) != $h0 ]] && lint_ok cassa || fail C manifest-unchanged-or-not-clean "$c" $t0
      record C ok $c $t0 ;;
  D)  read o c <<< "$(build D-build cassa 50 R1)"; [[ $o == released ]] || fail D $o $c $t0; record D $o $c $t0 ;;
  E1) append_once $S/requisiti-v3-magazzino.md "Magazzino (v3"
      c=$(headless E1-explore 8 "/mismagent:explore Magazzino del bar dell'oratorio, secondo la sezione 9 di REQUISITI.md. Usa come nome della feature: magazzino.

$POLICY") || fail E1 cli-error "$c" $t0
      [[ -f $R/.mismagent/features/magazzino/product-brief.md ]] || fail E1 missing-artifact "$c" $t0
      record E1 ok $c $t0 ;;
  E2) c=$(headless E2-model 14 "/mismagent:model magazzino

$POLICY") || fail E2 cli-error "$c" $t0
      [[ -f $(manifest magazzino) ]] && lint_ok magazzino || fail E2 manifest-not-clean "$c" $t0
      record E2 ok $c $t0 ;;
  E3) rel=$(grep -oE '^ *release: *"?R[0-9]+' $(manifest magazzino) | grep -oE 'R[0-9]+' | sort -u)
      [[ $(print -l $rel | wc -l | tr -d ' ') == 1 ]] || fail E3 "magazzino-releases:${rel//$'\n'/,}" 0 $t0
      read o c <<< "$(build E3-build magazzino 50 $rel)"; [[ $o == released ]] || fail E3 $o $c $t0; record E3 $o $c $t0 ;;
  F)  tag=$(git -C $R tag --sort=-creatordate | head -1); [[ -n $tag ]] || fail F no-release-tag 0 $t0
      W=$J/acceptance-wt; git -C $R worktree remove --force $W 2>/dev/null; git -C $R worktree add -q --detach $W $tag
      cp $S/acceptance.md $W/ACCEPTANCE.md
      (cd $W && claude -p --model $MODEL --permission-mode bypassPermissions --output-format json --max-budget-usd 10 \
         "$(cat $S/acceptance-prompt.md)" > $J/F-acceptance.json 2>&1)
      c=$(python3 -c "import json,sys;print(round(json.load(open(sys.argv[1])).get('total_cost_usd',0),4))" $J/F-acceptance.json 2>/dev/null || echo 0)
      [[ -f $W/acceptance-report.md ]] || fail F no-report $c $t0
      cp $W/acceptance-report.md $J/acceptance-report.md; record F "ok:$tag" $c $t0 ;;
  esac
done
log "scenario complete — results in $J"
