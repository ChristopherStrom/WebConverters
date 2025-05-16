# syntax=docker/dockerfile:1

### 1. Build stage ###
FROM python:3.11-slim AS build

# Install build‑time dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         build-essential \
         ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY . .

### 2. Runtime stage ###
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create a non‑root user
RUN groupadd -r appuser && useradd --no-log-init -r -g appuser appuser

# Create necessary directories and set permissions
RUN mkdir -p /app/static/downloads /app/static/uploads \
    && chmod 777 /app/static/downloads /app/static/uploads

# Copy installed dependencies and code from build stage
WORKDIR /app
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# bring in the pip‑installed console scripts (gunicorn, etc.)
COPY --from=build /usr/local/bin /usr/local/bin

# code
COPY --from=build /app /app

# Ensure proper permissions for app directory
RUN chown -R appuser:appuser /app/static

# Expose the port Gunicorn will listen on
EXPOSE 8080

# Switch to non‑root user
USER appuser

# Command to run the app with Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "3", "--timeout", "300", "--limit-request-line", "0", "--limit-request-fields", "32768"]
