FROM artifactory.itg.ti.com/docker-public/python:3.11-slim

WORKDIR /app

ENV http_proxy=http://webproxy.ext.ti.com:80 \
    https_proxy=http://webproxy.ext.ti.com:80 \
    ftp_proxy=http://webproxy.ext.ti.com:80 \
    no_proxy=localhost,127.0.0.1,ti.com

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV TI_PROCESSOR_SDK_DEFAULT_DEVICE=AM62X
ENV TI_PROCESSOR_SDK_DEFAULT_OS=linux
ENV TI_PROCESSOR_SDK_MCP_PORT=7471

EXPOSE 7471

# Liveness only: /health is served by the same app as /mcp and makes no outbound
# calls (GET /mcp answers 406 by design). Startup measured at ~0.7 s; 10 s grace.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7471/health', timeout=2)" || exit 1

CMD ["python3", "server.py", "--http", "7471"]
