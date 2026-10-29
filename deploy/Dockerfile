FROM python:3.11-slim

LABEL maintainer="AetherSelf Edge AI Team"
LABEL description="Autonomous Self-Healing Edge Agent Framework"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AETHERSELF_HOST=0.0.0.0 \
    AETHERSELF_PORT=8765

WORKDIR /app

# Install minimal edge system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml setup.py /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir psutil scikit-learn pydantic fastapi uvicorn rich numpy chromadb

COPY aetherself/ /app/aetherself/
COPY web/ /app/web/
RUN pip install --no-cache-dir -e .

EXPOSE 8765

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8765/api/status || exit 1

ENTRYPOINT ["aetherself", "start", "--host", "0.0.0.0", "--port", "8765"]
