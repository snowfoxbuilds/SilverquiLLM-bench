FROM node:20-slim

RUN apt-get update && \
    apt-get install -y python3 python3-pip git curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages pytest

RUN npm install -g @anthropic-ai/claude-code

ENV CLAUDE_CODE_DISABLE_TELEMETRY=1
ENV CLAUDE_CODE_DISABLE_1M_CONTEXT=1

# Pre-trust the staged workspace so the agent does not waste tokens on git safe.directory recovery.
# Use --system so it applies to whichever user runs the container.
RUN git config --system --add safe.directory /workspace

WORKDIR /app

# Custom skills and agents — copied into ~/.claude/ at container startup
COPY skills/ /app/skills/
COPY agents/ /app/agents/

COPY entrypoint.mjs /app/entrypoint.mjs

# Claude Code refuses --dangerously-skip-permissions when running as root.
# The node:20-slim base image already provides a `node` user (uid 1000).
USER node

ENTRYPOINT ["node", "/app/entrypoint.mjs"]
