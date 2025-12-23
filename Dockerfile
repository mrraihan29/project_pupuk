# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# System deps (psycopg/libpq)
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Collect static assets into STATIC_ROOT (set in settings)
RUN python manage.py collectstatic --noinput

# Non-root runtime user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["gunicorn", "sim_dp.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
