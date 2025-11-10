-- Тестовые данные для складской системы Helmitex Warehouse
-- Создание номенклатуры: сырье, полуфабрикаты, готовая продукция

-- ============================================================================
-- СЫРЬЕ (RAW MATERIALS)
-- ============================================================================

-- Загустители
INSERT INTO skus (code, name, type, category, unit, min_stock, created_at) VALUES
('RAW-THICK-001', 'Загуститель КМЦ', 'raw', 'Загустители', 'кг', 50, NOW()),
('RAW-THICK-002', 'Загуститель ГЭЦ', 'raw', 'Загустители', 'кг', 30, NOW())
ON CONFLICT (code) DO NOTHING;

-- Красители
INSERT INTO skus (code, name, type, category, unit, min_stock, created_at) VALUES
('RAW-COLOR-001', 'Пигмент красный', 'raw', 'Красители', 'кг', 20, NOW()),
('RAW-COLOR-002', 'Пигмент синий', 'raw', 'Красители', 'кг', 20, NOW()),
('RAW-COLOR-003', 'Пигмент белый (TiO2)', 'raw', 'Красители', 'кг', 100, NOW()),
('RAW-COLOR-004', 'Пигмент черный', 'raw', 'Красители', 'кг', 15, NOW())
ON CONFLICT (code) DO NOTHING;

-- Отдушки
INSERT INTO skus (code, name, type, category, unit, min_stock, created_at) VALUES
('RAW-FRAG-001', 'Отдушка "Лаванда"', 'raw', 'Отдушки', 'кг', 10, NOW()),
('RAW-FRAG-002', 'Отдушка "Роза"', 'raw', 'Отдушки', 'кг', 10, NOW()),
('RAW-FRAG-003', 'Отдушка "Цитрус"', 'raw', 'Отдушки', 'кг', 10, NOW())
ON CONFLICT (code) DO NOTHING;

-- Основы
INSERT INTO skus (code, name, type, category, unit, min_stock, created_at) VALUES
('RAW-BASE-001', 'Вода дистиллированная', 'raw', 'Основы', 'л', 500, NOW()),
('RAW-BASE-002', 'Глицерин', 'raw', 'Основы', 'кг', 100, NOW()),
('RAW-BASE-003', 'Масло минеральное', 'raw', 'Основы', 'л', 200, NOW()),
('RAW-BASE-004', 'Акриловая эмульсия', 'raw', 'Основы', 'кг', 300, NOW())
ON CONFLICT (code) DO NOTHING;

-- Добавки
INSERT INTO skus (code, name, type, category, unit, min_stock, created_at) VALUES
('RAW-ADD-001', 'Консервант Kathon CG', 'raw', 'Добавки', 'кг', 5, NOW()),
('RAW-ADD-002', 'Антисептик', 'raw', 'Добавки', 'кг', 10, NOW()),
('RAW-ADD-003', 'pH регулятор', 'raw', 'Добавки', 'кг', 15, NOW())
ON CONFLICT (code) DO NOTHING;

-- Упаковка
INSERT INTO skus (code, name, type, category, unit, min_stock, created_at) VALUES
('RAW-PACK-001', 'Ведро пластиковое 10л', 'raw', 'Упаковка', 'шт', 100, NOW()),
('RAW-PACK-002', 'Ведро пластиковое 5л', 'raw', 'Упаковка', 'шт', 200, NOW()),
('RAW-PACK-003', 'Банка пластиковая 1л', 'raw', 'Упаковка', 'шт', 300, NOW())
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- ПОЛУФАБРИКАТЫ (SEMI-FINISHED)
-- ============================================================================

INSERT INTO skus (code, name, type, unit, min_stock, created_at) VALUES
('SEMI-001', 'Краска белая (полуфабрикат)', 'semi', 'кг', 100, NOW()),
('SEMI-002', 'Краска красная (полуфабрикат)', 'semi', 'кг', 50, NOW()),
('SEMI-003', 'Краска синяя (полуфабрикат)', 'semi', 'кг', 50, NOW()),
('SEMI-004', 'Шпатлевка базовая (полуфабрикат)', 'semi', 'кг', 200, NOW())
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- ГОТОВАЯ ПРОДУКЦИЯ (FINISHED)
-- ============================================================================

INSERT INTO skus (code, name, type, unit, min_stock, created_at) VALUES
('FIN-001', 'Краска белая 10кг', 'finished', 'шт', 20, NOW()),
('FIN-002', 'Краска белая 5кг', 'finished', 'шт', 30, NOW()),
('FIN-003', 'Краска красная 10кг', 'finished', 'шт', 10, NOW()),
('FIN-004', 'Краска синяя 10кг', 'finished', 'шт', 10, NOW()),
('FIN-005', 'Шпатлевка 20кг', 'finished', 'шт', 15, NOW())
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- ПОЛУЧАТЕЛИ (RECIPIENTS) - для тестирования отгрузок
-- ============================================================================

INSERT INTO recipients (name, contact_info, notes, created_at) VALUES
('ООО "Стройка+"', 'Тел: +7 (495) 123-45-67, email: info@stroyka.ru', 'Постоянный клиент, отсрочка 14 дней', NOW()),
('ИП Иванов И.И.', 'Тел: +7 (926) 555-11-22', 'Оплата по предоплате', NOW()),
('ООО "РемонтМастер"', 'Тел: +7 (499) 888-99-00, email: zakaz@remontmaster.ru', 'Крупный оптовый клиент', NOW())
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Вывод результата
-- ============================================================================

SELECT 'Добавлено сырья:' as info, COUNT(*) as count FROM skus WHERE type = 'raw'
UNION ALL
SELECT 'Добавлено полуфабрикатов:', COUNT(*) FROM skus WHERE type = 'semi'
UNION ALL
SELECT 'Добавлено готовой продукции:', COUNT(*) FROM skus WHERE type = 'finished'
UNION ALL
SELECT 'Добавлено получателей:', COUNT(*) FROM recipients;

-- Показываем список добавленного сырья
SELECT code, name, category, unit, min_stock
FROM skus
WHERE type = 'raw'
ORDER BY category, name;
