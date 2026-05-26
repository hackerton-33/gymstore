-- Migration: Add Featured Testimonials Table
-- Date: 2025-11-27
-- Description: Creates table for managing featured testimonials on About Us page

CREATE TABLE IF NOT EXISTS featured_testimonials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER UNIQUE NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER NOT NULL,
    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_featured_testimonials_display_order 
ON featured_testimonials(display_order);

CREATE INDEX IF NOT EXISTS idx_featured_testimonials_is_active 
ON featured_testimonials(is_active);

-- Insert sample data (optional - only if you have existing reviews)
-- Uncomment and modify if you want to pre-populate with existing 5-star reviews
-- INSERT INTO featured_testimonials (review_id, display_order, created_by)
-- SELECT id, 0, 1 FROM reviews WHERE rating = 5 LIMIT 1;
