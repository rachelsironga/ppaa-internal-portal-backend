# Base overridable when registries fail (DNS / TLS), e.g. in `.env` or compose `DOCKER_PYTHON_IMAGE`:
#   public.ecr.aws/docker/library/python:3.12-slim   (AWS mirror)
#   python:3.12-slim                                 (Docker Hub, needs auth.docker.io)
# Default: Google mirror of docker.io/library/python — often resolves when ECR / Hub do not.
ARG PYTHON_IMAGE=mirror.gcr.io/library/python:3.12-slim
FROM ${PYTHON_IMAGE}

# Install system dependencies for WeasyPrint (CRITICAL) + gosu (drop root in entrypoint)
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libcairo-gobject2 \
    libgobject-2.0-0 \
    libglib2.0-0 \
    libharfbuzz0b \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    wget \
    libmagic1 \
    gcc \
    python3-dev \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    gosu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=ppaa_portal.settings

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --default-timeout=100 --retries 5 -r requirements.txt || \
    { echo "Retrying with pycryptodomex..."; \
      sed -i 's/pycryptodome/pycryptodomex/' requirements.txt; \
      pip install --no-cache-dir -r requirements.txt; }

# Entrypoint outside /app so `docker compose` bind-mount ./:/app cannot strip execute permission
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Copy project files
COPY . .

RUN python manage.py collectstatic --noinput || true

# Non-root user; own /app after collectstatic so static tree is writable by app at runtime
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /usr/sbin/nologin --home-dir /app app \
    && chown -R app:app /app

ENTRYPOINT ["/docker-entrypoint.sh"]
# Default process (override in compose for Celery)
# Run using Gunicorn

CMD ["gunicorn", "ppaa_portal.wsgi:application", "--bind", "0.0.0.0:8000"]
