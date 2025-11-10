-- Create alembic_version table and set correct version
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Set to latest migration (20251110_001) since we manually applied it
INSERT INTO alembic_version (version_num) VALUES ('20251110_001')
ON CONFLICT (version_num) DO NOTHING;

-- Verify
SELECT 'Current Alembic version:' as info, version_num FROM alembic_version;
