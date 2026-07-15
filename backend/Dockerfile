FROM python:3.11-slim

# Create a non-privileged user and group
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -s /bin/bash appuser

WORKDIR /app

# Ensure we install necessary system dependencies for cairosvg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and ensure ownership is set to appuser
COPY --chown=appuser:appgroup . .

# Switch to the non-privileged user
USER appuser

EXPOSE 8000

# Healthcheck checking the local health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import requests, os; r = requests.get(f'http://localhost:{os.getenv(\"PORT\", 8000)}/health'); exit(0 if r.status_code == 200 else 1)" || exit 1

# Launch uvicorn, respecting dynamic Render PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
