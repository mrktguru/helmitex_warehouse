"""
Модели базы данных для складского учета Helmitex Warehouse.
Полная логика: сырье → бочки (полуфабрикаты) → упаковка → отгрузка

Основные сущности:
- User: пользователи системы
- Warehouse: склады
- SKU: номенклатура (сырье/полуфабрикаты/готовая продукция)
- Stock: остатки товаров
- Movement: движения товаров
- TechnologicalCard: технологические карты (рецепты)
- RecipeComponent: компоненты рецептов
- ProductionBatch: партии производства
- Barrel: бочки с полуфабрикатами
- PackingVariant: варианты упаковки
- Recipient: получатели (клиенты)
- Shipment: отгрузки
- ShipmentItem: позиции отгрузок
- InventoryReserve: резервирование товаров
- WasteRecord: учет отходов
"""
from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Enum, ForeignKey, Float, Boolean, Text, Index
from sqlalchemy.orm import relationship
import enum

from app.database.db import Base

# ============================================================================
# ENUM ТИПЫ
# ============================================================================

class SKUType(str, enum.Enum):
    """Тип SKU (номенклатуры)"""
    raw = "raw"  # Сырье
    semi = "semi"  # Полуфабрикат (бочки)
    finished = "finished"  # Готовая продукция


class CategoryType(str, enum.Enum):
    """Категории сырья (только для SKUType.raw)"""
    thickeners = "Загустители"
    colorants = "Красители"
    fragrances = "Отдушки"
    bases = "Основы"
    additives = "Добавки"
    packaging = "Упаковка"


class UnitType(str, enum.Enum):
    """Единицы измерения"""
    kg = "кг"  # Килограммы (основная единица)
    liters = "л"  # Литры
    grams = "г"  # Граммы
    pieces = "шт"  # Штуки (для готовой продукции)


class MovementType(str, enum.Enum):
    """Тип движения товара"""
    in_ = "in"  # Приход сырья
    out = "out"  # Расход (общий)
    production = "production"  # Производство (создание бочек)
    packing = "packing"  # Фасовка (из бочек в готовую продукцию)
    shipment = "shipment"  # Отгрузка
    waste = "waste"  # Списание отходов
    adjustment = "adjustment"  # Корректировка остатков


class RecipeStatus(str, enum.Enum):
    """Статус технологической карты"""
    draft = "draft"  # Черновик (требует утверждения)
    active = "active"  # Активна (можно использовать)
    archived = "archived"  # Архивирована


class ProductionStatus(str, enum.Enum):
    """Статус производства (партии)"""
    planned = "planned"  # Запланировано
    in_progress = "in_progress"  # В работе
    completed = "completed"  # Завершено
    cancelled = "cancelled"  # Отменено


class ShipmentStatus(str, enum.Enum):
    """Статус отгрузки"""
    pending = "pending"  # Ожидает
    in_progress = "in_progress"  # В процессе
    completed = "completed"  # Завершена
    cancelled = "cancelled"  # Отменена


class ReserveType(str, enum.Enum):
    """Тип резервирования"""
    shipment = "shipment"  # Резерв под отгрузку
    production = "production"  # Резерв под производство
    manual = "manual"  # Ручной резерв


class WasteType(str, enum.Enum):
    """Тип отходов"""
    semifinished_defect = "semifinished_defect"  # Брак полуфабриката
    container_defect = "container_defect"  # Брак тары
    technological_loss = "technological_loss"  # Технологические потери


class ContainerType(str, enum.Enum):
    """Тип тары для упаковки"""
    bucket = "bucket"  # Ведро
    can = "can"  # Банка
    bag = "bag"  # Мешок
    bottle = "bottle"  # Бутылка
    other = "other"  # Другое


# ============================================================================
# ОСНОВНЫЕ ТАБЛИЦЫ
# ============================================================================

class User(Base):
    """
    Пользователь системы.
    Авторизация через Telegram ID.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)  # BigInteger для больших Telegram ID
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    # ДОБАВЛЕННЫЕ ПОЛЯ для совместимости с bot.py:
    is_active = Column(Boolean, default=True, nullable=False)
    can_receive_materials = Column(Boolean, default=False, nullable=False)
    can_produce = Column(Boolean, default=False, nullable=False)
    can_pack = Column(Boolean, default=False, nullable=False)
    can_ship = Column(Boolean, default=False, nullable=False)
    last_active = Column(DateTime, default=datetime.utcnow, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    # Relationships (без изменений)
    movements = relationship("Movement", back_populates="user")
    production_batches = relationship("ProductionBatch", back_populates="user")
    recipes_created = relationship("TechnologicalCard", back_populates="created_by_user")

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"

class Warehouse(Base):
    """
    Склад.
    Может быть один основной (is_default=True).
    """
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    location = Column(String(500), nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    stock = relationship("Stock", back_populates="warehouse", cascade="all, delete-orphan")
    movements = relationship("Movement", back_populates="warehouse")
    barrels = relationship("Barrel", back_populates="warehouse")

    def __repr__(self):
        return f"<Warehouse(id={self.id}, name={self.name}, is_default={self.is_default})>"


class SKU(Base):
    """
    Товарная позиция (номенклатура).
    
    type:
    - raw: сырье (требует category)
    - semi: полуфабрикат (бочки)
    - finished: готовая продукция
    """
    __tablename__ = "skus"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    type = Column(Enum(SKUType), nullable=False, index=True)
    category = Column(Enum(CategoryType), nullable=True)  # Только для type='raw'
    unit = Column(Enum(UnitType), default=UnitType.kg, nullable=False)
    min_stock = Column(Float, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    stock = relationship("Stock", back_populates="sku", cascade="all, delete-orphan")
    movements = relationship("Movement", back_populates="sku")
    
    # Для сырья: в каких рецептах используется
    recipe_components = relationship("RecipeComponent", back_populates="raw_material")
    
    # Для полуфабрикатов: какие рецепты производят
    recipes_output = relationship("TechnologicalCard", back_populates="semi_product")
    
    # Для полуфабрикатов: связь с бочками
    barrels = relationship("Barrel", back_populates="semi_product")
    
    # Для готовой продукции: варианты упаковки
    packing_variants_as_finished = relationship(
        "PackingVariant", 
        back_populates="finished_product",
        foreign_keys="PackingVariant.finished_product_id"
    )
    
    # Для полуфабрикатов: варианты упаковки (как источник)
    packing_variants_as_semi = relationship(
        "PackingVariant",
        back_populates="semi_product",
        foreign_keys="PackingVariant.semi_product_id"
    )

    def __repr__(self):
        return f"<SKU(id={self.id}, code={self.code}, name={self.name}, type={self.type.value})>"


class Stock(Base):
    """
    Остатки товаров на складе.
    Уникальная комбинация warehouse_id + sku_id.
    """
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    quantity = Column(Float, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    warehouse = relationship("Warehouse", back_populates="stock")
    sku = relationship("SKU", back_populates="stock")

    # Unique constraint
    __table_args__ = (
        Index('idx_warehouse_sku', 'warehouse_id', 'sku_id', unique=True),
    )

    def __repr__(self):
        return f"<Stock(id={self.id}, warehouse_id={self.warehouse_id}, sku_id={self.sku_id}, quantity={self.quantity})>"


class Movement(Base):
    """
    Движение товара (история всех операций).
    
    type:
    - in_: приход сырья
    - production: производство (списание сырья, оприходование полуфабриката)
    - packing: фасовка (списание полуфабриката, оприходование готовой продукции)
    - shipment: отгрузка
    - waste: списание отходов
    - adjustment: корректировка остатков
    """
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    type = Column(Enum(MovementType), nullable=False, index=True)
    quantity = Column(Float, nullable=False)  # Положительное при приходе, отрицательное при расходе
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Связь с бочкой (если движение связано с конкретной бочкой)
    barrel_id = Column(Integer, ForeignKey("barrels.id"), nullable=True, index=True)
    
    # Связь с партией производства
    production_batch_id = Column(Integer, ForeignKey("production_batches.id"), nullable=True, index=True)
    
    # Связь с отгрузкой
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=True, index=True)

    # Relationships
    warehouse = relationship("Warehouse", back_populates="movements")
    sku = relationship("SKU", back_populates="movements")
    user = relationship("User", back_populates="movements")
    barrel = relationship("Barrel", back_populates="movements")
    production_batch = relationship("ProductionBatch", back_populates="movements")
    shipment = relationship("Shipment", back_populates="movements")

    def __repr__(self):
        return f"<Movement(id={self.id}, type={self.type.value}, sku_id={self.sku_id}, quantity={self.quantity})>"


# ============================================================================
# ТЕХНОЛОГИЧЕСКИЕ КАРТЫ И РЕЦЕПТЫ
# ============================================================================

class TechnologicalCard(Base):
    """
    Технологическая карта (рецепт производства).
    
    Определяет:
    - Какой полуфабрикат производится
    - Из какого сырья (components)
    - В каких пропорциях (percentage в RecipeComponent)
    - Процент выхода (yield_percent)
    
    Статусы:
    - draft: черновик, требует утверждения владельцем
    - active: активна, можно использовать в производстве
    - archived: архивирована, не используется
    """
    __tablename__ = "technological_cards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    semi_product_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    yield_percent = Column(Float, nullable=False)  # 50-100% (процент выхода)
    status = Column(Enum(RecipeStatus), default=RecipeStatus.draft, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    semi_product = relationship("SKU", back_populates="recipes_output")
    components = relationship("RecipeComponent", back_populates="recipe", cascade="all, delete-orphan")
    created_by_user = relationship("User", back_populates="recipes_created")
    production_batches = relationship("ProductionBatch", back_populates="recipe")

    def __repr__(self):
        return f"<TechnologicalCard(id={self.id}, name={self.name}, status={self.status.value})>"


class RecipeComponent(Base):
    """
    Компонент технологической карты.
    
    Определяет процентное содержание сырья в рецепте.
    Сумма всех percentage в рамках одного recipe_id должна быть 100%.
    
    order: порядок добавления компонентов (для отображения)
    """
    __tablename__ = "recipe_components"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("technological_cards.id"), nullable=False, index=True)
    raw_material_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    percentage = Column(Float, nullable=False)  # Процент в рецепте (0-100)
    order = Column(Integer, default=0, nullable=False)  # Порядок добавления

    # Relationships
    recipe = relationship("TechnologicalCard", back_populates="components")
    raw_material = relationship("SKU", back_populates="recipe_components")

    def __repr__(self):
        return f"<RecipeComponent(id={self.id}, recipe_id={self.recipe_id}, percentage={self.percentage}%)>"


# ============================================================================
# ПРОИЗВОДСТВО (БОЧКИ)
# ============================================================================

class ProductionBatch(Base):
    """
    Партия производства (замес).
    
    Представляет один цикл производства по технологической карте.
    Создается при планировании производства.
    
    target_weight: планируемый вес готового полуфабриката
    actual_weight: фактический вес (заполняется после производства)
    
    Статусы:
    - planned: запланировано
    - in_progress: в работе
    - completed: завершено (создана бочка)
    - cancelled: отменено
    """
    __tablename__ = "production_batches"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("technological_cards.id"), nullable=False, index=True)
    target_weight = Column(Float, nullable=False)  # Планируемый вес (кг)
    actual_weight = Column(Float, nullable=True)  # Фактический вес (кг)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(Enum(ProductionStatus), default=ProductionStatus.planned, nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    recipe = relationship("TechnologicalCard", back_populates="production_batches")
    user = relationship("User", back_populates="production_batches")
    barrels = relationship("Barrel", back_populates="production_batch")
    movements = relationship("Movement", back_populates="production_batch")

    def __repr__(self):
        return f"<ProductionBatch(id={self.id}, recipe_id={self.recipe_id}, status={self.status.value})>"


class Barrel(Base):
    """
    Бочка с полуфабрикатом.
    
    Создается при производстве (после замеса).
    Хранит информацию о весе полуфабриката.
    
    initial_weight: начальный вес при создании
    current_weight: текущий вес (уменьшается при фасовке)
    
    FIFO: при фасовке используются самые старые бочки (по created_at)
    is_active: False если бочка полностью использована
    """
    __tablename__ = "barrels"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    semi_product_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    production_batch_id = Column(Integer, ForeignKey("production_batches.id"), nullable=False, index=True)
    
    initial_weight = Column(Float, nullable=False)  # Начальный вес (кг)
    current_weight = Column(Float, nullable=False)  # Текущий вес (кг)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)  # Для FIFO
    is_active = Column(Boolean, default=True, nullable=False, index=True)  # Активна ли бочка
    
    # Relationships
    warehouse = relationship("Warehouse", back_populates="barrels")
    semi_product = relationship("SKU", back_populates="barrels")
    production_batch = relationship("ProductionBatch", back_populates="barrels")
    movements = relationship("Movement", back_populates="barrel")

    def __repr__(self):
        return f"<Barrel(id={self.id}, semi_product_id={self.semi_product_id}, current_weight={self.current_weight})>"


# ============================================================================
# ФАСОВКА И УПАКОВКА
# ============================================================================

class PackingVariant(Base):
    """
    Вариант упаковки (связь полуфабрикат → готовая продукция).
    
    Определяет:
    - Из какого полуфабриката
    - В какую готовую продукцию
    - Тип тары
    - Вес одной упаковки
    
    Пример:
    - Полуфабрикат: "Краска белая (п/ф)"
    - Готовая продукция: "Краска белая 10кг"
    - Тип тары: ведро
    - Вес: 10 кг
    """
    __tablename__ = "packing_variants"

    id = Column(Integer, primary_key=True, index=True)
    semi_product_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    finished_product_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    container_type = Column(Enum(ContainerType), nullable=False)
    weight_per_unit = Column(Float, nullable=False)  # Вес одной упаковки (кг)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    semi_product = relationship(
        "SKU", 
        back_populates="packing_variants_as_semi",
        foreign_keys=[semi_product_id]
    )
    finished_product = relationship(
        "SKU", 
        back_populates="packing_variants_as_finished",
        foreign_keys=[finished_product_id]
    )

    def __repr__(self):
        return f"<PackingVariant(id={self.id}, weight_per_unit={self.weight_per_unit}kg)>"


# ============================================================================
# ОТГРУЗКА
# ============================================================================

class Recipient(Base):
    """
    Получатель (клиент).
    Опционально указывается при отгрузке.
    """
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    contact_info = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    shipments = relationship("Shipment", back_populates="recipient")

    def __repr__(self):
        return f"<Recipient(id={self.id}, name={self.name})>"


class Shipment(Base):
    """
    Отгрузка готовой продукции.
    
    Группирует несколько позиций (ShipmentItem) в одну отгрузку.
    """
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("recipients.id"), nullable=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    recipient = relationship("Recipient", back_populates="shipments")
    items = relationship("ShipmentItem", back_populates="shipment", cascade="all, delete-orphan")
    movements = relationship("Movement", back_populates="shipment")

    def __repr__(self):
        return f"<Shipment(id={self.id}, created_at={self.created_at})>"


class ShipmentItem(Base):
    """
    Позиция отгрузки (одна SKU в отгрузке).
    """
    __tablename__ = "shipment_items"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False, index=True)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    quantity = Column(Float, nullable=False)

    # Relationships
    shipment = relationship("Shipment", back_populates="items")
    sku = relationship("SKU")

    def __repr__(self):
        return f"<ShipmentItem(id={self.id}, shipment_id={self.shipment_id}, quantity={self.quantity})>"


# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ТАБЛИЦЫ
# ============================================================================

class InventoryReserve(Base):
    """
    Резервирование товара (будущая функция).
    
    Позволяет зарезервировать товар перед отгрузкой,
    чтобы другие пользователи не могли его отгрузить.
    """
    __tablename__ = "inventory_reserves"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    reserved_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reserve_type = Column(Enum(ReserveType), default=ReserveType.manual, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)  # Срок резервирования

    def __repr__(self):
        return f"<InventoryReserve(id={self.id}, sku_id={self.sku_id}, quantity={self.quantity})>"


class WasteRecord(Base):
    """
    Учет отходов.
    
    Типы отходов:
    - semifinished_defect: брак полуфабриката (при производстве)
    - container_defect: брак тары (при фасовке)
    - technological_loss: технологические потери
    """
    __tablename__ = "waste_records"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False, index=True)
    waste_type = Column(Enum(WasteType), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<WasteRecord(id={self.id}, waste_type={self.waste_type.value}, quantity={self.quantity})>"
