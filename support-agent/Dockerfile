# Stage 1: build the React frontend into static files.
FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Stage 2: Python API (Flask + Gunicorn) that also serves the built frontend.
FROM python:3.12-slim AS backend
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DATA_DIR=/data \
    FRONTEND_DIST=/app/frontend-dist \
    KNOWLEDGE_SEED_DIR=/app/knowledge-seed
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /data && chown app:app /data
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app backend/app.py backend/ai_client.py backend/knowledge.py \
     backend/storage.py backend/support_agent.py backend/tickets.py backend/seed_knowledge.py ./
# Offline seed only: in Azure the agent reads knowledge from Blob Storage.
COPY --chown=app:app knowledge/ knowledge-seed/
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s \
    --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; \
urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" \
    || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", \
     "--access-logfile", "-", "--error-logfile", "-", "app:app"]

FROM node:22-alpine AS frontend
WORKDIR /app
ENV PORT=8000
COPY --chown=node:node --from=frontend-build /frontend/dist/ ./dist/
COPY --chown=node:node frontend/server.mjs ./
USER node
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:8000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.mjs"]

# The default target retains the single-container local Docker/Terraform lab.
FROM backend AS combined
COPY --chown=app:app --from=frontend-build /frontend/dist/ frontend-dist/
