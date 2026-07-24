FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/storage/uploads /app/storage/outputs

EXPOSE 8000

# Render (and some other PaaS) inject $PORT and expect the process to bind
# to it. Defaults to 8000 for local `docker run` / docker-compose use.
#
# Gunicorn manages several Uvicorn worker *processes* so multiple users'
# parse/convert jobs run in true parallel instead of queuing behind each
# other on a single process (see the sizing notes in docker-compose.yml).
# WEB_CONCURRENCY controls the worker count - default 4, tune to your CPU
# count. --timeout is raised well above Gunicorn's 30s default since a
# large firewall config parse can legitimately take longer than that.
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-4} --timeout 120 --graceful-timeout 30 --access-logfile - --error-logfile -"]
