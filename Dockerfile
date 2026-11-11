FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema mínimas para pip.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY infra/ ./infra/
COPY tests/ ./tests/
COPY pytest.ini ./pytest.ini

EXPOSE 5000

# Flask directo (simple y suficiente para el proyecto de curso).
CMD ["python", "-m", "app.main"]
