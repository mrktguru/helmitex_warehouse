-- Manual migration: Add missing columns
-- This adds the columns that are in models.py but missing from database

-- Add updated_at to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

-- Add is_active to technological_cards table
ALTER TABLE technological_cards ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;
CREATE INDEX IF NOT EXISTS ix_technological_cards_is_active ON technological_cards (is_active);

-- Add is_active to packing_variants table
ALTER TABLE packing_variants ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;
CREATE INDEX IF NOT EXISTS ix_packing_variants_is_active ON packing_variants (is_active);

-- Update alembic version
INSERT INTO alembic_version (version_num) VALUES ('20251110_001')
ON CONFLICT (version_num) DO NOTHING;

-- Verification query (you can run this to check the changes)
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
