# Candidate code is graded here with no network, no host environment and no
# host files beyond read-only grading inputs; see ADR-013. SilverquiLLM's own
# code arrives as a read-only mount at /opt/sq, so the image holds only Python
# and the pinned pytest closure.
FROM python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285
COPY requirements.txt /tmp/grader-requirements.txt
RUN python -m pip install --no-cache-dir --no-deps --require-hashes -r /tmp/grader-requirements.txt \
    && rm /tmp/grader-requirements.txt \
    && mkdir -p /opt/sq /grade
USER 65534:65534
WORKDIR /tmp
