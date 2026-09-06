# Multi-stage Dockerfile for Recoup AI Recovery Engine
# ── Stage 1: Build React SPA Frontend ──────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY recoup/frontend/package*.json ./
RUN npm ci
COPY recoup/frontend ./
RUN npm run build

# ── Stage 2: Production Python Backend + Static Bundle ─────────
FROM python:3.11-slim
WORKDIR /app

# Prevent Python from writing pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    CORS_ORIGINS="*" \
    DATABASE_URL="sqlite+aiosqlite:///./recoup.db"

# Install backend dependencies
COPY recoup/backend/requirements.txt ./recoup/backend/requirements.txt
RUN pip install --no-cache-dir -r ./recoup/backend/requirements.txt

# Copy application backend, policies, and seed scripts
COPY recoup/backend ./recoup/backend
COPY policies ./policies

# Copy compiled React frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./recoup/frontend/dist

# Expose web port
EXPOSE 8000

WORKDIR /app/recoup/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
