#!/bin/bash
set -e

echo "================================="
echo "Waiting for database..."
echo "================================="

until pg_isready -h db -U warehouse -d warehouse; do
  echo "Database is unavailable - sleeping"
  sleep 2
done

echo "================================="
echo "Database is ready!"
echo "================================="

echo "Initializing database tables..."
export PYTHONPATH=/app:$PYTHONPATH

echo "Starting Telegram bot..."
cd /app && python -m app.bot
