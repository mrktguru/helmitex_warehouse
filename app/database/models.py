"""
Модели базы данных для складского учета Helmitex Warehouse.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
import enum

from .db import Base


class SKUType(str, enum.Enum):
    """Тип SKU"""
    raw = "raw"  # Сырье
    finished = "finished"  # Готовая продукция


class MovementType(str, enum.Enum):
    """Тип движения товара"""
    in_ = "in"  # Приход
    out = "out"  # Расход
    transfer = "transfer"  # Перемещение
    adjustment = "adjustment"  # Корректировка


class OrderType(str, enum.Enum):
    """Тип заказа"""
    purchase = "purchase"  # Закупка
    production = "production"  # Производство
    sale = "sale"  # Продажа


class OrderStatus(str, enum.Enum):
    """Статус заказа"""
    pending = "pending"  # Ожидает
    in_progress = "in_progress"  # В работе
    completed = "completed"  # Завершен
    cancelled = "cancelled"  # Отменен


class User(Base):
    """Пользователь системы"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    movements = relationship("Movement", back_populates="user")
    orders = relationship("Order", back_populates="user")


class Warehouse(Base):
    """Склад"""
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    stock = relationship("Stock", back_populates="warehouse")
    movements = relationship("Movement", back_populates="warehouse")
    orders = relationship("Order", back_populates="warehouse")


class SKU(Base):
    """Товарная позиция (Stock Keeping Unit)"""
    __tablename__ = "skus"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    type = Column(Enum(SKUType), nullable=False)
    unit = Column(String, default="шт")
    min_stock = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    stock = relationship("Stock", back_populates="sku")
    movements = relationship("Movement", back_populates="sku")
    order_items = relationship("OrderItem", back_populates="sku")


class Stock(Base):
    """Остатки на складе"""
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    quantity = Column(Float, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    warehouse = relationship("Warehouse", back_populates="stock")
    sku = relationship("SKU", back_populates="stock")


class Movement(Base):
    """Движение товара"""
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    type = Column(Enum(MovementType), nullable=False)
    quantity = Column(Float, nullable=False)
    from_warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)
    to_warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    warehouse = relationship("Warehouse", back_populates="movements", foreign_keys=[warehouse_id])
    sku = relationship("SKU", back_populates="movements")
    user = relationship("User", back_populates="movements")


class Order(Base):
    """Заказ"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_number = Column(String, unique=True, nullable=False)
    type = Column(Enum(OrderType), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.pending)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Связи
    warehouse = relationship("Warehouse", back_populates="orders")
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """Позиция заказа"""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    sku_id = Column(Integer, ForeignKey("skus.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=True)

    # Связи
    order = relationship("Order", back_populates="items")
    sku = relationship("SKU", back_populates="order_items")
