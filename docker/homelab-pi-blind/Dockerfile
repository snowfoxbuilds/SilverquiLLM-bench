FROM node:20-slim

RUN apt-get update && \
    apt-get install -y python3 python3-pip git && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages pytest

RUN apt-get update && \
    apt-get install -y python3 python3-pip git curl && \
    rm -rf /var/lib/apt/lists/*

# Create a local package context for the entrypoint
WORKDIR /app
RUN npm init -y && \
    npm install @earendil-works/pi-coding-agent

COPY models.json /root/.pi/agent/models.json
COPY entrypoint.mjs /app/entrypoint.mjs


ENTRYPOINT ["node", "/app/entrypoint.mjs"]