"""
Расчеты для бизнес-логики Helmitex Warehouse.

Модуль содержит все математические и логические расчеты:
- Расчет потребности сырья по рецепту
- FIFO-распределение по бочкам
- Расчет максимального количества упаковок
- Пересчет под доступное сырье
- Валидация процентов и сумм
"""
from typing import Dict, List, Tuple, Optional
from decimal import Decimal, ROUND_HALF_UP
from app.logger import get_logger

logger = get_logger("calculations")


# ============================================================================
# РАСЧЕТЫ ДЛЯ ПРОИЗВОДСТВА
# ============================================================================

def calculate_raw_materials_required(
    target_weight: float,
    yield_percent: float,
    components: List[Dict]
) -> Dict[int, float]:
    """
    Расчет потребности сырья по рецепту.
    
    Формулы:
    1. raw_total = target_weight / (yield_percent / 100)
    2. component_weight = raw_total * (percentage / 100)
    
    Args:
        target_weight: Целевой вес готового полуфабриката (кг)
        yield_percent: Процент выхода (50-100%)
        components: Список компонентов рецепта
            [{'raw_material_id': int, 'percentage': float}, ...]
            
    Returns:
        Dict[int, float]: {raw_material_id: required_weight}
        
    Example:
        >>> calculate_raw_materials_required(
        ...     target_weight=100.0,
        ...     yield_percent=85.0,
        ...     components=[
        ...         {'raw_material_id': 1, 'percentage': 45.5},
        ...         {'raw_material_id': 2, 'percentage': 30.0},
        ...         {'raw_material_id': 3, 'percentage': 24.5}
        ...     ]
        ... )
        {1: 53.53, 2: 35.29, 3: 28.82}
    """
    if target_weight <= 0:
        raise ValueError("Целевой вес должен быть положительным числом")
    
    if not (50 <= yield_percent <= 100):
        raise ValueError("Процент выхода должен быть от 50 до 100")
    
    # Общее количество сырья с учетом выхода
    raw_total = target_weight / (yield_percent / 100.0)
    
    logger.info(f"Расчет потребности: целевой вес={target_weight} кг, выход={yield_percent}%, сырья={raw_total:.2f} кг")
    
    # Расчет для каждого компонента
    required = {}
    for component in components:
        raw_material_id = component['raw_material_id']
        percentage = component['percentage']
        
        component_weight = raw_total * (percentage / 100.0)
        required[raw_material_id] = round(component_weight, 2)
        
        logger.debug(f"  Сырье ID={raw_material_id}: {percentage}% = {component_weight:.2f} кг")
    
    return required


def calculate_to_available_materials(
    required: Dict[int, float],
    available: Dict[int, float]
) -> Tuple[Dict[int, float], float]:
    """
    Пересчет рецепта под доступное сырье.
    
    Алгоритм:
    1. Найти ограничивающий компонент: min(available / required)
    2. Пересчитать все компоненты пропорционально
    
    Args:
        required: Требуемое количество {raw_material_id: weight}
        available: Доступное количество {raw_material_id: weight}
        
    Returns:
        Tuple[Dict[int, float], float]: 
            - Новое требуемое количество
            - Коэффициент уменьшения (0-1)
            
    Example:
        >>> calculate_to_available_materials(
        ...     required={1: 53.53, 2: 35.29, 3: 28.82},
        ...     available={1: 60.0, 2: 25.0, 3: 30.0}
        ... )
        ({1: 37.93, 2: 25.0, 3: 20.43}, 0.708)
    """
    if not required:
        raise ValueError("Список требуемых материалов пуст")
    
    # Находим ограничивающий компонент
    ratios = []
    limiting_id = None
    min_ratio = float('inf')
    
    for material_id, req_weight in required.items():
        avail_weight = available.get(material_id, 0)
        
        if req_weight <= 0:
            continue
            
        ratio = avail_weight / req_weight
        ratios.append((material_id, ratio))
        
        if ratio < min_ratio:
            min_ratio = ratio
            limiting_id = material_id
    
    if min_ratio >= 1.0:
        # Всего сырья достаточно
        logger.info("Всего сырья достаточно, пересчет не требуется")
        return required, 1.0
    
    logger.info(f"Ограничивающий компонент ID={limiting_id}, коэффициент={min_ratio:.3f}")
    
    # Пересчитываем все компоненты
    recalculated = {}
    for material_id, req_weight in required.items():
        new_weight = req_weight * min_ratio
        recalculated[material_id] = round(new_weight, 2)
        
        logger.debug(f"  Сырье ID={material_id}: {req_weight:.2f} → {new_weight:.2f} кг")
    
    return recalculated, round(min_ratio, 4)


def calculate_actual_output_weight(
    raw_total: float,
    yield_percent: float
) -> float:
    """
    Расчет фактического выхода полуфабриката.
    
    Args:
        raw_total: Общий вес использованного сырья (кг)
        yield_percent: Процент выхода (50-100%)
        
    Returns:
        float: Вес готового полуфабриката (кг)
        
    Example:
        >>> calculate_actual_output_weight(117.65, 85.0)
        100.0
    """
    output = raw_total * (yield_percent / 100.0)
    return round(output, 2)


# ============================================================================
# FIFO-РАСЧЕТЫ ДЛЯ ФАСОВКИ
# ============================================================================

def calculate_fifo_distribution(
    barrels: List[Dict],
    required_weight: float
) -> List[Dict]:
    """
    FIFO-распределение требуемого веса по бочкам.
    
    Алгоритм:
    1. Сортировка бочек по дате создания (FIFO)
    2. Последовательное списание с самых старых
    3. Полное использование бочки, если возможно
    
    Args:
        barrels: Список бочек [{'id': int, 'current_weight': float, 'created_at': datetime}, ...]
                 ВАЖНО: должны быть отсортированы по created_at
        required_weight: Требуемый вес (кг)
        
    Returns:
        List[Dict]: [{'barrel_id': int, 'weight_to_use': float}, ...]
        
    Raises:
        ValueError: Если недостаточно полуфабриката в бочках
        
    Example:
        >>> barrels = [
        ...     {'id': 1, 'current_weight': 50.0},
        ...     {'id': 2, 'current_weight': 80.0},
        ...     {'id': 3, 'current_weight': 30.0}
        ... ]
        >>> calculate_fifo_distribution(barrels, 100.0)
        [{'barrel_id': 1, 'weight_to_use': 50.0}, 
         {'barrel_id': 2, 'weight_to_use': 50.0}]
    """
    if required_weight <= 0:
        raise ValueError("Требуемый вес должен быть положительным")
    
    # Проверяем общую доступность
    total_available = sum(b['current_weight'] for b in barrels)
    if total_available < required_weight:
        raise ValueError(
            f"Недостаточно полуфабриката: требуется {required_weight} кг, "
            f"доступно {total_available} кг"
        )
    
    distribution = []
    remaining = required_weight
    
    logger.info(f"FIFO-распределение: требуется {required_weight} кг из {len(barrels)} бочек")
    
    for barrel in barrels:
        if remaining <= 0:
            break
        
        barrel_id = barrel['id']
        available = barrel['current_weight']
        
        # Сколько берем из этой бочки
        to_use = min(available, remaining)
        
        distribution.append({
            'barrel_id': barrel_id,
            'weight_to_use': round(to_use, 2)
        })
        
        remaining -= to_use
        
        logger.debug(f"  Бочка ID={barrel_id}: берем {to_use:.2f} кг из {available:.2f} кг")
    
    if remaining > 0.01:  # Допуск на погрешность округления
        raise ValueError(f"Ошибка распределения: осталось {remaining:.2f} кг")
    
    logger.info(f"Распределение завершено: использовано {len(distribution)} бочек")
    
    return distribution


def calculate_max_packing_units(
    total_weight: float,
    weight_per_unit: float
) -> int:
    """
    Расчет максимального количества упаковок.
    
    Args:
        total_weight: Общий доступный вес полуфабриката (кг)
        weight_per_unit: Вес одной упаковки (кг)
        
    Returns:
        int: Максимальное количество полных упаковок
        
    Example:
        >>> calculate_max_packing_units(113.4, 10.0)
        11
    """
    if weight_per_unit <= 0:
        raise ValueError("Вес упаковки должен быть положительным")
    
    max_units = int(total_weight / weight_per_unit)
    
    logger.info(f"Макс. упаковок: {total_weight} кг / {weight_per_unit} кг = {max_units} шт")
    
    return max_units


def calculate_packing_remainder(
    total_weight: float,
    units_count: int,
    weight_per_unit: float
) -> float:
    """
    Расчет остатка после фасовки.
    
    Args:
        total_weight: Общий вес полуфабриката (кг)
        units_count: Количество упакованных единиц
        weight_per_unit: Вес одной упаковки (кг)
        
    Returns:
        float: Остаток полуфабриката (кг)
        
    Example:
        >>> calculate_packing_remainder(113.4, 10, 10.0)
        13.4
    """
    used = units_count * weight_per_unit
    remainder = total_weight - used
    
    return round(remainder, 2)


# ============================================================================
# ВАЛИДАЦИЯ И ПРОВЕРКИ
# ============================================================================

def validate_percentage_sum(percentages: List[float], tolerance: float = 0.01) -> bool:
    """
    Проверка, что сумма процентов равна 100%.
    
    Args:
        percentages: Список процентов
        tolerance: Допустимая погрешность
        
    Returns:
        bool: True если сумма ~100%
        
    Example:
        >>> validate_percentage_sum([45.5, 30.0, 24.5])
        True
        >>> validate_percentage_sum([45.0, 30.0, 20.0])
        False
    """
    total = sum(percentages)
    is_valid = abs(total - 100.0) <= tolerance
    
    if not is_valid:
        logger.warning(f"Сумма процентов = {total:.2f}%, требуется 100%")
    
    return is_valid


def validate_stock_availability(
    required: Dict[int, float],
    available: Dict[int, float]
) -> Tuple[bool, List[Dict]]:
    """
    Проверка достаточности остатков.
    
    Args:
        required: Требуемые количества {sku_id: quantity}
        available: Доступные количества {sku_id: quantity}
        
    Returns:
        Tuple[bool, List[Dict]]:
            - True если всего достаточно
            - Список недостающих [{sku_id, required, available, shortage}, ...]
            
    Example:
        >>> validate_stock_availability(
        ...     required={1: 50.0, 2: 30.0},
        ...     available={1: 60.0, 2: 20.0}
        ... )
        (False, [{'sku_id': 2, 'required': 30.0, 'available': 20.0, 'shortage': 10.0}])
    """
    shortages = []
    
    for sku_id, req_qty in required.items():
        avail_qty = available.get(sku_id, 0)
        
        if avail_qty < req_qty:
            shortage = req_qty - avail_qty
            shortages.append({
                'sku_id': sku_id,
                'required': req_qty,
                'available': avail_qty,
                'shortage': round(shortage, 2)
            })
            
            logger.warning(f"Недостаток SKU ID={sku_id}: требуется {req_qty}, доступно {avail_qty}")
    
    is_sufficient = len(shortages) == 0
    
    return is_sufficient, shortages


def validate_weight_range(
    weight: float,
    min_weight: float = 0.1,
    max_weight: float = 9999.0
) -> bool:
    """
    Проверка веса в допустимом диапазоне.
    
    Args:
        weight: Проверяемый вес (кг)
        min_weight: Минимальный допустимый вес (кг)
        max_weight: Максимальный допустимый вес (кг)
        
    Returns:
        bool: True если вес в допустимом диапазоне
    """
    is_valid = min_weight <= weight <= max_weight
    
    if not is_valid:
        logger.warning(f"Вес {weight} кг вне диапазона [{min_weight}, {max_weight}]")
    
    return is_valid


# ============================================================================
# РАСЧЕТЫ ОТХОДОВ
# ============================================================================

def calculate_production_waste(
    raw_total: float,
    actual_output: float,
    expected_yield_percent: float
) -> Tuple[float, float]:
    """
    Расчет отходов при производстве.
    
    Args:
        raw_total: Общий вес использованного сырья (кг)
        actual_output: Фактический выход полуфабриката (кг)
        expected_yield_percent: Ожидаемый процент выхода
        
    Returns:
        Tuple[float, float]:
            - Фактический процент выхода
            - Вес отходов (кг)
            
    Example:
        >>> calculate_production_waste(117.65, 95.0, 85.0)
        (80.73, 22.65)
    """
    expected_output = raw_total * (expected_yield_percent / 100.0)
    waste = raw_total - actual_output
    actual_yield = (actual_output / raw_total) * 100.0
    
    logger.info(
        f"Отходы производства: {waste:.2f} кг "
        f"(выход {actual_yield:.1f}% вместо {expected_yield_percent}%)"
    )
    
    return round(actual_yield, 2), round(waste, 2)


def calculate_packing_waste_percentage(
    total_weight: float,
    remainder: float
) -> float:
    """
    Расчет процента остатка при фасовке.
    
    Args:
        total_weight: Общий вес до фасовки (кг)
        remainder: Остаток после фасовки (кг)
        
    Returns:
        float: Процент остатка
        
    Example:
        >>> calculate_packing_waste_percentage(113.4, 13.4)
        11.82
    """
    if total_weight <= 0:
        return 0.0
    
    percentage = (remainder / total_weight) * 100.0
    
    return round(percentage, 2)


# ============================================================================
# УТИЛИТЫ ДЛЯ ОКРУГЛЕНИЯ
# ============================================================================

def round_to_precision(value: float, precision: int = 2) -> float:
    """
    Округление до заданной точности с правилом ROUND_HALF_UP.
    
    Args:
        value: Значение для округления
        precision: Количество знаков после запятой
        
    Returns:
        float: Округленное значение
        
    Example:
        >>> round_to_precision(123.456, 2)
        123.46
    """
    if precision < 0:
        raise ValueError("Точность должна быть >= 0")
    
    decimal_value = Decimal(str(value))
    rounded = decimal_value.quantize(
        Decimal(10) ** -precision,
        rounding=ROUND_HALF_UP
    )
    
    return float(rounded)


def format_weight(weight: float, show_zero: bool = True) -> str:
    """
    Форматирование веса для отображения.
    
    Args:
        weight: Вес (кг)
        show_zero: Показывать ли нулевые веса
        
    Returns:
        str: Отформатированная строка
        
    Example:
        >>> format_weight(123.456)
        '123.46 кг'
        >>> format_weight(0.0, show_zero=False)
        '—'
    """
    if not show_zero and weight == 0:
        return "—"
    
    # Убираем незначащие нули
    if weight == int(weight):
        return f"{int(weight)} кг"
    else:
        return f"{weight:.2f} кг".rstrip('0').rstrip('.')


# ============================================================================
# РАСЧЕТЫ ДЛЯ СТАТИСТИКИ
# ============================================================================

def calculate_average_yield(batches: List[Dict]) -> float:
    """
    Расчет среднего процента выхода по партиям.
    
    Args:
        batches: Список партий с полями 'actual_weight', 'target_weight'
        
    Returns:
        float: Средний процент выхода
        
    Example:
        >>> batches = [
        ...     {'actual_weight': 95.0, 'target_weight': 100.0},
        ...     {'actual_weight': 98.0, 'target_weight': 100.0}
        ... ]
        >>> calculate_average_yield(batches)
        96.5
    """
    if not batches:
        return 0.0
    
    yields = []
    for batch in batches:
        actual = batch.get('actual_weight', 0)
        target = batch.get('target_weight', 0)
        
        if target > 0:
            yield_percent = (actual / target) * 100.0
            yields.append(yield_percent)
    
    if not yields:
        return 0.0
    
    avg = sum(yields) / len(yields)
    return round(avg, 2)


def calculate_material_utilization(
    used: float,
    total: float
) -> float:
    """
    Расчет коэффициента использования материала.
    
    Args:
        used: Использованное количество
        total: Общее количество
        
    Returns:
        float: Процент использования (0-100)
        
    Example:
        >>> calculate_material_utilization(80.0, 100.0)
        80.0
    """
    if total <= 0:
        return 0.0
    
    utilization = (used / total) * 100.0
    return round(utilization, 2)


def calculate_waste_ratio(
    waste: float,
    total: float
) -> float:
    """
    Расчет коэффициента отходов.
    
    Args:
        waste: Количество отходов
        total: Общее количество
        
    Returns:
        float: Процент отходов (0-100)
        
    Example:
        >>> calculate_waste_ratio(5.0, 100.0)
        5.0
    """
    if total <= 0:
        return 0.0
    
    ratio = (waste / total) * 100.0
    return round(ratio, 2)


# ============================================================================
# ОПТИМИЗАЦИЯ ПРОИЗВОДСТВА
# ============================================================================

def suggest_optimal_batch_size(
    recipe_components: List[Dict],
    available_materials: Dict[int, float],
    min_batch: float = 50.0,
    max_batch: float = 500.0
) -> Optional[float]:
    """
    Предложение оптимального размера партии под доступное сырье.
    
    Args:
        recipe_components: Компоненты рецепта с процентами
        available_materials: Доступное сырье {material_id: quantity}
        min_batch: Минимальный размер партии (кг)
        max_batch: Максимальный размер партии (кг)
        
    Returns:
        Optional[float]: Рекомендуемый размер партии или None
        
    Example:
        >>> suggest_optimal_batch_size(
        ...     [{'raw_material_id': 1, 'percentage': 50.0}],
        ...     {1: 100.0},
        ...     min_batch=50.0
        ... )
        100.0
    """
    if not recipe_components or not available_materials:
        return None
    
    # Для каждого компонента рассчитываем максимальный размер партии
    max_batches = []
    
    for component in recipe_components:
        material_id = component['raw_material_id']
        percentage = component['percentage']
        
        available = available_materials.get(material_id, 0)
        
        if available <= 0 or percentage <= 0:
            continue
        
        # Сколько можем произвести из этого компонента
        max_from_component = (available * 100.0) / percentage
        max_batches.append(max_from_component)
    
    if not max_batches:
        return None
    
    # Ограничиваемся минимумом (самый дефицитный компонент)
    optimal = min(max_batches)
    
    # Применяем ограничения
    optimal = max(min_batch, min(optimal, max_batch))
    
    # Округляем до красивого числа
    if optimal >= 100:
        optimal = round(optimal / 10) * 10  # Кратно 10
    else:
        optimal = round(optimal / 5) * 5  # Кратно 5
    
    logger.info(f"Рекомендуемый размер партии: {optimal} кг")
    
    return optimal
