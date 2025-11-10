-- ============================================================================
-- Комплексное исправление базы данных
-- ============================================================================

-- 1. Проверка текущей версии Alembic
SELECT 'Current Alembic version:' as info, version_num FROM alembic_version;

-- 2. Установка правильной версии (таблицы уже существуют после 20250204_001)
DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('20250204_001');

-- 3. Добавление недостающих колонок из миграции 20251110_001
--    (эти колонки нужны для корректной работы бота)

-- Добавление updated_at в таблицу users
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

-- Добавление is_active в таблицу technological_cards
ALTER TABLE technological_cards ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;
CREATE INDEX IF NOT EXISTS ix_technological_cards_is_active ON technological_cards (is_active);

-- Добавление is_active в таблицу packing_variants
ALTER TABLE packing_variants ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;
CREATE INDEX IF NOT EXISTS ix_packing_variants_is_active ON packing_variants (is_active);

-- 4. Обновление версии Alembic до 20251110_001
DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('20251110_001');

-- 5. Проверка результата
SELECT 'New Alembic version:' as info, version_num FROM alembic_version;

-- 6. Проверка добавленных колонок
SELECT
    'users' as table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'updated_at'
UNION ALL
SELECT
    'technological_cards' as table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'technological_cards' AND column_name = 'is_active'
UNION ALL
SELECT
    'packing_variants' as table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'packing_variants' AND column_name = 'is_active';

-- Готово!
SELECT '✓ Migration completed successfully!' as status;
