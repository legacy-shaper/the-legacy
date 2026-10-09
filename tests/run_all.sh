#!/usr/bin/env bash
# Runs every test suite in parallel (each suite has its own local port) and stops the publish if one fails.
# Usage: bash tests/run_all.sh        → prints one line per suite, exit code 0 only if all passed.
cd "$(dirname "$0")/.." || exit 1
export PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}
out=$(mktemp -d)
ls tests/test_*.py | xargs -P 6 -I{} sh -c 'n=$(basename {} .py); timeout 900 python3 {} > "'"$out"'/$n.log" 2>&1; echo $? > "'"$out"'/$n.rc"'
fail=0
for rc in "$out"/*.rc; do n=$(basename "$rc" .rc); r=$(cat "$rc"); last=$(grep -E "FAIL|ALL|passed|Error" "$out/$n.log" | tail -1)
  if [ "$r" = "0" ] && ! grep -q "^FAIL" "$out/$n.log"; then echo "ok   $n — $last"; else echo "FAIL $n — $last"; fail=1; fi; done
exit $fail
