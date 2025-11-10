-- Fix remaining TIMESTAMP WITHOUT TIME ZONE columns

-- SKUs table - only created_at exists
ALTER TABLE skus
  ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC';

-- Stock table - only updated_at exists
ALTER TABLE stock
  ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE USING updated_at AT TIME ZONE 'UTC';

-- Verify all are now TIMESTAMPTZ
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name IN ('created_at', 'updated_at', 'last_active', 'started_at', 'completed_at', 'expires_at')
  AND data_type = 'timestamp without time zone'
ORDER BY table_name, column_name;

SELECT '✓ All remaining timestamp columns converted!' as status;
