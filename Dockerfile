FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей (минимум)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements. txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . . 

# Health check (для Docker Compose и оркестраторов)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from core.database import test_connection; asyncio.run(test_connection())" || exit 1

# Запуск бота
CMD ["python", "-m", "bot. main"]