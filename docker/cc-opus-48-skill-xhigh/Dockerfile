FROM node:20-slim

RUN apt-get update && \
    apt-get install -y python3 python3-pip git curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages pytest

RUN npm install -g @anthropic-ai/claude-code

ENV CLAUDE_CODE_DISABLE_TELEMETRY=1

# xhigh effort pushes more tokens per turn; give the model headroom so a long
# turn ends on its own rather than being truncated with stop_reason: max_tokens.
ENV CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000

# Pre-trust the staged workspace so the agent does not waste tokens on git safe.directory recovery.
# Use --system so it applies to whichever user runs the container.
RUN git config --system --add safe.directory /workspace

WORKDIR /app

# Skill (the implement-mtg-card playbook + grep-rulebook) and the card-verifier
# subagent — copied into ~/.claude/ at container startup. This is the ONLY
# difference from the bare image: a single agent runs (no --agent), but it has
# the playbook skill and can spawn the verifier via the Task tool.
COPY skills/ /app/skills/
COPY agents/ /app/agents/

COPY entrypoint.mjs /app/entrypoint.mjs

# Claude Code refuses --dangerously-skip-permissions when running as root.
# The node:20-slim base image already provides a `node` user (uid 1000).
USER node

ENTRYPOINT ["node", "/app/entrypoint.mjs"]
