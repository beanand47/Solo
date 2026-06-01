FROM python:3.11-slim

WORKDIR /app
ENV PORT=8080

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos "" solouser
RUN chown -R solouser:solouser /app
USER solouser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8080}/health" || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers ${WEB_CONCURRENCY:-1}"]
