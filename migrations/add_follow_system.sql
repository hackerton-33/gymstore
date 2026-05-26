-- Migration: Add Follow System for Seller Shops
-- Description: Allows buyers to follow sellers and view their shop pages

-- Create follows table
CREATE TABLE IF NOT EXISTS follows (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    follower_id INTEGER NOT NULL,
    following_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE,
    
    UNIQUE KEY unique_follower_following (follower_id, following_id),
    INDEX idx_follower (follower_id),
    INDEX idx_following (following_id),
    INDEX idx_created_at (created_at)
);

-- For SQLite (if using SQLite instead of MySQL)
-- CREATE TABLE IF NOT EXISTS follows (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     follower_id INTEGER NOT NULL,
--     following_id INTEGER NOT NULL,
--     created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
--     
--     FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
--     FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE,
--     
--     UNIQUE (follower_id, following_id)
-- );
-- 
-- CREATE INDEX IF NOT EXISTS idx_follows_follower ON follows(follower_id);
-- CREATE INDEX IF NOT EXISTS idx_follows_following ON follows(following_id);
-- CREATE INDEX IF NOT EXISTS idx_follows_created_at ON follows(created_at);
