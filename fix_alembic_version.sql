-- Check current alembic version
SELECT * FROM alembic_version;

-- If empty, set to the last applied migration
-- Since tables exist, we assume 20250204_001 was applied
DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('20250204_001');

-- Verify
SELECT * FROM alembic_version;
