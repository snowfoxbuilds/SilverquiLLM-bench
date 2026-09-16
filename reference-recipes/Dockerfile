FROM python@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285
RUN apt-get update && apt-get install -y --no-install-recommends git sudo passwd ripgrep libstdc++6 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pytest==8.4.2 iniconfig==2.1.0 packaging==25.0 pluggy==1.6.0 pygments==2.19.2
COPY native/ /opt/native/
COPY bootstrap.py initializer.py adapter.py /opt/benchmark/
ARG ADAPTER
RUN if [ "$ADAPTER" = claude ]; then ln -s /opt/native/claude /usr/local/bin/claude; else ln -s /opt/native/vendor/x86_64-unknown-linux-musl/bin/codex /usr/local/bin/codex; fi
RUN dpkg-query -W > /opt/benchmark/os-packages.txt
