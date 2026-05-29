-- Add firebase_uid column to users table for cross-platform authentication
ALTER TABLE users ADD COLUMN firebase_uid VARCHAR(255) UNIQUE;
CREATE INDEX idx_users_firebase_uid ON users(firebase_uid);
