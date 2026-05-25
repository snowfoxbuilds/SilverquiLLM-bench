FROM node:20-slim

RUN apt-get update && \
    apt-get install -y python3 python3-pip git curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages pytest

RUN npm install -g @github/copilot

# Pre-trust the staged workspace so the agent does not waste tokens on git safe.directory recovery.
RUN git config --global --add safe.directory /workspace

WORKDIR /app

# Custom skills and agents — copied into ~/.copilot/ at container startup
COPY skills/ /app/skills/
COPY agents/ /app/agents/

COPY entrypoint.mjs /app/entrypoint.mjs

ENV COPILOT_PROVIDER_BASE_URL="http://localhost:8080"
ENV COPILOT_MODEL=local

ENTRYPOINT ["node", "/app/entrypoint.mjs"]
