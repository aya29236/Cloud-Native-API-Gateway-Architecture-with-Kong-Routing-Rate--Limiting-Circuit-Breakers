# Accounts service container (V1.6).
# DEC-006: Django's development server is used instead of gunicorn.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# --noreload keeps exactly one process per container so X-Served-By
# (the container hostname) identifies a single replica unambiguously.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"]
