#!/bin/bash
set -euo pipefail
mkdir -p /output
cp -r /workspace/engine /workspace/engine_work
PROMPT=$(cat /workspace/prompt.md)
PROMPT="${PROMPT}

Make all engine modifications in /workspace/engine_work/ (a working copy of /workspace/engine/).
After implementing each card, write tests in a tests.py file alongside card_impl.py and iterate until they pass. Use pytest to run your tests."
echo "{\"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"event\": \"started\"}" >> /output/progress.jsonl
trap 'echo "{\"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"event\": \"timed_out\"}" >> /output/progress.jsonl; exit 143' SIGTERM
opencode --prompt "${PROMPT}" --dir /workspace \
  > >(tee /output/stdout.log) \
  2> >(tee /output/stderr.log >&2) &
AGENT_PID=$!
set +e
wait $AGENT_PID
EXIT_CODE=$?
set -e
if [ $EXIT_CODE -eq 0 ]; then
  echo "{\"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"event\": \"completed\"}" >> /output/progress.jsonl
else
  echo "{\"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"event\": \"failed\", \"exit_code\": $EXIT_CODE}" >> /output/progress.jsonl
fi
echo $EXIT_CODE > /output/exit_code
exit $EXIT_CODE
