# Portable certminder image built from the published PyPI release, so it needs
# no checkout of this repository. It builds and runs the same on Windows (WSL2),
# macOS and Linux container engines.
#
#   docker compose up -d --build
FROM python:3.13-slim

# 3.13+ lets certinspect expose the server-presented chain
# (get_unverified_chain) and explain why an untrusted chain failed.
# Unbuffered so log lines appear immediately in `docker logs`, not buffered.
ENV PYTHONUNBUFFERED=1

# Pin the release for reproducible rebuilds; bump this to upgrade. Installing
# certminder pulls a compatible certinspect (>= 2.4.5) from PyPI.
RUN pip install --no-cache-dir "certminder==2.5.2" \
    && useradd --system --no-create-home --uid 10001 certminder \
    && mkdir -p /var/lib/certminder \
    && chown certminder:certminder /var/lib/certminder

USER certminder
VOLUME ["/var/lib/certminder"]

ENTRYPOINT ["certminder"]
CMD ["run", "-c", "/etc/certminder/certminder.yml"]
