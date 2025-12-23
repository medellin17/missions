FROM python:3.12-slim

WORKDIR /app

# Добавляем PYTHONPATH, чтобы гарантировать доступ к пакетам из рабочей директории
ENV PYTHONPATH=/app

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем проект
COPY . .

# Стартуем бота через модульный запуск
CMD ["python", "-m", "bot.main"]