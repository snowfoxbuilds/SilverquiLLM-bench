#!/bin/bash
set -euo pipefail

PROGRESS_FILE="/output/progress.jsonl"

# ── progress helpers ────────────────────────────────────────────────
emit_progress() {
  # Usage: emit_progress '{"event":"started"}'  (ts is prepended automatically)
  local payload="$1"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  # Merge ts into the JSON object (insert after opening brace)
  echo "${payload/\{/\{\"ts\": \"$ts\", }" >> "$PROGRESS_FILE"
}

# Background card watcher: polls for card_impl.py changes every 10s
# Uses mtime comparison against initial snapshot to avoid false positives
# from SOS templates that already contain class/def stubs.
card_watcher() {
  local -A seen_cards  # tracks cards we already emitted card_started for
  local -A completed_cards  # tracks cards we already emitted card_completed for
  local -A last_mtime  # tracks mtime from previous poll for stability check
  while true; do
    for impl in /workspace/cards/sos/*/card_impl.py; do
      [ -f "$impl" ] || continue
      local card_dir
      card_dir="$(dirname "$impl")"
      local card_id
      card_id="$(basename "$card_dir")"
      # Determine card name from card_spec.json if available
      local card_name=""
      if [ -f "$card_dir/card_spec.json" ]; then
        card_name=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('name',''))" "$card_dir/card_spec.json" 2>/dev/null || true)
      fi
      # Compare current mtime against initial snapshot
      local current_mtime
      current_mtime="$(stat -c '%Y' "$impl" 2>/dev/null || echo 0)"
      local initial_mtime
      initial_mtime="$(grep " ${impl}$" /tmp/card_mtimes_initial.txt 2>/dev/null | cut -d' ' -f1 || echo 0)"
      # Card started: mtime changed from initial snapshot (agent modified the file)
      if [ "$current_mtime" != "$initial_mtime" ] && [ -z "${seen_cards[$card_id]+x}" ]; then
        seen_cards[$card_id]=1
        last_mtime[$card_id]="$current_mtime"
        if [ -n "$card_name" ]; then
          emit_progress "{\"event\": \"card_started\", \"card_id\": \"$card_id\", \"card_name\": \"$card_name\"}"
        else
          emit_progress "{\"event\": \"card_started\", \"card_id\": \"$card_id\"}"
        fi
      fi
      # Card completed: started and mtime stable since last poll
      if [ -n "${seen_cards[$card_id]+x}" ] && [ -z "${completed_cards[$card_id]+x}" ]; then
        if [ "${last_mtime[$card_id]:-0}" = "$current_mtime" ]; then
          completed_cards[$card_id]=1
          emit_progress "{\"event\": \"card_completed\", \"card_id\": \"$card_id\"}"
        else
          last_mtime[$card_id]="$current_mtime"
        fi
      fi
    done
    sleep 10
  done
}

# ── main ────────────────────────────────────────────────────────────
mkdir -p /output
cp -r /workspace/engine /workspace/engine_work
PROMPT=$(cat /workspace/prompt.md)
PROMPT="${PROMPT}

Make all engine modifications in /workspace/engine_work/ (a working copy of /workspace/engine/).
After implementing each card, write tests in a tests.py file alongside card_impl.py and iterate until they pass. Use pytest to run your tests."

emit_progress '{"event": "started"}'

# Snapshot initial mtimes so watcher can detect agent modifications
find /workspace/cards/sos/*/card_impl.py -exec stat -c '%Y %n' {} \; > /tmp/card_mtimes_initial.txt 2>/dev/null || true

trap 'emit_progress "{\"event\": \"timed_out\"}"; kill "$WATCHER_PID" 2>/dev/null || true; exit 143' SIGTERM

# Start card watcher in background
card_watcher &
WATCHER_PID=$!

opencode --prompt "${PROMPT}" --dir /workspace \
  > >(tee /output/stdout.log) \
  2> >(tee /output/stderr.log >&2) &
AGENT_PID=$!
set +e
wait $AGENT_PID
EXIT_CODE=$?
set -e

# Stop card watcher
kill "$WATCHER_PID" 2>/dev/null || true
wait "$WATCHER_PID" 2>/dev/null || true

# Final scan to catch any last card modifications missed by the watcher
for impl in /workspace/cards/sos/*/card_impl.py; do
  [ -f "$impl" ] || continue
  card_dir="$(dirname "$impl")"
  card_id="$(basename "$card_dir")"
  current_mtime="$(stat -c '%Y' "$impl" 2>/dev/null || echo 0)"
  initial_mtime="$(grep " ${impl}$" /tmp/card_mtimes_initial.txt 2>/dev/null | cut -d' ' -f1 || echo 0)"
  if [ "$current_mtime" != "$initial_mtime" ]; then
    emit_progress "{\"event\": \"card_completed\", \"card_id\": \"$card_id\"}"
  fi
done

if [ $EXIT_CODE -eq 0 ]; then
  emit_progress '{"event": "completed"}'
else
  emit_progress "{\"event\": \"failed\", \"exit_code\": $EXIT_CODE}"
fi
echo $EXIT_CODE > /output/exit_code
exit $EXIT_CODE
