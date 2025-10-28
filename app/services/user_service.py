"""
Сервис для работы с пользователями.
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import User
from app.logger import get_logger

logger = get_logger("user_service")


def get_or_create_user(
    db: Session,
    telegram_id: int,
    username: Optional[str] = None,
    full_name: Optional[str] = None
) -> User:
    """Получить или создать пользователя."""
    user = db.execute(
        select(User).where(User.telegram_id == telegram_id)
    ).scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            is_admin=False
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user: {telegram_id} ({username})")
    
    return user


def is_admin(db: Session, telegram_id: int) -> bool:
    """Проверить, является ли пользователь администратором."""
    user = db.execute(
        select(User).where(User.telegram_id == telegram_id)
    ).scalar_one_or_none()
    
    return user.is_admin if user else False


def set_admin(db: Session, telegram_id: int, is_admin: bool = True):
    """Установить/снять права администратора."""
    user = db.execute(
        select(User).where(User.telegram_id == telegram_id)
    ).scalar_one_or_none()
    
    if user:
        user.is_admin = is_admin
        db.commit()
        logger.info(f"User {telegram_id} admin status set to {is_admin}")
