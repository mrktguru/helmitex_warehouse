"""
Централизованный экспорт всех обработчиков (handlers) Telegram бота.

Этот модуль позволяет импортировать все handlers через один импорт:
    from app.handlers import (
        get_arrival_handler,
        get_production_handler,
        ...
    )

Каждый handler возвращает настроенный ConversationHandler для регистрации в Application.
"""

# Импорт handlers операционных процессов
from .arrival import get_arrival_handler
from .production import get_production_handler
from .packing import get_packing_handler
from .shipment import get_shipment_handler

# Импорт handlers просмотра и аналитики
from .stock import get_stock_handler
from .history import get_history_handler

# Импорт административных handlers
from .admin_warehouse import get_admin_warehouse_handler
from .admin_users import get_admin_users_handler


# Список всех экспортируемых handlers
__all__ = [
    # Операционные handlers
    'get_arrival_handler',
    'get_production_handler',
    'get_packing_handler',
    'get_shipment_handler',
    
    # Информационные handlers
    'get_stock_handler',
    'get_history_handler',
    
    # Административные handlers
    'get_admin_warehouse_handler',
    'get_admin_users_handler',
]


# Версия handlers API
__version__ = '1.0.0'


def get_all_handlers():
    """
    Возвращает список всех функций-генераторов handlers.
    
    Returns:
        list: Список функций, возвращающих ConversationHandler
        
    Example:
        >>> handlers = get_all_handlers()
        >>> for handler_func in handlers:
        ...     handler = handler_func()
        ...     application.add_handler(handler)
    """
    return [
        get_arrival_handler,
        get_production_handler,
        get_packing_handler,
        get_shipment_handler,
        get_stock_handler,
        get_history_handler,
        get_admin_warehouse_handler,
        get_admin_users_handler,
    ]


def get_operational_handlers():
    """
    Возвращает список операционных handlers (основные бизнес-процессы).
    
    Returns:
        list: Список функций операционных handlers
    """
    return [
        get_arrival_handler,
        get_production_handler,
        get_packing_handler,
        get_shipment_handler,
    ]


def get_informational_handlers():
    """
    Возвращает список информационных handlers (просмотр данных).
    
    Returns:
        list: Список функций информационных handlers
    """
    return [
        get_stock_handler,
        get_history_handler,
    ]


def get_admin_handlers():
    """
    Возвращает список административных handlers.
    
    Returns:
        list: Список функций административных handlers
    """
    return [
        get_admin_warehouse_handler,
        get_admin_users_handler,
    ]


def register_all_handlers(application):
    """
    Регистрирует все handlers в Application.
    
    Удобная функция для массовой регистрации всех handlers
    в правильном порядке приоритета.
    
    Args:
        application: telegram.ext.Application instance
        
    Example:
        >>> from telegram.ext import Application
        >>> from app.handlers import register_all_handlers
        >>> 
        >>> app = Application.builder().token(TOKEN).build()
        >>> register_all_handlers(app)
    """
    # Регистрация в порядке приоритета
    
    # 1. Административные handlers (высокий приоритет)
    for handler_func in get_admin_handlers():
        application.add_handler(handler_func(), group=0)
    
    # 2. Операционные handlers
    for handler_func in get_operational_handlers():
        application.add_handler(handler_func(), group=1)
    
    # 3. Информационные handlers
    for handler_func in get_informational_handlers():
        application.add_handler(handler_func(), group=2)


def get_handler_info():
    """
    Возвращает информацию о всех handlers.
    
    Returns:
        dict: Словарь с информацией о каждом handler
    """
    return {
        'arrival': {
            'function': 'get_arrival_handler',
            'name': 'Приемка сырья',
            'command': '/arrival',
            'description': 'Приемка сырья на склад от поставщиков',
            'permissions': ['can_receive_materials'],
            'category': 'operational'
        },
        'production': {
            'function': 'get_production_handler',
            'name': 'Производство',
            'command': '/production',
            'description': 'Создание производственных партий и выполнение замесов',
            'permissions': ['can_produce'],
            'category': 'operational'
        },
        'packing': {
            'function': 'get_packing_handler',
            'name': 'Фасовка',
            'command': '/packing',
            'description': 'Фасовка полуфабрикатов в готовую продукцию',
            'permissions': ['can_pack'],
            'category': 'operational'
        },
        'shipment': {
            'function': 'get_shipment_handler',
            'name': 'Отгрузка',
            'command': '/shipment',
            'description': 'Создание и выполнение отгрузок готовой продукции',
            'permissions': ['can_ship'],
            'category': 'operational'
        },
        'stock': {
            'function': 'get_stock_handler',
            'name': 'Остатки',
            'command': '/stock',
            'description': 'Просмотр остатков по складам и бочкам',
            'permissions': [],
            'category': 'informational'
        },
        'history': {
            'function': 'get_history_handler',
            'name': 'История',
            'command': '/history',
            'description': 'Просмотр истории всех операций',
            'permissions': [],
            'category': 'informational'
        },
        'admin_warehouse': {
            'function': 'get_admin_warehouse_handler',
            'name': 'Админ: Склады',
            'command': '/admin',
            'description': 'Управление складами, номенклатурой и рецептами',
            'permissions': ['is_admin'],
            'category': 'administrative'
        },
        'admin_users': {
            'function': 'get_admin_users_handler',
            'name': 'Админ: Пользователи',
            'command': '/admin',
            'description': 'Управление пользователями и правами доступа',
            'permissions': ['is_admin'],
            'category': 'administrative'
        },
    }


def get_handler_commands():
    """
    Возвращает список всех команд для настройки BotCommandScope.
    
    Returns:
        list: Список кортежей (command, description)
        
    Example:
        >>> commands = get_handler_commands()
        >>> await bot.set_my_commands(commands)
    """
    info = get_handler_info()
    
    commands = []
    seen_commands = set()
    
    for handler_data in info.values():
        command = handler_data['command'].lstrip('/')
        description = handler_data['name']
        
        # Избегаем дубликатов команд
        if command not in seen_commands:
            commands.append((command, description))
            seen_commands.add(command)
    
    # Добавляем базовые команды
    base_commands = [
        ('start', 'Запуск бота'),
        ('help', 'Справка'),
        ('cancel', 'Отмена текущей операции'),
    ]
    
    for cmd, desc in base_commands:
        if cmd not in seen_commands:
            commands.insert(0, (cmd, desc))
    
    return commands


def get_handlers_by_permission(permission: str):
    """
    Возвращает список handlers, требующих указанное разрешение.
    
    Args:
        permission: Название разрешения (например, 'can_produce')
        
    Returns:
        list: Список функций handlers
        
    Example:
        >>> production_handlers = get_handlers_by_permission('can_produce')
        >>> # [get_production_handler]
    """
    info = get_handler_info()
    handler_functions = {
        'arrival': get_arrival_handler,
        'production': get_production_handler,
        'packing': get_packing_handler,
        'shipment': get_shipment_handler,
        'stock': get_stock_handler,
        'history': get_history_handler,
        'admin_warehouse': get_admin_warehouse_handler,
        'admin_users': get_admin_users_handler,
    }
    
    result = []
    for handler_key, handler_data in info.items():
        if permission in handler_data['permissions']:
            result.append(handler_functions[handler_key])
    
    return result


def get_handlers_by_category(category: str):
    """
    Возвращает список handlers по категории.
    
    Args:
        category: Категория ('operational', 'informational', 'administrative')
        
    Returns:
        list: Список функций handlers
        
    Example:
        >>> operational = get_handlers_by_category('operational')
        >>> # [get_arrival_handler, get_production_handler, ...]
    """
    if category == 'operational':
        return get_operational_handlers()
    elif category == 'informational':
        return get_informational_handlers()
    elif category == 'administrative':
        return get_admin_handlers()
    else:
        return []


# Metadata для удобства отладки
HANDLERS_METADATA = {
    'total_handlers': len(__all__),
    'operational': len(get_operational_handlers()),
    'informational': len(get_informational_handlers()),
    'administrative': len(get_admin_handlers()),
    'version': __version__,
}

