"""
Централизованный экспорт всех сервисных модулей.

Этот модуль позволяет импортировать все сервисы через один импорт:
    from app.services import recipe_service, production_service, ...

Или импортировать конкретные функции:
    from app.services import create_recipe, execute_batch, ...
"""

# Импорт модулей сервисов
from . import recipe_service
from . import production_service
from . import barrel_service
from . import packing_service
from . import shipment_service

# Для удобства можно импортировать часто используемые функции напрямую

# Recipe Service
from .recipe_service import (
    create_recipe,
    get_recipe,
    get_recipe_with_components,
    get_recipes,
    add_recipe_component,
    update_recipe_component,
    remove_recipe_component,
    update_recipe,
    activate_recipe,
    archive_recipe,
    validate_recipe_components,
    calculate_recipe_requirements,
    get_recipe_statistics
)

# Production Service
from .production_service import (
    create_batch,
    get_batch,
    get_batches,
    check_materials_availability,
    execute_batch,
    cancel_batch,
    get_batch_statistics,
    get_production_efficiency
)

# Barrel Service
from .barrel_service import (
    create_barrel,
    get_barrel,
    get_barrels,
    get_barrels_for_packing,
    get_fifo_barrels,
    update_barrel_weight,
    mark_barrel_empty,
    get_barrel_statistics
)

# Packing Service
from .packing_service import (
    create_packing_variant,
    get_packing_variant,
    get_packing_variants,
    update_packing_variant,
    archive_packing_variant,
    calculate_available_for_packing,
    calculate_max_units,
    execute_packing,
    get_packing_history,
    get_packing_statistics
)

# Shipment Service
from .shipment_service import (
    create_recipient,
    get_recipients,
    update_recipient,
    get_recipient_statistics,
    create_shipment,
    add_shipment_item,
    update_shipment_item,
    remove_shipment_item,
    reserve_for_shipment,
    cancel_shipment_reservation,
    execute_shipment,
    cancel_shipment,
    get_shipments,
    get_shipment_statistics,
    get_pending_shipments
)

# Список всех экспортируемых объектов
__all__ = [
    # Модули
    'recipe_service',
    'production_service',
    'barrel_service',
    'packing_service',
    'shipment_service',
    
    # Recipe Service Functions
    'create_recipe',
    'get_recipe',
    'get_recipe_with_components',
    'get_recipes',
    'add_recipe_component',
    'update_recipe_component',
    'remove_recipe_component',
    'update_recipe',
    'activate_recipe',
    'archive_recipe',
    'validate_recipe_components',
    'calculate_recipe_requirements',
    'get_recipe_statistics',
    
    # Production Service Functions
    'create_batch',
    'get_batch',
    'get_batches',
    'check_materials_availability',
    'execute_batch',
    'cancel_batch',
    'get_batch_statistics',
    'get_production_efficiency',
    
    # Barrel Service Functions
    'create_barrel',
    'get_barrel',
    'get_barrels',
    'get_barrels_for_packing',
    'get_fifo_barrels',
    'update_barrel_weight',
    'mark_barrel_empty',
    'get_barrel_statistics',
    
    # Packing Service Functions
    'create_packing_variant',
    'get_packing_variant',
    'get_packing_variants',
    'update_packing_variant',
    'archive_packing_variant',
    'calculate_available_for_packing',
    'calculate_max_units',
    'execute_packing',
    'get_packing_history',
    'get_packing_statistics',
    
    # Shipment Service Functions
    'create_recipient',
    'get_recipients',
    'update_recipient',
    'get_recipient_statistics',
    'create_shipment',
    'add_shipment_item',
    'update_shipment_item',
    'remove_shipment_item',
    'reserve_for_shipment',
    'cancel_shipment_reservation',
    'execute_shipment',
    'cancel_shipment',
    'get_shipments',
    'get_shipment_statistics',
    'get_pending_shipments',
]


# Версия API сервисов
__version__ = '1.0.0'


def get_all_services():
    """
    Возвращает список всех доступных сервисных модулей.
    
    Returns:
        list: Список имен сервисов
    """
    return [
        'recipe_service',
        'production_service',
        'barrel_service',
        'packing_service',
        'shipment_service',
    ]


def get_service_info():
    """
    Возвращает информацию о всех сервисах.
    
    Returns:
        dict: Словарь с информацией о каждом сервисе
    """
    return {
        'recipe_service': {
            'description': 'Управление технологическими картами и рецептами',
            'functions': [
                'create_recipe', 'get_recipe', 'get_recipes',
                'add_recipe_component', 'update_recipe', 'archive_recipe'
            ]
        },
        'production_service': {
            'description': 'Управление производственными партиями и замесами',
            'functions': [
                'create_batch', 'get_batch', 'get_batches',
                'execute_batch', 'cancel_batch', 'get_batch_statistics'
            ]
        },
        'barrel_service': {
            'description': 'Управление бочками с полуфабрикатами',
            'functions': [
                'create_barrel', 'get_barrel', 'get_barrels',
                'get_fifo_barrels', 'update_barrel_weight', 'mark_barrel_empty'
            ]
        },
        'packing_service': {
            'description': 'Управление фасовкой готовой продукции',
            'functions': [
                'create_packing_variant', 'get_packing_variants',
                'execute_packing', 'get_packing_history', 'get_packing_statistics'
            ]
        },
        'shipment_service': {
            'description': 'Управление отгрузками и получателями',
            'functions': [
                'create_recipient', 'create_shipment', 'add_shipment_item',
                'reserve_for_shipment', 'execute_shipment', 'get_shipments'
            ]
        }
    }
