FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY data_pipeline /app/data_pipeline
COPY quant_engine /app/quant_engine
COPY backend /app/backend
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 "/app/data_pipeline[parquet]" /app/quant_engine /app/backend \
 && useradd --create-home --uid 10001 app && mkdir -p /app/data && chown -R app /app/data
USER app
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=4).status == 200 else 1)"
# Apply migrations, then serve. Ingestion and NAV refresh are explicit jobs (see docs/deployment.md).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
