# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on
WORKDIR /app

# System dependencies (includes Cairo toolchain for PDF rendering)
RUN apt-get update \
&& apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    wget \
    libcairo2-dev \
    libffi-dev \
    pkg-config \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-0 \
&& rm -rf /var/lib/apt/lists/*

# Install dependencies (cache-friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Create writable static directory
RUN mkdir -p /staticfiles

# Copy project source
COPY . .

EXPOSE 8000

# Runtime entrypoint: migrate, collectstatic, start gunicorn
ENTRYPOINT ["/bin/sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn sim_dp.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout ${GUNICORN_TIMEOUT:-120}"]