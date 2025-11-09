"""
Централизованный экспорт всех обработчиков (handlers) Telegram бота.

Этот модуль экспортирует все routers для aiogram 3.x.
Каждый router регистрируется в dispatcher через bot.py.
"""

# Import routers from handler modules
from .arrival import arrival_router
from .production import production_router
from .packing import packing_router
from .shipment import shipment_router
from .stock import stock_router
from .history import history_router
from .admin_users import admin_users_router
from .admin_warehouse import admin_warehouse_router

# Список всех экспортируемых routers
__all__ = [
    'arrival_router',
    'production_router',
    'packing_router',
    'shipment_router',
    'stock_router',
    'history_router',
    'admin_users_router',
    'admin_warehouse_router',
]

__version__ = '3.0.0'  # aiogram 3.x version

# Metadata для удобства отладки
HANDLERS_METADATA = {
    'total_routers': len(__all__),
    'version': __version__,
    'routers': __all__,
}
