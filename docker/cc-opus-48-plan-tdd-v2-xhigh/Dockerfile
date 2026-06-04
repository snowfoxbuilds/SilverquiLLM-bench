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

# Two-phase plan->TDD flow. The entrypoint runs TWO sequential single-agent
# `claude -p` sessions in /workspace, sharing state only through PLAN.md:
#   Phase 1 (planner): reads specs + engine + rulebook, identifies engine gaps
#     and an implementation sequence, writes /workspace/PLAN.md (no code).
#   Phase 2 (implementer): treats the requirements (card_spec.json + RULEBOOK.txt)
#     as its contract and PLAN.md only as a sequencing guide it may overrule;
#     implements every card with TDD and validates against the spec via the real engine.
# No subagents and no --agent — just two top-level agents handing off via the
# filesystem. Skills installed: tdd + grep-rulebook + implement-mtg-card.
COPY skills/ /app/skills/
COPY phase1_planner.md /app/phase1_planner.md
COPY phase2_implementer.md /app/phase2_implementer.md
COPY entrypoint.mjs /app/entrypoint.mjs

# Claude Code refuses --dangerously-skip-permissions when running as root.
# The node:20-slim base image already provides a `node` user (uid 1000).
USER node

ENTRYPOINT ["node", "/app/entrypoint.mjs"]
