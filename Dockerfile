FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY . .

# Отладка: проверим, что файлы есть
RUN ls -la /app/core/
RUN cat /app/core/database.py | grep -n "def init_db"

CMD ["python", "-m", "bot.main"]