FROM python:3.11-slim AS deps

# Dedicated non-root app user (UID/GID 10001) so the container never runs as root
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin leadagent

WORKDIR /app
COPY requirements.txt .

# Pre-deploy security gate: fail the build if any pinned dependency has a
# known CVE. Because the runtime stage (below) builds FROM this stage, a
# failing audit stops the image build — and thus the deploy.
RUN pip install --no-cache-dir pip-audit \
 && pip-audit -r requirements.txt --progress-spinner off

RUN pip install --no-cache-dir -r requirements.txt

FROM deps

# Build-time git SHA (injected by the deploy/compose build). Reported by
# /api/health as "version" so you can confirm which commit is running.
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

COPY --chown=leadagent:leadagent app ./app
COPY --chown=leadagent:leadagent static ./static

# Serve under path-prefixed routing (Traefik strips /lead-agent)
EXPOSE 8000
USER leadagent
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", "/lead-agent"]