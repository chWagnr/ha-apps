FROM python:3.14-slim-bookworm

ARG BUILD_VERSION=0.1.1
ARG BUILD_ARCH=amd64
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="addon" \
      io.hass.arch="${BUILD_ARCH}" \
      org.opencontainers.image.title="Nextcloud MCP" \
      org.opencontainers.image.description="Home Assistant packaging for nc_mcp_server" \
      org.opencontainers.image.source="https://github.com/chWagnr/hassio-addons" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt
COPY addon.py setup.html setup.js ./
EXPOSE 3738
CMD ["python", "addon.py"]
