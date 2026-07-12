FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# SQLite DB file lives here - mount a volume at /app/data in production
# so conversation memory survives container restarts/redeploys.
ENV DB_PATH=/app/data/luniq_memory.db
RUN mkdir -p /app/data

EXPOSE 8000

# 4 gunicorn workers with uvicorn's worker class is a reasonable starting
# point for ~100 users on a single small/medium instance. Tune worker count
# to your CPU cores (roughly 2 x cores + 1).
CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
