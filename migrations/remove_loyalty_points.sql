-- Migration: Remove Loyalty Points System
-- Date: 2024
-- Description: Removes loyalty_points and points_transactions tables

-- Drop points_transactions table first (has foreign key to loyalty_points)
DROP TABLE IF EXISTS points_transactions;

-- Drop loyalty_points table
DROP TABLE IF EXISTS loyalty_points;
