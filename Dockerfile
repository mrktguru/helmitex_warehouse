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

# Делаем скрипт исполняемым
RUN chmod +x /app/start.sh

# Запуск через скрипт
CMD ["/app/start.sh"]
