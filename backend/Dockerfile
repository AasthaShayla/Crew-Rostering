# Backend Dockerfile
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (curl for debugging)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better caching
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application source
COPY backend /app

# Expose backend port (matches backend/run.py default)
EXPOSE 5050

# Optional: pass GROQ_API_KEY at runtime if available
ENV PORT=5050

# Default command uses Flask-SocketIO dev server (sufficient unless you need eventlet/gevent)
CMD ["python", "run.py"]

