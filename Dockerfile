# certwatch container image.
#
# Build:
#   docker build -t certwatch .
# Run a single cycle (cron-style), config and state mounted from the host:
#   docker run --rm \
#     -v "$PWD/certwatch.yml:/etc/certwatch/certwatch.yml:ro" \
#     -v certwatch-state:/var/lib/certwatch \
#     certwatch once -c /etc/certwatch/certwatch.yml
# Run as a daemon (the default CMD):
#   docker run -d --name certwatch \
#     -v "$PWD/certwatch.yml:/etc/certwatch/certwatch.yml:ro" \
#     -v certwatch-state:/var/lib/certwatch \
#     certwatch

FROM python:3.12-slim AS build

WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
# Build a wheel so the final image carries no build sources or caches.
RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /dist

FROM python:3.12-slim

# certwatch shells out to certinspect; both come from PyPI via the wheel's deps.
COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl certinspect \
    && rm -rf /tmp/*.whl \
    && useradd --system --no-create-home --uid 10001 certwatch \
    && mkdir -p /var/lib/certwatch \
    && chown certwatch:certwatch /var/lib/certwatch

USER certwatch
VOLUME ["/var/lib/certwatch"]

ENTRYPOINT ["certwatch"]
CMD ["run", "-c", "/etc/certwatch/certwatch.yml"]
