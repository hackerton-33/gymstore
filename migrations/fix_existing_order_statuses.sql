-- Migration: Fix Existing Order Statuses
-- Date: 2025-10-27
-- Description: Updates old status values to match new system

-- Update old status values to new lowercase format
UPDATE orders SET status = 'pending' WHERE LOWER(status) = 'pending';
UPDATE orders SET status = 'confirmed' WHERE LOWER(status) IN ('confirmed', 'confirm');
UPDATE orders SET status = 'preparing' WHERE LOWER(status) IN ('preparing', 'processing');
UPDATE orders SET status = 'for_pickup' WHERE LOWER(status) IN ('shipped', 'for_pickup', 'ready');
UPDATE orders SET status = 'picked_up' WHERE LOWER(status) = 'picked_up';
UPDATE orders SET status = 'on_the_way' WHERE LOWER(status) IN ('on_the_way', 'in_transit', 'delivering');
UPDATE orders SET status = 'delivered' WHERE LOWER(status) = 'delivered';
UPDATE orders SET status = 'completed' WHERE LOWER(status) = 'completed';
UPDATE orders SET status = 'cancelled' WHERE LOWER(status) IN ('cancelled', 'canceled');
UPDATE orders SET status = 'refunded' WHERE LOWER(status) = 'refunded';

-- Initialize last_status_update for existing orders
UPDATE orders SET last_status_update = updated_at WHERE last_status_update IS NULL;
