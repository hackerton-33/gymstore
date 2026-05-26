-- Migration: Add Order Status Tracking System
-- Date: 2025-10-27
-- Description: Adds activity log for order status changes and improves order tracking

-- Create order status logs table
CREATE TABLE IF NOT EXISTS order_status_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    user_role VARCHAR(20) NOT NULL,
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    action VARCHAR(255) NOT NULL,
    notes TEXT,
    ip_address VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_status_logs_order ON order_status_logs(order_id);
CREATE INDEX IF NOT EXISTS idx_status_logs_user ON order_status_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_status_logs_created ON order_status_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_status_logs_status ON order_status_logs(new_status);

-- Add last_status_update column to orders table
ALTER TABLE orders ADD COLUMN last_status_update DATETIME;

-- Update existing orders to have last_status_update
UPDATE orders SET last_status_update = updated_at WHERE last_status_update IS NULL;
