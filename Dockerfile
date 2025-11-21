# Use official Python 3.12 slim image
FROM python:3.12-slim

# Install system dependencies for WeasyPrint (CRITICAL)
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --default-timeout=100 --retries 5 -r requirements.txt || \
    { echo "Retrying with pycryptodomex..."; \
      sed -i 's/pycryptodome/pycryptodomex/' requirements.txt; \
      pip install --no-cache-dir -r requirements.txt; }

# Copy project files
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Run using Gunicorn
CMD ["gunicorn", "mnh_approval.wsgi:application", "--bind", "0.0.0.0:8000"]
