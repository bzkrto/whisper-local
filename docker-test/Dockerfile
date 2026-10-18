FROM python:3.12-slim
RUN --mount=type=secret,id=proxy_ca \
    set -eu; \
    if [ -f /run/secrets/proxy_ca ]; then \
      apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update; \
    else apt-get update; fi; \
    apt-get install -y --no-install-recommends fonts-dejavu-core; \
    rm -rf /var/lib/apt/lists/*
COPY requirements-test.txt /opt/requirements-test.txt
RUN --mount=type=secret,id=proxy_ca \
    set -eu; \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python -m pip install --no-cache-dir -r /opt/requirements-test.txt
LABEL org.whisper.test-runtime="v32.13"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /candidate
