-- Add missing delivery coordinate columns to orders table (MySQL)
-- Only add columns if they don't already exist
ALTER TABLE orders 
ADD COLUMN IF NOT EXISTS delivery_latitude DECIMAL(10, 8);

ALTER TABLE orders 
ADD COLUMN IF NOT EXISTS delivery_longitude DECIMAL(11, 8);

-- Add missing status tracking column
ALTER TABLE orders 
ADD COLUMN IF NOT EXISTS last_status_update DATETIME;
