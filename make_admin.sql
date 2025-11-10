-- Скрипт для назначения пользователя администратором
-- Telegram ID: 157625351

-- Обновляем пользователя: делаем админом и утверждаем
UPDATE users
SET
    is_admin = true,
    approval_status = 'approved',
    can_receive_materials = true,
    can_produce = true,
    can_pack = true,
    can_ship = true,
    is_active = true,
    updated_at = NOW()
WHERE telegram_id = 157625351;

-- Проверяем результат
SELECT
    id,
    telegram_id,
    username,
    full_name,
    is_admin,
    approval_status,
    can_receive_materials,
    can_produce,
    can_pack,
    can_ship
FROM users
WHERE telegram_id = 157625351;
