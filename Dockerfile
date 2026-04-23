FROM python:3.12-slim

WORKDIR /src

# dependencias del sistema (psycopg2 / asyncpg)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# instalar dependencias python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copiar el código
COPY . .

# exponer puerto
EXPOSE 8080

# arrancar FastAPI
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080
