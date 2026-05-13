FROM python:3.12-slim
RUN apt-get update && apt-get install -y git curl diffutils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir opencode-ai pytest
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV OPENCODE_NON_INTERACTIVE=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
ENTRYPOINT ["/entrypoint.sh"]
