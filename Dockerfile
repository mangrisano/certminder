# certminder container image.
#
# Build:
#   docker build -t certminder .
# Run a single cycle (cron-style), config and state mounted from the host:
#   docker run --rm \
#     -v "$PWD/certminder.yml:/etc/certminder/certminder.yml:ro" \
#     -v certminder-state:/var/lib/certminder \
#     certminder once -c /etc/certminder/certminder.yml
# Run as a daemon (the default CMD):
#   docker run -d --name certminder \
#     -v "$PWD/certminder.yml:/etc/certminder/certminder.yml:ro" \
#     -v certminder-state:/var/lib/certminder \
#     certminder

FROM python:3.12-slim AS build

WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
# Build a wheel so the final image carries no build sources or caches.
RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /dist

FROM python:3.12-slim

# certminder shells out to certinspect; both come from PyPI via the wheel's deps.
COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl certinspect \
    && rm -rf /tmp/*.whl \
    && useradd --system --no-create-home --uid 10001 certminder \
    && mkdir -p /var/lib/certminder \
    && chown certminder:certminder /var/lib/certminder

USER certminder
VOLUME ["/var/lib/certminder"]

ENTRYPOINT ["certminder"]
CMD ["run", "-c", "/etc/certminder/certminder.yml"]
