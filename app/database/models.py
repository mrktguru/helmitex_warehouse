# app/database/models.py - ОБНОВЛЕННАЯ ВЕРСИЯ

"""
Модели базы данных для складского учета Helmitex Warehouse.
Включает полную логику: сырье → бочки → упаковка → отгрузка
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Float, Boolean, Text
from sqlalchemy.orm import relationship
import enum

from .db import Base


# ============================================================================
# ENUM ТИПЫ
# ============================================================================

class SKUType(str, enum.Enum):
    """Тип SKU"""
    raw = "raw"  # Сырье
    semi = "semi"  # Полуфабрикат (бочки)
    finished = "finished"  # Готовая продукция


class CategoryType(str, enum.Enum):
    """Категории сырья"""
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
    pieces = "шт"  # Штуки


class MovementType(str, enum.Enum):
    """Тип движения товара"""
    in_ = "in"  # Приход
    out = "out"  # Расход
    production = "production"  # Производство
    packing = "packing"  # Фасовка
    shipment = "shipment"  # Отгрузка
    waste = "waste"  # Списание отходов


class RecipeStatus(str, enum.Enum):
    """Статус технологической карты"""
    draft = "draft"  # Черновик
    active = "active"  # Активна
    archived = "archived"  # Архивирована


class ProductionStatus(str, enum.Enum):
    """Статус производства"""
    planned = "planned"  # Запланировано
    in_progress = "in_progress"  # В работе
    completed = "completed"  # Завершено
    cancelled = "cancelled"  # Отменено


class WasteType(str, enum.Enum):
    """Тип отходов"""
    semifinished_defect = "semifinished_defect"  # Брак полуфабриката
    container_defect = "container_defect"  # Брак тары
    technological_loss = "technological_loss"  # Технологические потери


class ContainerType(str, enum.Enum):
    """Тип тары"""
    bucket = "bucket"  # Ведро
    can = "can"  # Банка
    bag = "bag"  # Мешок
    other = "other"  # Другое


# ============================================================================
# ОСНОВНЫЕ ТАБЛИЦЫ
# ============================================================================

class User(Base):
    """Пользователь системы"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    movements = relationship("Movement", back_populates="user")
    production_batches = relationship("ProductionBatch", back_populates="user")
    recipes_created = relationship("TechnologicalCard", back_populates="created_by_user")


class Warehouse(Base):
    """Склад"""
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    stock = relationship("Stock", back_populates="warehouse")
    movements = relationship("Movement", back_populates="warehouse")
    barrels = relationship("Barrel", back_populates="warehouse")


class SKU(Base):
    """Товарная позиция (номенклатура)"""
    __tablename__ = "skus"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(Enum(SKUType), nullable=False, index=True)
    category = Column(Enum(CategoryType), nullable=True)  # Только для сырья
    unit = Column(Enum(UnitType), default=UnitType.kg)
    min_stock = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    stock = relationship("Stock", back_populates="sku")
    movements = relationship("Movement", back_populates="sku")
    recipe_components = relationship("RecipeComponent", back_populates="raw_material")
    recipes_output = relationship("TechnologicalCard", back_populates="semi_product")
    packing_variants = relationship("PackingVariant", back_populates="finished_product")
    barrels = relationship("Barrel", back_populates="semi_product")


class Stock(Base):
    """Остатки на складе"""
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    quantity = Column(Float, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    warehouse = relationship("Warehouse", back_populates="stock")
    sku = relationship("SKU", back_populates="stock")

    # Индексы
    __table_args__ = (
        {'schema': None},
    )


class Movement(Base):
    """Движение товара"""
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    type = Column(Enum(MovementType), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Связь с бочкой (если движение связано с бочкой)
    barrel_id = Column(Integer, ForeignKey("barrels.id"), nullable=True)
    
    # Связь с партией производства
    production_batch_id = Column(Integer, ForeignKey("production_batches.id"), nullable=True)

    # Relationships
    warehouse = relationship("Warehouse", back_populates="movements")
    sku = relationship("SKU", back_populates="movements")
    user = relationship("User", back_populates="movements")
    barrel = relationship("Barrel", back_populates="movements")
    production_batch = relationship("ProductionBatch", back_populates="movements")


# ============================================================================
# ТЕХНОЛОГИЧЕСКИЕ КАРТЫ И РЕЦЕПТЫ
# ============================================================================

class TechnologicalCard(Base):
    """Технологическая карта (рецепт)"""
    __tablename__ = "technological_cards"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    semi_product_id = Column(Integer, ForeignKey("skus.id"), nullable=False)  # Полуфабрикат
    yield_percent = Column(Float, nullable=False)  # Процент выхода (50-100)
    status = Column(Enum(RecipeStatus), default=RecipeStatus.draft, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    semi_product = relationship("SKU", back_populates="recipes_output")
    components = relationship("RecipeComponent", back_populates="recipe", cascade="all, delete-orphan")
    created_by_user = relationship("User", back_populates="recipes_created")
    production_batches = relationship("ProductionBatch", back_populates="recipe")


class RecipeComponent(Base):
    """Компонент технологической карты"""
    __tablename__ = "recipe_components"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("technological_cards.id"), nullable=False)
    raw_material_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    percentage = Column(Float, nullable=False)  # Процент в рецепте
    order = Column(Integer, default=0)  # Порядок добавления

    # Relationships
    recipe = relationship("TechnologicalCard", back_populates="components")
    raw_material = relationship("SKU", back_populates="recipe_components")


# ============================================================================
# ПРОИЗВОДСТВО (БОЧКИ)
# ============================================================================

class ProductionBatch(Base):
    """Партия производства"""
    __tablename__ = "production_batches"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("technological_cards.id"), nullable=False)
    target_weight = Column(Float, nullable=False)  # Планируемый вес
    actual_weight = Column(Float, nullable=True)  # Фактический вес
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(ProductionStatus), default=ProductionStatus.planned)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    recipe = relationship("TechnologicalCard", back_populates="production_batches")
    user = relationship("User", back_populates="production_batches")
    barrels = relationship("Barrel", back_populates="production_batch")
    movements = relationship("Movement", back_populates="production_batch")


class Barrel(Base):
    """Бочка с полуфабрикатом"""
    __tablename__ = "barrels"

    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    semi_product_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    production_batch_id = Column(Integer, ForeignKey("production_batches.id"), nullable=False)
    
    initial_weight = Column(Float, nullable=False)  # Начальный вес
    current_weight = Column(Float, nullable=False)  # Текущий вес
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # FIFO по дате
    is_active = Column(Boolean, default=True)  # Активна ли бочка
    
    # Relationships
    warehouse = relationship("Warehouse", back_populates="barrels")
    semi_product = relationship("SKU", back_populates="barrels")
    production_batch = relationship("ProductionBatch", back_populates="barrels")
    movements = relationship("Movement", back_populates="barrel")


# ============================================================================
# ФАСОВКА И УПАКОВКА
# ============================================================================

class PackingVariant(Base):
    """Варианты упаковки"""
    __tablename__ = "packing_variants"

    id = Column(Integer, primary_key=True)
    semi_product_id = Column(Integer, ForeignKey("skus.id"), nullable=False)  # Полуфабрикат
    finished_product_id = Column(Integer, ForeignKey("skus.id"), nullable=False)  # Готовая продукция
    container_type = Column(Enum(ContainerType), nullable=False)
    weight_per_unit = Column(Float, nullable=False)  # Вес одной упаковки
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    semi_product = relationship("SKU", foreign_keys=[semi_product_id])
    finished_product = relationship("SKU", back_populates="packing_variants", foreign_keys=[finished_product_id])


# ============================================================================
# ОТГРУЗКА
# ============================================================================

class Recipient(Base):
    """Получатель (клиент)"""
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    contact_info = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    shipments = relationship("Shipment", back_populates="recipient")


class Shipment(Base):
    """Отгрузка"""
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True)
    recipient_id = Column(Integer, ForeignKey("recipients.id"), nullable=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    recipient = relationship("Recipient", back_populates="shipments")
    items = relationship("ShipmentItem", back_populates="shipment", cascade="all, delete-orphan")


class ShipmentItem(Base):
    """Позиция отгрузки"""
    __tablename__ = "shipment_items"

    id = Column(Integer, primary_key=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    quantity = Column(Float, nullable=False)

    # Relationships
    shipment = relationship("Shipment", back_populates="items")
    sku = relationship("SKU")


# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ТАБЛИЦЫ
# ============================================================================

class InventoryReserve(Base):
    """Резервирование товара"""
    __tablename__ = "inventory_reserves"

    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    reserved_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class WasteRecord(Base):
    """Учет отходов"""
    __tablename__ = "waste_records"

    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    waste_type = Column(Enum(WasteType), nullable=False)
    quantity = Column(Float, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
