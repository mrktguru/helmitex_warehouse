# ===================================================================
# ДОБАВИТЬ В КОНЕЦ ФАЙЛА app/services/barrel_service.py
# ===================================================================

# ============================================================================
# ДОПОЛНИТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ HANDLERS (NEW!)
# ============================================================================

def get_barrels_for_packing(
    db: Session,
    warehouse_id: int,
    semi_product_id: int = None
) -> List[Barrel]:
    """
    Получение бочек доступных для фасовки.
    
    Возвращает только активные бочки с остатком больше нуля,
    отсортированные по FIFO (дате создания).
    
    Args:
        db: Сессия БД
        warehouse_id: ID склада
        semi_product_id: Фильтр по полуфабрикату (опционально)
        
    Returns:
        List[Barrel]: Список бочек готовых к фасовке
        
    Note:
        Это alias для get_active_barrels() с загрузкой связанных данных.
    """
    barrels = get_active_barrels(
        db=db,
        warehouse_id=warehouse_id,
        semi_product_id=semi_product_id
    )
    
    # Дополнительно загружаем связанные данные если нужно
    # (уже загружены в get_active_barrels через joinedload)
    
    logger.debug(f"Бочки для фасовки на складе {warehouse_id}: {len(barrels)} шт")
    
    return barrels
