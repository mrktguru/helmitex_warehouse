"""
Централизованный экспорт всех моделей базы данных и утилит подключения.

Этот модуль позволяет импортировать все модели и функции работы с БД:
    from app.database import User, Warehouse, SKU, get_session, engine

Также предоставляет утилиты для инициализации и управления БД.
"""

# Импорт всех моделей из models.py
from .models import (
    # Базовая модель
    Base,
    
    # Основные модели
    User,
    Warehouse,
    SKU,
    Stock,
    Movement,
    
    # Производственные модели
    TechnologicalCard,
    RecipeComponent,
    ProductionBatch,
    Barrel,
    
    # Фасовка и отгрузка
    PackingVariant,
    Recipient,
    Shipment,
    ShipmentItem,
    
    # Вспомогательные модели
    InventoryReserve,
    WasteRecord,
    
    # Enum типы
    SKUType,
    MovementType,
    ProductionStatus,
    ShipmentStatus,
    ReserveType,
    WasteType,
)


# Список всех экспортируемых моделей
__all__ = [
    # Базовая модель
    'Base',
    
    # Основные модели
    'User',
    'Warehouse',
    'SKU',
    'Stock',
    'Movement',
    
    # Производственные модели
    'TechnologicalCard',
    'RecipeComponent',
    'ProductionBatch',
    'Barrel',
    
    # Фасовка и отгрузка
    'PackingVariant',
    'Recipient',
    'Shipment',
    'ShipmentItem',
    
    # Вспомогательные модели
    'InventoryReserve',
    'WasteRecord',
    
    # Enum типы
    'SKUType',
    'MovementType',
    'ProductionStatus',
    'ShipmentStatus',
    'ReserveType',
    'WasteType',
    
    # Утилиты (будут добавлены после импорта connection)
    'engine',
    'SessionLocal',
    'get_session',
    'init_db',
    'close_db',
]


# Версия схемы БД
__version__ = '1.0.0'
DB_SCHEMA_VERSION = '2025.02.04'  # Дата последней миграции


def get_all_models():
    """
    Возвращает список всех моделей SQLAlchemy.
    
    Returns:
        list: Список классов моделей
    """
    return [
        User,
        Warehouse,
        SKU,
        Stock,
        Movement,
        TechnologicalCard,
        RecipeComponent,
        ProductionBatch,
        Barrel,
        PackingVariant,
        Recipient,
        Shipment,
        ShipmentItem,
        InventoryReserve,
        WasteRecord,
    ]


def get_model_by_name(model_name: str):
    """
    Возвращает класс модели по имени.
    
    Args:
        model_name: Название модели (например, 'User', 'Warehouse')
        
    Returns:
        Model class или None если не найдена
        
    Example:
        >>> UserModel = get_model_by_name('User')
        >>> user = UserModel(telegram_id=123, username='test')
    """
    models_map = {
        'User': User,
        'Warehouse': Warehouse,
        'SKU': SKU,
        'Stock': Stock,
        'Movement': Movement,
        'TechnologicalCard': TechnologicalCard,
        'RecipeComponent': RecipeComponent,
        'ProductionBatch': ProductionBatch,
        'Barrel': Barrel,
        'PackingVariant': PackingVariant,
        'Recipient': Recipient,
        'Shipment': Shipment,
        'ShipmentItem': ShipmentItem,
        'InventoryReserve': InventoryReserve,
        'WasteRecord': WasteRecord,
    }
    
    return models_map.get(model_name)


def get_table_names():
    """
    Возвращает список имен всех таблиц в БД.
    
    Returns:
        list: Список имен таблиц
    """
    return [
        'users',
        'warehouses',
        'sku',
        'stock',
        'movements',
        'technological_cards',
        'recipe_components',
        'production_batches',
        'barrels',
        'packing_variants',
        'recipients',
        'shipments',
        'shipment_items',
        'inventory_reserves',
        'waste_records',
    ]


def get_enum_types():
    """
    Возвращает словарь всех Enum типов.
    
    Returns:
        dict: Словарь {название: класс Enum}
    """
    return {
        'SKUType': SKUType,
        'MovementType': MovementType,
        'ProductionStatus': ProductionStatus,
        'ShipmentStatus': ShipmentStatus,
        'ReserveType': ReserveType,
        'WasteType': WasteType,
    }


def get_models_info():
    """
    Возвращает информацию о всех моделях.
    
    Returns:
        dict: Словарь с информацией о каждой модели
    """
    return {
        'User': {
            'table': 'users',
            'description': 'Пользователи системы',
            'primary_key': 'id',
            'relationships': ['created_movements', 'created_batches', 'created_shipments']
        },
        'Warehouse': {
            'table': 'warehouses',
            'description': 'Склады',
            'primary_key': 'id',
            'relationships': ['stocks', 'movements', 'batches', 'barrels']
        },
        'SKU': {
            'table': 'sku',
            'description': 'Номенклатура (сырье, полуфабрикаты, готовая продукция)',
            'primary_key': 'id',
            'relationships': ['stocks', 'movements', 'recipe_components']
        },
        'Stock': {
            'table': 'stock',
            'description': 'Остатки товаров на складах',
            'primary_key': 'id',
            'relationships': ['sku', 'warehouse']
        },
        'Movement': {
            'table': 'movements',
            'description': 'Движения товаров',
            'primary_key': 'id',
            'relationships': ['sku', 'warehouse', 'performed_by']
        },
        'TechnologicalCard': {
            'table': 'technological_cards',
            'description': 'Технологические карты (рецепты)',
            'primary_key': 'id',
            'relationships': ['components', 'batches', 'semi_finished_sku']
        },
        'RecipeComponent': {
            'table': 'recipe_components',
            'description': 'Компоненты рецептов',
            'primary_key': 'id',
            'relationships': ['recipe', 'raw_sku']
        },
        'ProductionBatch': {
            'table': 'production_batches',
            'description': 'Производственные партии',
            'primary_key': 'id',
            'relationships': ['recipe', 'warehouse', 'created_by', 'barrels']
        },
        'Barrel': {
            'table': 'barrels',
            'description': 'Бочки с полуфабрикатами',
            'primary_key': 'id',
            'relationships': ['batch', 'warehouse', 'semi_sku']
        },
        'PackingVariant': {
            'table': 'packing_variants',
            'description': 'Варианты упаковки',
            'primary_key': 'id',
            'relationships': ['semi_sku', 'finished_sku']
        },
        'Recipient': {
            'table': 'recipients',
            'description': 'Получатели (контрагенты)',
            'primary_key': 'id',
            'relationships': ['shipments']
        },
        'Shipment': {
            'table': 'shipments',
            'description': 'Отгрузки',
            'primary_key': 'id',
            'relationships': ['warehouse', 'recipient', 'created_by', 'items']
        },
        'ShipmentItem': {
            'table': 'shipment_items',
            'description': 'Позиции отгрузок',
            'primary_key': 'id',
            'relationships': ['shipment', 'sku']
        },
        'InventoryReserve': {
            'table': 'inventory_reserves',
            'description': 'Резервы товаров',
            'primary_key': 'id',
            'relationships': ['warehouse', 'sku', 'reserved_by']
        },
        'WasteRecord': {
            'table': 'waste_records',
            'description': 'Записи об отходах',
            'primary_key': 'id',
            'relationships': ['warehouse', 'sku', 'batch']
        },
    }


# Метаданные БД
DATABASE_METADATA = {
    'schema_version': DB_SCHEMA_VERSION,
    'total_models': len(get_all_models()),
    'total_tables': len(get_table_names()),
    'enum_types': len(get_enum_types()),
    'api_version': __version__,
}


# Примечание: Импорт connection будет добавлен после создания файла connection.py
# from .connection import engine, SessionLocal, get_session, init_db, close_db

# Временные заглушки (будут заменены после создания connection.py)
engine = None
SessionLocal = None
get_session = None
init_db = None
close_db = None


def print_database_info():
    """
    Выводит информацию о структуре базы данных.
    
    Полезно для отладки и документирования.
    """
    print("=" * 60)
    print("DATABASE STRUCTURE INFO")
    print("=" * 60)
    print(f"Schema Version: {DB_SCHEMA_VERSION}")
    print(f"Total Models: {DATABASE_METADATA['total_models']}")
    print(f"Total Tables: {DATABASE_METADATA['total_tables']}")
    print(f"Enum Types: {DATABASE_METADATA['enum_types']}")
    print("\n" + "=" * 60)
    print("MODELS:")
    print("=" * 60)
    
    for model_name, info in get_models_info().items():
        print(f"\n{model_name}:")
        print(f"  Table: {info['table']}")
        print(f"  Description: {info['description']}")
        print(f"  Relationships: {', '.join(info['relationships'])}")
    
    print("\n" + "=" * 60)
    print("ENUM TYPES:")
    print("=" * 60)
    
    for enum_name, enum_class in get_enum_types().items():
        values = [e.value for e in enum_class]
        print(f"\n{enum_name}: {', '.join(values)}")
    
    print("\n" + "=" * 60)


def validate_database_schema():
    """
    Валидирует целостность схемы базы данных.
    
    Returns:
        dict: Результаты валидации
        
    Example:
        >>> result = validate_database_schema()
        >>> if result['valid']:
        ...     print("Schema is valid!")
    """
    issues = []
    
    # Проверка наличия всех моделей
    required_models = [
        'User', 'Warehouse', 'SKU', 'Stock', 'Movement',
        'TechnologicalCard', 'RecipeComponent', 'ProductionBatch',
        'Barrel', 'PackingVariant', 'Recipient', 'Shipment',
        'ShipmentItem', 'InventoryReserve', 'WasteRecord'
    ]
    
    for model_name in required_models:
        model = get_model_by_name(model_name)
        if model is None:
            issues.append(f"Missing model: {model_name}")
    
    # Проверка Enum типов
    required_enums = [
        'SKUType', 'MovementType', 'ProductionStatus',
        'ShipmentStatus', 'ReserveType', 'WasteType'
    ]
    
    enum_types = get_enum_types()
    for enum_name in required_enums:
        if enum_name not in enum_types:
            issues.append(f"Missing enum: {enum_name}")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'total_models': len(get_all_models()),
        'total_enums': len(get_enum_types()),
    }


# Экспорт функций валидации
__all__.extend([
    'get_all_models',
    'get_model_by_name',
    'get_table_names',
    'get_enum_types',
    'get_models_info',
    'DATABASE_METADATA',
    'print_database_info',
    'validate_database_schema',
])
