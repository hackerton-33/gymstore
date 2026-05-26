-- Migration: Add delivery coordinates to orders table
-- Date: 2025-10-27
-- Description: Adds latitude and longitude fields for map integration

ALTER TABLE orders ADD COLUMN delivery_latitude REAL;
ALTER TABLE orders ADD COLUMN delivery_longitude REAL;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_orders_coordinates ON orders(delivery_latitude, delivery_longitude);
