# syntax=docker/dockerfile:1

# Kinetic Ledger Phase-2 API
# Compatible with docker compose (api/db/redis) and Cloud Run.
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata and package source BEFORE installing so setuptools
# can discover the kinetic_ledger package (src layout, see pyproject.toml).
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install Python dependencies as editable so the app's filesystem-relative
# paths (/app/data, /app/config, /app/artifacts) resolve correctly at runtime.
RUN pip install --upgrade pip && \
    pip install -e .

# Copy runtime assets
COPY config/ ./config/
COPY data/ ./data/

# Create writable runtime directories
RUN mkdir -p /app/logs /app/artifacts

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/ready || exit 1

# Run the application
CMD ["uvicorn", "kinetic_ledger.api.server:app", "--host", "0.0.0.0", "--port", "8080" , "--reload"]
