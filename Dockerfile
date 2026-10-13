# syntax=docker/dockerfile:1
FROM node:22.16.0-bookworm-slim AS opencode
ARG TARGETARCH
RUN --mount=type=secret,id=build_ca,mode=0444 \
    if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    case "$TARGETARCH" in amd64) arch=x64 ;; arm64) arch=arm64 ;; *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; esac \
    && npm install --prefix /opt/opencode --ignore-scripts --save-exact "@opencode/cli-linux-${arch}@2.0.23" \
    && cp "/opt/opencode/node_modules/@opencode/cli-linux-${arch}/bin/opencode" /usr/local/bin/opencode

FROM python:3.13.5-slim-bookworm
ARG SLR_EXTRAS=""
RUN --mount=type=secret,id=build_ca,mode=0444 \
    set -eu; \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca REQUESTS_CA_BUNDLE=/run/secrets/build_ca; fi; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources; \
    apt-get -o Acquire::https::CaInfo="${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt}" update \
    && apt-get -o Acquire::https::CaInfo="${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt}" install -y --no-install-recommends ca-certificates git libgomp1 libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.12.23
COPY --from=opencode /usr/local/bin/opencode /usr/local/bin/opencode
WORKDIR /opt/app
COPY . .
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON=/usr/local/bin/python \
    UV_PYTHON_DOWNLOADS=never UV_PYTHON_PREFERENCE=only-system
RUN --mount=type=secret,id=build_ca,mode=0444 \
    set -eu; \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca UV_NATIVE_TLS=true; fi; \
    set -- --extra dev --extra pdf --extra lint; \
    for extra in $SLR_EXTRAS; do \
        case "$extra" in documents|rag) set -- "$@" --extra "$extra" ;; \
            *) echo "Unsupported extra: $extra" >&2; exit 1 ;; esac; \
    done; \
    uv sync --locked --no-editable "$@" \
    && /opt/venv/bin/python scripts/validate_project.py \
    && /opt/venv/bin/python -m pytest -q
RUN chmod -R a+rX /opt/app /opt/venv \
    && useradd --create-home --uid 1000 workbench \
    && mkdir -p /review /backups /state/data /state/config /state/cache /state/state \
    && chown -R workbench:workbench /review /backups /state
ENV PATH="/opt/venv/bin:$PATH" \
    SLR_PROJECT_ROOT=/review SLR_ENVIRONMENT=/opt/venv SLR_SETUP_ENVIRONMENT=/usr/local \
    SLR_ROUTED_LAUNCH=1 SLR_CONTAINER=1 SLR_BACKUP_DIR=/backups \
    XDG_DATA_HOME=/state/data XDG_CONFIG_HOME=/state/config \
    XDG_CACHE_HOME=/state/cache XDG_STATE_HOME=/state/state
USER workbench
WORKDIR /review
ENTRYPOINT ["/opt/venv/bin/python", "/opt/app/scripts/workbench.py"]
CMD ["help"]
