"""
Централизованный экспорт всех сервисных модулей.

Этот модуль позволяет импортировать все сервисы через один импорт:
    from app.services import recipe_service, production_service, ...

Или импортировать конкретные функции:
    from app.services import create_recipe, execute_batch, ...
    
ИСПРАВЛЕНО: Удалены импорты несуществующих функций
"""

# Импорт модулей сервисов
from . import recipe_service
from . import production_service
from . import barrel_service
from . import packing_service
from . import shipment_service

# ============================================================================
# RECIPE SERVICE - Импорт ТОЛЬКО существующих функций
# ============================================================================
from .recipe_service import (
    create_recipe,
    get_recipe_by_id,
    get_recipes,
    get_active_recipes,
    activate_recipe,
    archive_recipe,
    update_recipe_status,
    update_recipe,
    update_recipe_components,
    calculate_required_materials,
    get_recipe_details_formatted,
    validate_recipe,
    can_activate_recipe,
    delete_recipe,
)

# ============================================================================
# PRODUCTION SERVICE - Импорт ТОЛЬКО существующих функций
# ============================================================================
from .production_service import (
    create_production_batch,
    get_production_batch,
    get_production_history,
    check_materials_availability,
    recalculate_to_available,
    execute_production,
    cancel_production_batch,
    get_production_statistics,
    get_recipe_usage_frequency,
    get_production_batch_details,
)

# ============================================================================
# BARREL SERVICE - Импорт ТОЛЬКО существующих функций
# ============================================================================
from .barrel_service import (
    create_barrel,
    get_barrel_by_id,
    get_barrels,
    get_active_barrels,
    get_barrels_fifo,
    calculate_barrel_distribution,
    update_barrel_weight,
    deactivate_barrel,
    reactivate_barrel,
    get_barrel_balance,
    get_warehouse_barrels_summary,
    get_barrel_usage_history,
    find_oldest_barrel,
    get_empty_barrels,
    get_barrel_details,
)

# ============================================================================
# PACKING SERVICE - Импорт ТОЛЬКО существующих функций
# ============================================================================
from .packing_service import (
    create_packing_variant,
    get_packing_variant,
    get_packing_variants,
    get_packing_variants_for_semi_product,
    calculate_available_for_packing,
    calculate_max_units,
    execute_packing,
    execute_packing_by_variant,
    get_packing_history,
    get_packing_statistics,
    validate_packing_request,
    get_packing_suggestions,
)

# ============================================================================
# SHIPMENT SERVICE - Импорт ТОЛЬКО существующих функций
# ============================================================================
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
    get_pending_shipments,
)


# ============================================================================
# СПИСОК ВСЕХ ЭКСПОРТИРУЕМЫХ ОБЪЕКТОВ
# ============================================================================
__all__ = [
    # Модули сервисов
    'recipe_service',
    'production_service',
    'barrel_service',
    'packing_service',
    'shipment_service',
    
    # Recipe Service Functions (14)
    'create_recipe',
    'get_recipe_by_id',
    'get_recipes',
    'get_active_recipes',
    'activate_recipe',
    'archive_recipe',
    'update_recipe_status',
    'update_recipe',
    'update_recipe_components',
    'calculate_required_materials',
    'get_recipe_details_formatted',
    'validate_recipe',
    'can_activate_recipe',
    'delete_recipe',
    
    # Production Service Functions (10)
    'create_production_batch',
    'get_production_batch',
    'get_production_history',
    'check_materials_availability',
    'recalculate_to_available',
    'execute_production',
    'cancel_production_batch',
    'get_production_statistics',
    'get_recipe_usage_frequency',
    'get_production_batch_details',
    
    # Barrel Service Functions (15)
    'create_barrel',
    'get_barrel_by_id',
    'get_barrels',
    'get_active_barrels',
    'get_barrels_fifo',
    'calculate_barrel_distribution',
    'update_barrel_weight',
    'deactivate_barrel',
    'reactivate_barrel',
    'get_barrel_balance',
    'get_warehouse_barrels_summary',
    'get_barrel_usage_history',
    'find_oldest_barrel',
    'get_empty_barrels',
    'get_barrel_details',
    
    # Packing Service Functions (12)
    'create_packing_variant',
    'get_packing_variant',
    'get_packing_variants',
    'get_packing_variants_for_semi_product',
    'calculate_available_for_packing',
    'calculate_max_units',
    'execute_packing',
    'execute_packing_by_variant',
    'get_packing_history',
    'get_packing_statistics',
    'validate_packing_request',
    'get_packing_suggestions',
    
    # Shipment Service Functions (15)
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


# ============================================================================
# ВЕРСИЯ API
# ============================================================================
__version__ = '1.0.0-fixed'


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

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
                'create_recipe', 'get_recipe_by_id', 'get_recipes',
                'update_recipe', 'activate_recipe', 'archive_recipe',
                'validate_recipe', 'calculate_required_materials'
            ]
        },
        'production_service': {
            'description': 'Управление производственными партиями и замесами',
            'functions': [
                'create_production_batch', 'get_production_batch', 'get_production_history',
                'execute_production', 'cancel_production_batch', 'get_production_statistics'
            ]
        },
        'barrel_service': {
            'description': 'Управление бочками с полуфабрикатами',
            'functions': [
                'create_barrel', 'get_barrel_by_id', 'get_barrels',
                'get_barrels_fifo', 'update_barrel_weight', 'deactivate_barrel'
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
