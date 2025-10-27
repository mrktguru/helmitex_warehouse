"""
Главный модуль Telegram бота.
"""
from app.database.db import init_db
from app.handlers._original_handlers import build_application
from app.logger import setup_logging, get_logger
from app.config import LOG_LEVEL, LOG_FILE, APP_NAME, APP_VERSION

# Настраиваем логирование
setup_logging(log_level=LOG_LEVEL, log_file=LOG_FILE)
logger = get_logger("bot")


def main():
    """Основная функция запуска бота."""
    logger.info("=" * 80)
    logger.info(f"Запуск {APP_NAME} v{APP_VERSION}")
    logger.info("=" * 80)
    
    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        init_db()
        logger.info("✅ База данных инициализирована успешно")
        
        # Создание и запуск приложения
        logger.info("Создание Telegram приложения...")
        app = build_application()
        logger.info("✅ Telegram приложение создано успешно")
        
        # Запуск polling
        logger.info("🚀 Запуск polling...")
        logger.info("Бот готов к работе!")
        app.run_polling()
        
    except KeyboardInterrupt:
        logger.info("⏹️  Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка при запуске бота: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
