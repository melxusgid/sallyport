# Stage 1: Install system deps + Python deps
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
COPY sallyport/ sallyport/

# Install Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn pydantic playwright tilion-fortress

# Install Playwright system deps and Chromium browser
RUN playwright install --with-deps chromium

# Stage 2: Runtime image
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python environment from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Runtime also needs Chromium/Fortress shared libraries; the builder's apt packages
# do not carry into this final slim image.
RUN playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Copy application
COPY sallyport/ sallyport/
COPY pyproject.toml .

# Expose Sallyport API port
EXPOSE 9378

# Environment defaults
ENV SALLYPORT_HOST=0.0.0.0
ENV SALLYPORT_PORT=9378
ENV FORT_CHANNEL=stable
ENV FORT_PORT=9222

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:9378/health || exit 1

CMD ["python3", "-m", "sallyport.server"]
