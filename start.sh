#!/bin/bash
set -e

echo "================================="
echo "Waiting for database..."
echo "================================="

# Ожидание готовности PostgreSQL
until pg_isready -h db -U warehouse -d warehouse; do
  echo "Database is unavailable - sleeping"
  sleep 2
done

echo "================================="
echo "Database is ready!"
echo "================================="

echo "Running Alembic migrations..."
alembic upgrade head

if [ $? -eq 0 ]; then
  echo "================================="
  echo "Migrations completed successfully!"
  echo "================================="
else
  echo "================================="
  echo "Migration failed!"
  echo "================================="
  exit 1
fi

echo "Starting Telegram bot..."
# Устанавливаем PYTHONPATH чтобы Python мог найти модуль app
export PYTHONPATH=/app:$PYTHONPATH
cd /app && python -m app.bot
