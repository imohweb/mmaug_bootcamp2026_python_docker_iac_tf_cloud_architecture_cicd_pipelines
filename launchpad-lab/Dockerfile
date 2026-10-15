FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app app.py .
COPY --chown=app:app ai_demo.py .
COPY --chown=app:app templates/ templates/
COPY --chown=app:app static/ static/
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s \
    --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; \
urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" \
    || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", \
     "--access-logfile", "-", "--error-logfile", "-", "app:app"]
