"""
Главный модуль Telegram бота.
"""
import logging
from telegram.ext import Application, CommandHandler

from app.database.db import init_db
from app.config import TELEGRAM_TOKEN
from app.handlers.start_handler import start, help_command, status

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Запуск бота"""
    # Инициализация базы данных
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully!")

    # Создание приложения
    logger.info("Starting bot...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))

    # Запуск бота
    logger.info("Bot started successfully!")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
