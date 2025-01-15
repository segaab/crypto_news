# Add .dockerignore
COPY .dockerignore .
COPY .env.example .env

# Use multi-stage build
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
    docker build -f Dockerfile.db .
    docker build -f Dockerfile.web .
# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/ /app/requirements/
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY src/ /app/src/
COPY .env.example /app/.env

# Create logs directory
RUN mkdir -p /app/logs

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose ports
EXPOSE 8000
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application
CMD ["python", "-m", "src.main"] 