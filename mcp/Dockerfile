FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV TI_PROCESSOR_SDK_DEFAULT_DEVICE=AM62X
ENV TI_PROCESSOR_SDK_DEFAULT_OS=linux
ENV TI_PROCESSOR_SDK_MCP_PORT=7471

EXPOSE 7471

CMD ["python3", "server.py", "--http", "7471"]
