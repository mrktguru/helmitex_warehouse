FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всех файлов приложения
COPY . .

# Создание директорий для логов и данных
RUN mkdir -p /app/logs /app/data

# Создание скрипта запуска с миграциями
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "================================="\n\
echo "Waiting for database..."\n\
echo "================================="\n\
\n\
# Ожидание готовности PostgreSQL\n\
until pg_isready -h db -U warehouse -d warehouse; do\n\
  echo "Database is unavailable - sleeping"\n\
  sleep 2\n\
done\n\
\n\
echo "================================="\n\
echo "Database is ready!"\n\
echo "================================="\n\
\n\
echo "Running Alembic migrations..."\n\
alembic upgrade head\n\
\n\
if [ $? -eq 0 ]; then\n\
  echo "================================="\n\
  echo "Migrations completed successfully!"\n\
  echo "================================="\n\
else\n\
  echo "================================="\n\
  echo "Migration failed!"\n\
  echo "================================="\n\
  exit 1\n\
fi\n\
\n\
echo "Starting Telegram bot..."\n\
python bot.py' > /app/start.sh

# Делаем скрипт исполняемым
RUN chmod +x /app/start.sh

# Запуск через скрипт
CMD ["/app/start.sh"]
