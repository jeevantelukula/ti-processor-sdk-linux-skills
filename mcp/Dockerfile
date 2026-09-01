FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# Default variant — override at runtime via env vars.
# All 32 device/OS combos are served dynamically; defaults just set the tool parameter defaults.
ENV TI_SDK_DEFAULT_DEVICE=AM62X
ENV TI_SDK_DEFAULT_OS=linux
ENV TI_SDK_MCP_PORT=7471

EXPOSE 7471

CMD ["python3", "server.py", "--http", "7471"]
