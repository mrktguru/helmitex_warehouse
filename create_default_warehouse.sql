-- Создание склада по умолчанию (если его нет)
INSERT INTO warehouses (name, location, is_default, created_at)
VALUES ('Основной склад', 'Главный офис', true, NOW())
ON CONFLICT DO NOTHING;

-- Проверка
SELECT id, name, location, is_default, created_at
FROM warehouses
WHERE is_default = true;
