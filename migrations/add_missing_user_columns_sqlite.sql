-- SQLite migration to add missing columns to users table
-- This script is for SQLite, not MySQL

-- Check if columns exist before adding them
-- Note: SQLite doesn't support IF NOT EXISTS for columns, so we need to handle this carefully

-- These columns should already exist from previous migration
-- If you get errors, it means they're already in the database

ALTER TABLE users ADD COLUMN business_name VARCHAR(200);
ALTER TABLE users ADD COLUMN business_permit VARCHAR(500);
ALTER TABLE users ADD COLUMN dti_certification VARCHAR(500);
ALTER TABLE users ADD COLUMN id_document VARCHAR(500);
ALTER TABLE users ADD COLUMN auth_type VARCHAR(20) DEFAULT 'manual';
ALTER TABLE users ADD COLUMN oauth_provider_id VARCHAR(100);

-- Update any existing records that might have wrong auth_type
UPDATE users SET auth_type = 'manual' WHERE auth_type = 'local' OR auth_type IS NULL;
